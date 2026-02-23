(() => {
  const rows = document.querySelectorAll("tr[data-hc-status-row]");
  const elUnassigned = document.getElementById("hcLiveUnassigned");
  const elInProgress = document.getElementById("hcLiveInProgress");
  const elCanHelp = document.getElementById("hcLiveCanHelp");
  if (!rows.length || (!elUnassigned && !elInProgress && !elCanHelp)) return;

  function recompute(){
    let inProgress = 0;
    let unassigned = 0;
    let canHelpTotal = 0;

    rows.forEach(row => {
      const status = (row.dataset.hcStatusRow || "").trim();
      const assignedId = (row.dataset.assignedVolunteerId || "").trim();
      const canHelp = parseInt(row.dataset.sigCanHelp || "0", 10);

      if (status === "IN_PROGRESS") inProgress += 1;
      if (!assignedId && !["CLOSED", "COMPLETED"].includes(status)) unassigned += 1;
      canHelpTotal += Number.isNaN(canHelp) ? 0 : canHelp;
    });

    if (elUnassigned) elUnassigned.textContent = `• Sans bénévole assigné: ${unassigned}`;
    if (elInProgress) elInProgress.textContent = `• En cours: ${inProgress}`;
    if (elCanHelp) elCanHelp.textContent = `• Disponibles (CAN_HELP): ${canHelpTotal}`;
  }

  recompute();
})();
