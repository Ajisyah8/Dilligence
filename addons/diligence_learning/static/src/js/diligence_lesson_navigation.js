/** @odoo-module **/

const STORAGE_KEY = "diligence.lesson.reader.position";
const LESSON_LINK_SELECTOR =
    ".diligence-lesson-viewer .diligence-sidebar-lesson-card > a[href^='/slides/slide/']";

if ("scrollRestoration" in window.history) {
    window.history.scrollRestoration = "manual";
}

document.addEventListener("click", (event) => {
    const link = event.target.closest(LESSON_LINK_SELECTOR);
    if (!link) {
        return;
    }
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
        pageY: window.scrollY,
        sidebarY: document.querySelector(".diligence-lesson-main .o_wslides_lesson_aside_list")?.scrollTop || 0,
        savedAt: Date.now(),
    }));
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
    const restore = () => {
        window.scrollTo({
            top: Number(position.pageY) || 0,
            left: 0,
            behavior: "auto",
        });
        const sidebar = document.querySelector(".diligence-lesson-main .o_wslides_lesson_aside_list");
        if (sidebar) {
            sidebar.scrollTop = Number(position.sidebarY) || 0;
        }
    };
    [0, 50, 150, 350, 700, 1200, 2000].forEach((delay) => {
        window.setTimeout(restore, delay);
    });
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
