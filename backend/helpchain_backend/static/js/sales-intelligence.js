(() => {
  const body = document.getElementById("salesPriorityBody");
  const daysSelect = document.getElementById("days");

  if (!body) return;

  const esc = (value) => {
    const div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  };

  const badge = (value) => {
    const normalized = String(value || "unknown").toLowerCase();
    const labels = {
      hot: "HOT",
      warm: "WARM",
      engaged: "ENGAGED",
      low: "LOW",
      strong: "STRONG",
      good: "GOOD",
      possible: "POSSIBLE",
      unknown: "UNKNOWN",
      contact_now: "CONTACT NOW",
      high: "HIGH",
      medium: "MEDIUM",
    };
    return `<span class="hc-rev-tier hc-rev-tier--${normalized === "hot" || normalized === "contact_now" ? "hot" : normalized === "warm" || normalized === "high" ? "warm" : "cold"}">${esc(labels[normalized] || normalized.toUpperCase())}</span>`;
  };

  const actionLabel = (action) => ({
    contact_today: "Contact today",
    contact_soon: "Contact soon",
    nurture: "Nurture",
    monitor: "Monitor",
    wait_for_identification: "Not contactable",
  }[action] || action || "-");

  async function loadSalesIntelligence() {
    const days = daysSelect ? daysSelect.value : "30";
    body.innerHTML = '<tr><td colspan="6" class="text-muted">Chargement...</td></tr>';

    try {
      const response = await fetch(`/admin/api/visitor-intent?days=${encodeURIComponent(days)}`, {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      const visitors = Array.isArray(data.visitors) ? data.visitors : [];

      if (!visitors.length) {
        body.innerHTML = '<tr><td colspan="6" class="text-muted">Aucun signal commercial pour cette periode.</td></tr>';
        return;
      }

      body.innerHTML = visitors.map((visitor) => {
        const prospect = visitor.prospect || {};
        const fit = visitor.fit;
        const priority = visitor.priority || {};

        const identity = visitor.contactable
          ? `<strong>${esc(prospect.name || prospect.organization || "Prospect identifie")}</strong>
             <div class="text-muted small">${esc(prospect.organization || prospect.email || "")}</div>`
          : `<strong>Visiteur anonyme</strong>
             <div class="text-muted small">${esc(visitor.visitor_id)}</div>`;

        return `
          <tr>
            <td>${identity}</td>
            <td><strong>${esc(visitor.score)}</strong>/100<br>${badge(visitor.level)}</td>
            <td>${fit ? `<strong>${esc(fit.score)}</strong>/100<br>${badge(fit.level)}` : '<span class="text-muted">-</span>'}</td>
            <td><strong>${esc(priority.score)}</strong>/100<br>${badge(priority.level)}</td>
            <td>${visitor.contactable ? '<span class="badge text-bg-success">Contactable</span>' : '<span class="badge text-bg-secondary">Anonymous</span>'}</td>
            <td><strong>${esc(actionLabel(priority.next_best_action))}</strong></td>
          </tr>`;
      }).join("");
    } catch (error) {
      console.error("Sales Intelligence load failed", error);
      body.innerHTML = '<tr><td colspan="6" class="text-danger">Impossible de charger Sales Intelligence.</td></tr>';
    }
  }

  if (daysSelect) {
    daysSelect.addEventListener("change", loadSalesIntelligence);
  }

  loadSalesIntelligence();
})();
