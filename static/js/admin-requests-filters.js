(() => {
  const rows = Array.from(document.querySelectorAll("tr[data-hc-status-row]"));
  const tabs = Array.from(document.querySelectorAll("[data-hc-tab]"));
  const kpiCards = Array.from(document.querySelectorAll("#hcAdminKpis [data-kpi]"));
  const btnAction = document.getElementById("hcToggleActionable");

  if (!rows.length || (!tabs.length && !kpiCards.length && !btnAction)) return;

  let activeTab = "ALL";
  let actionOnly = false;
  const actionLabelBase = btnAction ? (btnAction.textContent || "Actions prioritaires").trim() : "Actions prioritaires";

  function normalizeTab(v){
    const val = (v || "").toUpperCase();
    const allowed = new Set(["ALL","NEW","ASSIGNED","IN_PROGRESS","COMPLETED","CLOSED"]);
    return allowed.has(val) ? val : "ALL";
  }

  function readFromUrl(){
    const u = new URL(window.location.href);
    activeTab = normalizeTab(u.searchParams.get("tab") || "ALL");
    actionOnly = (u.searchParams.get("action") === "1");
  }

  function writeToUrl(){
    const u = new URL(window.location.href);

    if (activeTab && activeTab !== "ALL") u.searchParams.set("tab", activeTab);
    else u.searchParams.delete("tab");

    if (actionOnly) u.searchParams.set("action", "1");
    else u.searchParams.delete("action");

    // update without reload
    window.history.replaceState({ tab: activeTab, action: actionOnly ? 1 : 0 }, "", u.toString());
  }

  function isActionable(tr) {
    const status = (tr.dataset.hcStatusRow || "").trim();
    const assigned = (tr.dataset.assignedVolunteerId || "").trim();
    const canHelp = parseInt(tr.dataset.sigCanHelp || "0", 10);

    const unassignedOpen = !assigned && !["CLOSED", "COMPLETED"].includes(status);
    const inProgress = status === "IN_PROGRESS";
    const hasCanHelp = canHelp > 0;

    return unassignedOpen || inProgress || hasCanHelp;
  }

  function passesTab(tr) {
    const s = (tr.dataset.hcStatusRow || "").trim();
    return activeTab === "ALL" || s === activeTab;
  }

  function applyFilters({ syncUrl = true } = {}) {
    let actionableCount = 0;
    rows.forEach((tr) => {
      const actionable = isActionable(tr);
      if (actionable) actionableCount += 1;
      const ok = passesTab(tr) && (!actionOnly || actionable);
      tr.style.display = ok ? "" : "none";
    });

    tabs.forEach((t) =>
      t.setAttribute("aria-current", String(t.dataset.hcTab === activeTab))
    );

    if (btnAction) {
      btnAction.setAttribute("aria-current", String(actionOnly));
      btnAction.textContent = `${actionLabelBase} (${actionableCount})`;
    }
    if (syncUrl) writeToUrl();
  }

  tabs.forEach((t) => {
    t.addEventListener("click", () => {
      activeTab = t.dataset.hcTab || "ALL";
      applyFilters();
    });
  });

  kpiCards.forEach((card) => {
    card.style.cursor = "pointer";
    card.addEventListener("click", () => {
      activeTab = card.dataset.kpi || "ALL";
      applyFilters();
    });
  });

  if (btnAction) {
    btnAction.addEventListener("click", () => {
      actionOnly = !actionOnly;
      applyFilters();
    });
  }

  window.addEventListener("popstate", () => {
    readFromUrl();
    applyFilters({ syncUrl: false });
  });

  readFromUrl();
  applyFilters({ syncUrl: true });
})();
