/** @odoo-module **/

import Fullscreen from '@website_slides/js/slides_course_fullscreen_player';

/* Keep the fullscreen course outline expanded after website_slides renders or
   replaces the current lesson.  This is separate from the quiz script so it
   is always available on PDF, audio, video and article lessons. */
function keepDiligenceFullscreenSidebarOpen() {
    /* Kept as a hook for the fullscreen player; section dropdowns are now
       controlled by Bootstrap so learners can open and close them. */
}

function syncDiligenceFullscreenCompletionButton() {
    const button = document.querySelector('.diligence-fullscreen-mark-completed');
    const activeLesson = document.querySelector('.o_wslides_fs_sidebar_list_item.active');
    if (!button || !activeLesson) return;

    const slideId = activeLesson.dataset.id;
    const isCompleted = activeLesson.dataset.completed === 'true'
        || Boolean(activeLesson.querySelector('.o_wslides_slide_completed'));
    const label = button.querySelector('span');
    const doneContainer = activeLesson.querySelector('.o_wslides_sidebar_done_button');
    let doneIcon = doneContainer?.querySelector('i');

    button.dataset.slideId = slideId;
    button.classList.toggle('is-completed', isCompleted);
    if (doneContainer && isCompleted && !doneIcon) {
        doneIcon = document.createElement('i');
        doneContainer.replaceChildren(doneIcon);
    }
    if (doneIcon && isCompleted) {
        doneIcon.className = 'o_wslides_slide_completed fa fa-check-circle fa-fw text-success fa-lg';
        doneIcon.title = 'Completed';
    }
    if (isCompleted) {
        if (button.hasAttribute('href')) button.removeAttribute('href');
        if (button.getAttribute('aria-disabled') !== 'true') button.setAttribute('aria-disabled', 'true');
        if (label && label.textContent !== 'Completed') label.textContent = 'Completed';
    } else {
        const href = `/diligence/slides/slide/${slideId}/set_completed`;
        if (button.getAttribute('href') !== href) button.setAttribute('href', href);
        if (button.hasAttribute('aria-disabled')) button.removeAttribute('aria-disabled');
        if (label && label.textContent !== 'Mark as Completed') label.textContent = 'Mark as Completed';
    }
}

/* The native fullscreen player renders the media first, but keeps the lesson
   description in the normal lesson page.  Put the same trusted Odoo HTML
   directly below the rendered preview, matching the course-reader flow. */
let diligenceDescriptionRequest = null;
let diligenceDescriptionRefreshTimers = [];
const diligenceDescriptionCache = new Map();

async function loadDiligenceLessonDescription(slideId, preferredDescription = '') {
    if (preferredDescription?.trim()) {
        diligenceDescriptionCache.set(String(slideId), preferredDescription);
        return preferredDescription;
    }
    if (diligenceDescriptionCache.has(String(slideId))) {
        return diligenceDescriptionCache.get(String(slideId));
    }

    const response = await fetch(`/diligence/slides/description/${slideId}`, {
        credentials: 'same-origin',
        headers: {'X-Requested-With': 'XMLHttpRequest'},
    });
    if (!response.ok) {
        throw new Error(`Description request failed: ${response.status}`);
    }
    const description = (await response.json()).description || '';
    diligenceDescriptionCache.set(String(slideId), description);
    return description;
}

function scheduleDiligenceFullscreenDescriptionRefresh() {
    diligenceDescriptionRefreshTimers.forEach((timer) => window.clearTimeout(timer));
    diligenceDescriptionRefreshTimers = [100, 300, 600, 1000, 1600].map((delay) => (
        window.setTimeout(() => renderDiligenceFullscreenDescription(), delay)
    ));
}

