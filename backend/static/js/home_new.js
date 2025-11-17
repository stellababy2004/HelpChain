// Extracted from inline script in home_new.html for CSP compliance.
// Minimal placeholder: toggle logic for admin fallback & QR onboarding panels.
// Extend with full i18n + dynamic counters as needed.

(function () {
  function initToggles() {
    const toggleButtons = document.querySelectorAll(".toggle");
    toggleButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const targetId = btn.getAttribute("data-target");
        const targetEl = document.getElementById(targetId);
        if (!targetEl) return;
        const isHidden =
          targetEl.style.display === "none" ||
          targetEl.classList.contains("admin-hidden") ||
          targetEl.classList.contains("qr-hidden");
        if (isHidden) {
          targetEl.style.display = "block";
          targetEl.classList.remove("admin-hidden", "qr-hidden");
          btn.setAttribute("aria-expanded", "true");
        } else {
          targetEl.style.display = "none";
          btn.setAttribute("aria-expanded", "false");
        }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", initToggles);
})();
