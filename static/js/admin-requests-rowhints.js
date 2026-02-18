(() => {
  const rows = document.querySelectorAll("tr[data-sig-can-help]");
  if (!rows.length) return;

  rows.forEach((tr) => {
    const ch = parseInt(tr.dataset.sigCanHelp || "0", 10);
    if (ch > 0) tr.classList.add("hc-row-hot");
  });
})();
