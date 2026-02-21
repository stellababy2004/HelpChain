document.addEventListener("DOMContentLoaded", function () {
  const section = document.querySelector(".hc-ops-kpis");
  if (!section) return;
  const select = section.querySelector("[data-ops-days]");
  const windowLabel = document.getElementById("opsWindowLabel");

  function formatHours(hours) {
    const n = Number(hours);
    if (!Number.isFinite(n) || n <= 0) return "0h";
    const total = Math.round(n);
    const days = Math.floor(total / 24);
    const rem = total % 24;
    return days > 0 ? `${days}j ${rem}h` : `${rem}h`;
  }

  function categoryHref(category) {
    const params = new URLSearchParams(window.location.search);
    if (category) params.set("category", category);
    return `${window.location.pathname}?${params.toString()}`;
  }

  function load(days) {
    if (windowLabel) windowLabel.textContent = `Fenêtre: ${days} jours`;
    fetch(`/admin/api/ops-kpis?days=${days}`)
      .then((res) => res.json())
      .then((data) => {
        const elNew = document.getElementById("kpi-new");
        const elResolved = document.getElementById("kpi-resolved");
        const elAssign = document.getElementById("kpi-assign");
        const elResolve = document.getElementById("kpi-resolve");
        const elStale = document.getElementById("kpi-stale");

        if (elNew) elNew.textContent = data.new_requests ?? 0;
        if (elResolved) elResolved.textContent = data.resolved_requests ?? 0;
        if (elAssign) elAssign.textContent = formatHours(data.avg_owner_assign_hours ?? 0);
        if (elResolve) elResolve.textContent = formatHours(data.avg_resolve_hours ?? 0);

        const stale = Number(data.stale_over_7d ?? 0);
        if (elStale) elStale.textContent = stale;
        const staleCard = document.getElementById("kpi-stale-card");
        const ctaContainer = document.getElementById("hc-health-cta");
        if (staleCard) {
          staleCard.classList.remove(
            "hc-kpi-card--focus",
            "hc-kpi-card--warning",
            "hc-kpi-card--healthy",
          );
        }
        if (ctaContainer) {
          ctaContainer.innerHTML = "";
        }

        const healthEl = document.getElementById("hc-health-value");
        const healthWrapper = document.getElementById("hc-health");
        const healthSubEl = document.getElementById("hc-health-sub");
        if (healthEl && healthWrapper) {
          healthWrapper.classList.remove(
            "hc-health--stable",
            "hc-health--warning",
            "hc-health--danger",
          );
          const status = data.health && data.health.status;
          const sla = data.sla || {};
          const assignB = Number(sla.assign_breach_count || 0);
          const resolveB = Number(sla.resolve_breach_count || 0);
          let line = "Aucun dépassement SLA";
          if (resolveB > 0) {
            line = `SLA résolution dépassé : ${resolveB} dossiers`;
          } else if (assignB > 0) {
            line = `SLA assignation dépassé : ${assignB} dossiers`;
          }
          if (healthSubEl) healthSubEl.textContent = line;
          if (status === "stable") {
            healthEl.textContent = "Stable";
            healthWrapper.classList.add("hc-health--stable");
            if (staleCard) staleCard.classList.add("hc-kpi-card--healthy");
          } else if (status === "sous_tension") {
            healthEl.textContent = "Sous tension";
            healthWrapper.classList.add("hc-health--warning");
            if (staleCard) staleCard.classList.add("hc-kpi-card--warning");
          } else if (status === "critique") {
            healthEl.textContent = "Critique";
            healthWrapper.classList.add("hc-health--danger");
            if (staleCard) staleCard.classList.add("hc-kpi-card--focus");
            if (ctaContainer) {
              const link = document.createElement("a");
              link.href = "?risk=stale";
              link.className = "hc-health__cta";
              link.textContent = "Voir les dossiers en attente > 7j →";
              ctaContainer.appendChild(link);
            }
          } else {
            healthEl.textContent = "—";
          }
        }

        const categoryList = document.getElementById("kpi-category");
        if (!categoryList) return;

        categoryList.innerHTML = "";
        const rows = Array.isArray(data.by_category) ? data.by_category : [];
        if (!rows.length) {
          const li = document.createElement("li");
          li.textContent = "—";
          categoryList.appendChild(li);
          return;
        }

        rows.forEach((row) => {
          const li = document.createElement("li");
          const a = document.createElement("a");
          a.className = "hc-kpi-category-link";
          a.href = categoryHref(row.category || "");
          a.textContent = `${row.category}: ${row.count}`;
          li.appendChild(a);
          categoryList.appendChild(li);
        });
      })
      .catch((err) => {
        console.error("KPI fetch error:", err);
      });
  }

  const initialDays = select ? Number(select.value || 30) : Number(section.dataset.days || 30);
  load(initialDays);

  if (select) {
    select.addEventListener("change", function () {
      load(Number(select.value || 30));
    });
  }
});
