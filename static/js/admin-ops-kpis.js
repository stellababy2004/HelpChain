(function () {
  function setText(sel, value) {
    var el = document.querySelector(sel);
    if (!el) return;
    el.textContent = value == null ? "—" : String(value);
  }

  function renderCategoryRows(items) {
    var tbody = document.getElementById("hcOpsByCategory");
    if (!tbody) return;
    tbody.innerHTML = "";
    if (!Array.isArray(items) || items.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="2" class="text-muted">No data.</td></tr>';
      return;
    }
    items.forEach(function (row) {
      var tr = document.createElement("tr");
      var tdC = document.createElement("td");
      var tdN = document.createElement("td");
      tdC.textContent = row.category || "—";
      tdN.textContent = String(row.count || 0);
      tdN.className = "text-end";
      tr.appendChild(tdC);
      tr.appendChild(tdN);
      tbody.appendChild(tr);
    });
  }

  function render(data) {
    setText('[data-kpi="new_requests"]', data.new_requests ?? 0);
    setText('[data-kpi="resolved_requests"]', data.resolved_requests ?? 0);
    setText(
      '[data-kpi="avg_owner_assign_hours"]',
      Number(data.avg_owner_assign_hours ?? 0).toFixed(2),
    );
    setText(
      '[data-kpi="avg_resolve_hours"]',
      Number(data.avg_resolve_hours ?? 0).toFixed(2),
    );
    setText('[data-kpi="stale_over_7d"]', data.stale_over_7d ?? 0);
    setText('[data-kpi="window_days"]', data.window_days ?? 30);
    renderCategoryRows(data.by_category || []);
  }

  function loadOpsKpis() {
    if (!document.getElementById("hcOpsKpiCards")) return;
    fetch("/admin/api/ops-kpis", { credentials: "same-origin" })
      .then(function (res) {
        if (!res.ok) throw new Error("ops-kpis request failed");
        return res.json();
      })
      .then(render)
      .catch(function () {
        renderCategoryRows([]);
      });
  }

  document.addEventListener("DOMContentLoaded", loadOpsKpis);
})();
