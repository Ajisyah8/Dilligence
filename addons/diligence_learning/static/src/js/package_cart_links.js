/** @odoo-module **/

// Keep the visible cart action on the learning-package URL, including
// notification links injected after an AJAX add-to-cart operation.
(() => {
    const packagePath = (url) => {
        if (!url) return url;
        return url.replace('/shop/address', '/paket-belajar/address')
            .replace('/shop/cart', '/paket-belajar/cart')
            .replace('/shop/checkout', '/paket-belajar/checkout')
            .replace('/shop/extra_info', '/paket-belajar/extra_info')
            .replace('/shop/payment', '/paket-belajar/payment')
            .replace('/shop/confirmation', '/paket-belajar/confirmation');
    };

    const rewrite = (root = document) => {
        root.querySelectorAll?.('a[href="/shop/cart"], a[href^="/shop/cart?"]').forEach((link) => {
            link.setAttribute('href', link.getAttribute('href').replace('/shop/cart', '/paket-belajar/cart'));
        });
        root.querySelectorAll?.('a[href*="/shop/address"], a[href*="/shop/checkout"], a[href*="/shop/payment"], a[href*="/shop/confirmation"]').forEach((link) => {
            link.setAttribute('href', packagePath(link.getAttribute('href')));
        });
    };
    rewrite();
    document.addEventListener('click', (event) => {
        const link = event.target.closest?.('a[href]');
        if (!link) return;
        const rewritten = packagePath(link.getAttribute('href'));
        if (rewritten !== link.getAttribute('href')) {
            event.preventDefault();
            window.location.assign(rewritten);
        }
    }, true);
    new MutationObserver(() => rewrite()).observe(document.body, {childList: true, subtree: true});
})();
