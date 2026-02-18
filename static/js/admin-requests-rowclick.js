(() => {
  const rows = document.querySelectorAll("tr[data-href]");
  if (!rows.length) return;

  function isInteractive(el){
    if (!el) return false;
    return !!el.closest("a, button, input, select, textarea, label, [role='button'], [data-no-rowclick]");
  }

  rows.forEach(tr => {
    tr.style.cursor = "pointer";
    tr.tabIndex = 0;
    tr.setAttribute("role", "link");

    tr.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" && e.key !== " ") return;
      if (isInteractive(e.target)) return;
      e.preventDefault();
      const href = tr.dataset.href;
      if (href) window.location.href = href;
    });

    tr.addEventListener("click", (e) => {
      // ignore clicks on interactive elements
      if (isInteractive(e.target)) return;

      const href = tr.dataset.href;
      if (!href) return;

      // open same tab
      window.location.href = href;
    });

    // optional: open in new tab with Ctrl/Meta
    tr.addEventListener("auxclick", (e) => {
      if (e.button !== 1) return; // middle click
      if (isInteractive(e.target)) return;
      const href = tr.dataset.href;
      if (href) window.open(href, "_blank", "noopener");
    });
  });
})();
