/** @odoo-module **/

const uploadFormSelector = 'form[data-diligence-payment-upload="1"]';

document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.matches(uploadFormSelector)) {
        return;
    }
    if (form.dataset.diligenceProcessing === "1") {
        event.preventDefault();
        return;
    }

    const button = event.submitter || form.querySelector("button[type='submit']");
    if (!button) {
        return;
    }

    form.dataset.diligenceProcessing = "1";
    form.setAttribute("aria-busy", "true");
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    button.innerHTML = [
        '<span class="diligence-payment-spinner" aria-hidden="true"></span>',
        '<span>Memproses pembayaran...</span>',
    ].join("");

    const status = document.createElement("div");
    status.className = "small text-muted mt-2";
    status.setAttribute("role", "status");
    status.textContent = "Bukti pembayaran sedang dikirim. Mohon jangan menutup halaman ini.";
    form.append(status);
});
