/** @odoo-module **/

/* A course URL is an overview in website_slides.  Diligence learners should
 * land in the reader instead: the native reader already provides the lesson
 * outline on the left and the active material on the right. */
function openDiligenceCourseReader() {
    const hero = document.querySelector('.diligence-course-hero[data-diligence-first-slide-url]');
    if (!hero || !hero.dataset.diligenceFirstSlideUrl) return;
    if (hero.dataset.diligenceReaderEntry !== '1') return;

    const params = new URLSearchParams(window.location.search);
    if (params.get('overview') === '1') return;

    window.location.replace(hero.dataset.diligenceFirstSlideUrl);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', openDiligenceCourseReader, {once: true});
} else {
    openDiligenceCourseReader();
}