async function renderDiligenceFullscreenDescription() {
    const content = document.querySelector('.o_wslides_fs_content');
    const activeLesson = document.querySelector('.o_wslides_fs_sidebar_list_item.active[data-id]');
    if (!content || !activeLesson) {
        return;
    }

    const slideId = activeLesson.dataset.id;
    if (!slideId) return;

    /* The native player replaces the content node when moving to the next
       lesson. Remove only a description belonging to a previous slide. */
    const existingDescription = content.querySelector('.diligence-fs-media-description');
    if (existingDescription && existingDescription.dataset.slideId !== slideId) {
        existingDescription.remove();
    }
    if (content.querySelector(
        `.diligence-fs-media-description[data-slide-id="${slideId}"][data-description-resolved="true"]`
    )) {
        return;
    }
    /* Every native lesson renderer creates a child in this container.  Do
       not filter by a particular media tag: PDF/document viewers, audio,
       local video, external video, infographic and article lessons all need
       the same description placement. */
    if (!content.children.length) {
        return;
    }

    if (!slideId || diligenceDescriptionRequest?.slideId === slideId && diligenceDescriptionRequest.pending) {
        return;
    }
    diligenceDescriptionRequest = {slideId, pending: true};
    const source = document.querySelector(`.diligence-fs-description-source[data-slide-id="${slideId}"]`);
    const sidebarDescription = activeLesson.dataset.description || '';
    let description = source?.dataset.description || sidebarDescription;
    try {
        description = await loadDiligenceLessonDescription(slideId, description);
    } catch (error) {
        console.warn('Unable to load lesson description', error);
        return;
    } finally {
        if (diligenceDescriptionRequest?.slideId === slideId) {
            diligenceDescriptionRequest.pending = false;
        }
    }

    /* Odoo finishes replacing the media asynchronously after the sidebar
       active state changes. Wait briefly, then re-query the DOM: the original
       content reference may already have been replaced by the native player. */
    await new Promise((resolve) => window.setTimeout(resolve, 250));
    const currentContent = document.querySelector('.o_wslides_fs_content');
    const currentLesson = document.querySelector('.o_wslides_fs_sidebar_list_item.active[data-id]');
    if (!description.trim() || !currentContent || !currentLesson
        || currentLesson.dataset.id !== slideId || !currentContent.children.length) {
        return;
    }

    currentContent.querySelectorAll('.diligence-fs-media-description').forEach((node) => node.remove());

    const block = document.createElement('section');
    block.className = 'diligence-fs-media-description';
    block.dataset.slideId = slideId;
    block.dataset.descriptionResolved = 'true';
    block.innerHTML = `
        <div class="diligence-fs-media-description-kicker">ABOUT THIS LESSON</div>
        <div class="diligence-fs-media-description-body">${description}</div>
    `;
    const quizContainer = currentContent.querySelector('.o_wslides_fs_quiz_container, .o_diligence_fs_quiz');
    const quizBody = quizContainer?.querySelector(':scope > .container');
    if (quizBody) {
        /* Quiz has no media stage, so keep its description below the lesson
           title and before the questions/results. */
        quizBody.prepend(block);
    } else {
        currentContent.appendChild(block);
    }
}

async function mountDiligenceDescriptionForRenderedSlide(fullscreen, slide) {
    const content = fullscreen.el?.querySelector('.o_wslides_fs_content');
    if (!content || !slide?.id || !content.children.length) return;

    const sidebarLesson = document.querySelector(
        `.o_wslides_fs_sidebar_list_item[data-id="${slide.id}"]:not([data-is-quiz="1"])`
    );
    const source = document.querySelector(
        `.diligence-fs-description-source[data-slide-id="${slide.id}"]`
    );
    const preferredDescription = slide.description
        || sidebarLesson?.dataset.description
        || source?.dataset.description
        || '';
    let description;
    try {
        description = await loadDiligenceLessonDescription(slide.id, preferredDescription);
    } catch (error) {
        console.warn('Unable to load lesson description', error);
        return;
    }

    /* The learner may navigate again while the request is in flight. Never
       attach the previous lesson's description to the newly rendered media. */
    const activeLesson = document.querySelector('.o_wslides_fs_sidebar_list_item.active[data-id]');
    const currentContent = fullscreen.el?.querySelector('.o_wslides_fs_content');
    if (!currentContent || activeLesson?.dataset.id !== String(slide.id)) return;

    currentContent.querySelectorAll('.diligence-fs-media-description').forEach((node) => node.remove());

    const block = document.createElement('section');
    block.className = 'diligence-fs-media-description';
    block.dataset.slideId = String(slide.id);
    block.dataset.descriptionResolved = 'true';
    block.innerHTML = `
        <div class="diligence-fs-media-description-kicker">ABOUT THIS LESSON</div>
        <div class="diligence-fs-media-description-body">${description}</div>
    `;

    const quizContainer = currentContent.querySelector('.o_wslides_fs_quiz_container, .o_diligence_fs_quiz');
    const quizBody = quizContainer?.querySelector(':scope > .container');
    if (quizBody) {
        quizBody.prepend(block);
    } else {
        currentContent.appendChild(block);
    }
}

