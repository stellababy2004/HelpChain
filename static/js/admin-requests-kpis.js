(() => {
  const kpiWrap = document.getElementById("hcAdminKpis");
  const rows = document.querySelectorAll("[data-hc-status-row]");
  if (!kpiWrap || !rows.length) return;
  if (kpiWrap.dataset.summaryCountsSource === "server") return;

  function recompute(){
    const counts = { NEW:0, ASSIGNED:0, IN_PROGRESS:0, COMPLETED:0, CLOSED:0, URGENT:0 };
    rows.forEach(r => {
      const s = (r.dataset.hcStatusRow || "").trim();
      if (counts[s] !== undefined) counts[s] += 1;
      const p = (r.dataset.priority || "").trim().toUpperCase();
      if (p === "URGENT" || p === "CRITICAL" || p === "HIGH") counts.URGENT += 1;
    });

    kpiWrap.querySelectorAll("[data-request-summary-kpi]").forEach(card => {
      const key = card.dataset.requestSummaryKpi;
      const v = card.querySelector(`[data-kpi-target="${key}"]`);
      if (v) v.textContent = String(counts[key] ?? 0);
    });
  }

  recompute();
})();
