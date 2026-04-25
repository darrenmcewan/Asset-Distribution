/**
 * Lightweight modal helper for disclaimer dialogs (welcome + claim confirmation).
 * Exposes window.Disclaimer with show()/hide() and a buildPanel() utility.
 */
(function () {
    function ensureContainer() {
        var el = document.getElementById('disclaimer-modal');
        if (el) return el;
        el = document.createElement('div');
        el.id = 'disclaimer-modal';
        el.className = 'disclaimer-modal';
        el.setAttribute('role', 'dialog');
        el.setAttribute('aria-modal', 'true');
        document.body.appendChild(el);
        return el;
    }

    function show(panelHtml, opts) {
        opts = opts || {};
        var modal = ensureContainer();
        modal.innerHTML = '<div class="disclaimer-modal__panel">' + panelHtml + '</div>';
        modal.classList.add('is-open');
        document.body.style.overflow = 'hidden';

        if (!opts.allowBackdropClose) {
            modal.onclick = null;
        } else {
            modal.onclick = function (e) { if (e.target === modal) hide(); };
        }
        return modal;
    }

    function hide() {
        var modal = document.getElementById('disclaimer-modal');
        if (!modal) return;
        modal.classList.remove('is-open');
        modal.innerHTML = '';
        document.body.style.overflow = '';
    }

    function escapeHtml(s) {
        return String(s || '').replace(/[&<>"']/g, function (c) {
            return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
        });
    }

    window.Disclaimer = { show: show, hide: hide, escapeHtml: escapeHtml };
})();
