document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-fold-toggle]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const panelId = btn.getAttribute("aria-controls");
      const panel = panelId ? document.getElementById(panelId) : null;
      if (!panel) return;

      const isOpen = btn.getAttribute("aria-expanded") === "true";
      btn.setAttribute("aria-expanded", String(!isOpen));
      panel.hidden = isOpen;
    });
  });
});
