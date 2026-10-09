/** @odoo-module **/

/** Keep the desktop header's active state consistent on controller routes.
 *
 * Odoo marks normal website.page links active, but the Programs dropdown has
 * an href of "#" and /blog redirects to a concrete blog slug.  Resolve those
 * two route families explicitly while preserving Odoo's native active state.
 */
function setDiligenceActiveMenu() {
    const menu = document.querySelector('#top #top_menu');
    if (!menu) return;

    const path = window.location.pathname.replace(/\/+$/, '') || '/';
    const topLinks = [...menu.querySelectorAll(':scope > li > .nav-link')];

    for (const link of topLinks) {
        const item = link.closest(':scope > li') || link.parentElement;
        const href = link.getAttribute('href') || '';
        let active = false;

        if (href === '/') {
            active = path === '/';
        } else if (href === '/blog') {
            active = path === '/blog' || path.startsWith('/blog/');
        } else if (item?.querySelector('a[href^="/slides"]')) {
            active = path === '/slides' || path.startsWith('/slides/');
        } else if (href.startsWith('/')) {
            const cleanHref = href.split(/[?#]/, 1)[0].replace(/\/+$/, '');
            active = path === cleanHref || path.startsWith(`${cleanHref}/`);
        }

        link.classList.toggle('active', active);
        item?.classList.toggle('active', active);
        if (active) {
            link.setAttribute('aria-current', 'page');
        } else {
            link.removeAttribute('aria-current');
        }
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setDiligenceActiveMenu, {once: true});
} else {
    setDiligenceActiveMenu();
}
