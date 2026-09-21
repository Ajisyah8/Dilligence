/** @odoo-module **/

// Search analytics intentionally stores only aggregate, normalized phrases.
// It must never block navigation or expose a visitor identity.
if (!window.__diligenceSeoSearchTrackingInstalled) {
    window.__diligenceSeoSearchTrackingInstalled = true;

    document.addEventListener("submit", (event) => {
        const form = event.target.closest("form.o_searchbar_form");
        if (!form || !form.action.includes("/website/search")) {
            return;
        }
        const input = form.querySelector("input[name='search']");
        const query = input?.value?.trim();
        if (!query || query.length < 2) {
            return;
        }
        const payload = JSON.stringify({
            jsonrpc: "2.0",
            method: "call",
            params: {query: query.slice(0, 120)},
            id: Date.now(),
        });
        try {
            fetch("/diligence/seo/search-track", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: payload,
                credentials: "same-origin",
                keepalive: true,
            }).catch(() => {});
        } catch {
            // Search navigation must continue even if analytics is unavailable.
        }
    }, true);
}
