/** @odoo-module **/

async function diligenceRpc(route, params) {
    const response = await fetch(route, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({
            jsonrpc: '2.0',
            method: 'call',
            params,
            id: Date.now(),
        }),
    });
    if (!response.ok) throw new Error(`RPC request failed: ${response.status}`);
    const payload = await response.json();
    if (payload.error) throw new Error(payload.error.message || 'RPC error');
    return payload.result;
}

const STORAGE_KEY = "diligence.lesson.reader.position";
const LESSON_LINK_SELECTOR =
    ".diligence-lesson-viewer a[href*='/slides/slide/']";

if ("scrollRestoration" in window.history) {
    window.history.scrollRestoration = "manual";
}

function getLessonPosition() {
    return {
        pageY: window.scrollY,
        sidebarY: document.querySelector(
            ".diligence-lesson-main .o_wslides_lesson_aside_list"
        )?.scrollTop || 0,
        savedAt: Date.now(),
    };
}

function saveLessonPosition() {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(getLessonPosition()));
}

function keepSelectedLessonVisible(targetHref = window.location.href) {
    const sidebar = document.querySelector(
        ".diligence-lesson-main .o_wslides_lesson_aside_list"
    );
    if (!sidebar) return;

    const targetPath = new URL(targetHref, window.location.origin).pathname;
    // Odoo rebuilds the sidebar and may change the link wrapper classes. The
    // stable identifier is the native data-id rendered for every lesson.
    const idMatch = targetPath.match(/-(\d+)\/?$/);
    const targetId = idMatch?.[1];
    const item = targetId
        ? sidebar.querySelector(`[data-id="${targetId}"]`)
        : null;
    const link = item?.querySelector("a[href*='/slides/slide/']") || [...sidebar.querySelectorAll(
        "a[href*='/slides/slide/']"
    )].find((candidate) => (
        new URL(candidate.href, window.location.origin).pathname === targetPath
    ));
    const selectedItem = item || link?.closest(
        ".diligence-sidebar-lesson-card, .o_wslides_lesson_aside_list_link"
    );
    if (!selectedItem) return;

    const sidebarRect = sidebar.getBoundingClientRect();
    const itemRect = selectedItem.getBoundingClientRect();
    const itemTop = itemRect.top - sidebarRect.top + sidebar.scrollTop;
    const itemBottom = itemRect.bottom - sidebarRect.top + sidebar.scrollTop;
    const viewTop = sidebar.scrollTop;
    const viewBottom = viewTop + sidebar.clientHeight;
    if (itemTop >= viewTop && itemBottom <= viewBottom) return;

    if (itemTop < viewTop) {
        sidebar.scrollTop = Math.max(0, itemTop - 24);
    } else {
        sidebar.scrollTop = Math.max(0, itemBottom - sidebar.clientHeight + 24);
    }
}

function restoreLessonPosition(position, targetHref = window.location.href) {
    if (!document.querySelector(".diligence-lesson-viewer")) return;
    const restore = () => {
        window.scrollTo({
            top: Number(position.pageY) || 0,
            left: 0,
            behavior: "auto",
        });
        const sidebar = document.querySelector(
            ".diligence-lesson-main .o_wslides_lesson_aside_list"
        );
        if (sidebar) sidebar.scrollTop = Number(position.sidebarY) || 0;
        keepSelectedLessonVisible(targetHref);
    };
    requestAnimationFrame(restore);
    [80, 250, 500, 900, 1500, 2500].forEach((delay) => {
        window.setTimeout(restore, delay);
    });
}

let lessonNavigationBusy = false;

async function navigateLessonWithRpc(link) {
    if (lessonNavigationBusy) return;
    lessonNavigationBusy = true;
    const position = getLessonPosition();
    saveLessonPosition();
    link.setAttribute('aria-busy', 'true');
    link.classList.add('diligence-lesson-loading');
    try {
        const match = link.pathname.match(/\/slides\/slide\/([^/]+)/);
        if (!match) throw new Error('Invalid lesson URL');
        const response = await diligenceRpc('/diligence/slides/slide/content', {
            slide_id: decodeURIComponent(match[1]),
        });
        if (!response?.html) throw new Error(response?.error || 'Lesson unavailable');

        const parsed = new DOMParser().parseFromString(response.html, 'text/html');
        const nextWrap = parsed.querySelector('#wrap');
        const currentWrap = document.querySelector('#wrap');
        if (!nextWrap || !currentWrap) throw new Error('Lesson content not found');

        currentWrap.replaceWith(nextWrap);
        window.history.pushState({diligenceLesson: true}, '', link.href);
        if (response.title) document.title = response.title;
        restoreLessonPosition(position, link.href);
        document.dispatchEvent(new CustomEvent('diligence:lesson-replaced', {
            detail: {url: link.href},
        }));
    } catch (error) {
        // Native navigation remains a safe fallback if the RPC is unavailable.
        console.warn('Diligence lesson RPC navigation failed; using native link', error);
        window.location.assign(link.href);
    } finally {
        link.removeAttribute('aria-busy');
        link.classList.remove('diligence-lesson-loading');
        lessonNavigationBusy = false;
    }
}

document.addEventListener("click", (event) => {
    const link = event.target.closest(LESSON_LINK_SELECTOR);
    if (!link) {
        return;
    }
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    event.stopPropagation();
    navigateLessonWithRpc(link);
}, true);

function restoreLessonReaderPosition() {
    if (!document.querySelector(".diligence-lesson-viewer")) {
        return;
    }
    const rawPosition = sessionStorage.getItem(STORAGE_KEY);
    if (!rawPosition) {
        return;
    }
    let position;
    try {
        position = JSON.parse(rawPosition);
    } catch {
        sessionStorage.removeItem(STORAGE_KEY);
        return;
    }
    if (!position.savedAt || Date.now() - position.savedAt > 10000) {
        sessionStorage.removeItem(STORAGE_KEY);
        return;
    }
    restoreLessonPosition(position, window.location.href);
    window.setTimeout(() => sessionStorage.removeItem(STORAGE_KEY), 2500);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", restoreLessonReaderPosition, {once: true});
} else {
    restoreLessonReaderPosition();
}
window.addEventListener("pageshow", restoreLessonReaderPosition);

let audioRefreshSequence = 0;

async function refreshVisibleLessonAudio() {
    if (document.visibilityState !== "visible") {
        return;
    }
    const audio = document.querySelector("audio[data-diligence-audio-id]");
    if (!audio || !audio.paused) {
        return;
    }
    const slideId = audio.dataset.diligenceAudioId;
    const sequence = ++audioRefreshSequence;
    try {
        const response = await fetch(
            `/diligence/slides/media/${encodeURIComponent(slideId)}?v=${Date.now()}`,
            {cache: "no-store", credentials: "same-origin"}
        );
        if (!response.ok || sequence !== audioRefreshSequence) {
            return;
        }
        const blob = await response.blob();
        if (sequence !== audioRefreshSequence) {
            return;
        }
        const previousObjectUrl = audio.dataset.diligenceObjectUrl;
        const objectUrl = URL.createObjectURL(blob);
        audio.src = objectUrl;
        audio.dataset.diligenceObjectUrl = objectUrl;
        audio.load();
        if (previousObjectUrl) {
            URL.revokeObjectURL(previousObjectUrl);
        }
    } catch {
        // Keep the server-rendered audio URL when a refresh request is interrupted.
    }
}

document.addEventListener("visibilitychange", refreshVisibleLessonAudio);
window.addEventListener("pageshow", refreshVisibleLessonAudio);
