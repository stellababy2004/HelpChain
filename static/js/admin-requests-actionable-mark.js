(() => {
  const rows = document.querySelectorAll("tr[data-hc-status-row]");
  if (!rows.length) return;

  function isActionable(tr){
    const status = (tr.dataset.hcStatusRow || "").trim();
    const owner = (tr.dataset.ownerId || "").trim();
    const canHelp = parseInt(tr.dataset.sigCanHelp || "0", 10);

    const unassignedOpen = (!owner && !["CLOSED","COMPLETED"].includes(status));
    const inProgress = (status === "IN_PROGRESS");
    const hasCanHelp = (canHelp > 0);

    return unassignedOpen || inProgress || hasCanHelp;
  }

  rows.forEach(tr => {
    if (isActionable(tr)) tr.classList.add("hc-row-actionable");
  });
})();