/* Fullscreen navigation is client-side. Attach the description to the real
   website_slides render lifecycle so every completed media render receives
   its own description without requiring a browser refresh. */
Fullscreen.include({
    async _renderSlide() {
        const result = await this._super(...arguments);
        await mountDiligenceDescriptionForRenderedSlide(this, this._slideValue);
        scheduleDiligenceFullscreenDescriptionRefresh();
        return result;
    },
});

/* The native sidebar deliberately calls stopPropagation() on lesson clicks.
   Capture the event before that handler so the description refresh is still
   scheduled when a learner navigates without a full page reload. */
document.addEventListener('click', async (event) => {
    if (event.target.closest(
        '.o_wslides_fs_sidebar_list_item a, .o_wslides_fs_slide_nav, '
        + '.o_wslides_fs_next, .o_wslides_fs_previous, '
        + '.o_wslides_fs_header a'
    )) {
        scheduleDiligenceFullscreenDescriptionRefresh();
    }

    const button = event.target.closest('.diligence-fullscreen-mark-completed');
    if (!button || button.getAttribute('aria-disabled') === 'true') {
        return;
    }

    event.preventDefault();
    button.setAttribute('aria-disabled', 'true');
    button.classList.add('is-loading');

    try {
        const response = await fetch(button.href, {
            credentials: 'same-origin',
            headers: {'X-Requested-With': 'XMLHttpRequest'},
        });
        if (!response.ok) {
            throw new Error(`Completion request failed: ${response.status}`);
        }

        button.classList.remove('is-loading');
        button.classList.add('is-completed');
        button.removeAttribute('href');
        const label = button.querySelector('span');
        if (label) {
            label.textContent = 'Completed';
        }

        const slideId = button.dataset.slideId;
        const sidebarItem = document.querySelector(
            `.o_wslides_fs_sidebar_list_item[data-id="${slideId}"]`
        );
        const doneIcon = sidebarItem?.querySelector('.o_wslides_sidebar_done_button i');
        if (doneIcon) {
            doneIcon.className = 'o_wslides_slide_completed fa fa-check-circle fa-fw text-success fa-lg';
            doneIcon.title = 'Completed';
        }
        const doneContainer = sidebarItem?.querySelector('.o_wslides_sidebar_done_button');
        doneContainer?.setAttribute('data-completed', 'true');
        syncDiligenceFullscreenCompletionButton();
    } catch (error) {
        button.removeAttribute('aria-disabled');
        button.classList.remove('is-loading');
        console.error(error);
    }
}, true);

window.addEventListener('popstate', scheduleDiligenceFullscreenDescriptionRefresh);
window.addEventListener('hashchange', scheduleDiligenceFullscreenDescriptionRefresh);

const diligenceFullscreenObserver = new MutationObserver(() => {
    keepDiligenceFullscreenSidebarOpen();
    syncDiligenceFullscreenCompletionButton();
    renderDiligenceFullscreenDescription();
});
diligenceFullscreenObserver.observe(document.body, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['data-completed'],
});
keepDiligenceFullscreenSidebarOpen();
syncDiligenceFullscreenCompletionButton();
renderDiligenceFullscreenDescription();
window.setInterval(syncDiligenceFullscreenCompletionButton, 300);
window.setInterval(renderDiligenceFullscreenDescription, 300);
