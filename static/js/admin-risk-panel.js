(() => {
  const POLL_MS = 30000;
  const meta = document.getElementById("hcRiskMeta");
  const kStale = document.getElementById("kStale");
  const kUnassigned = document.getElementById("kUnassigned");
  const kNotSeen = document.getElementById("kNotSeen");
  const kConv = document.getElementById("kConv");

  const kStaleSub = document.getElementById("kStaleSub");
  const kUnassignedSub = document.getElementById("kUnassignedSub");
  const kNotSeenSub = document.getElementById("kNotSeenSub");
  const kConvSub = document.getElementById("kConvSub");
  const kNotSeenWarn = document.getElementById("kNotSeenWarn");
  const kNotSeenIcon = document.getElementById("kNotSeenIcon");
  const cardNotSeen = document.getElementById("cardNotSeen");
  const topList = document.getElementById("riskTopList");

  async function load() {
    const res = await fetch("/admin/api/risk-kpis", { credentials: "same-origin" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  }

  function fmt(v) {
    return v === null || v === undefined ? "-" : String(v);
  }

  function renderMeta(updatedAt, isFallback) {
    if (!meta) return;
    meta.innerHTML = "";

    const updated = document.createElement("span");
    updated.className = "text-muted";
    updated.textContent = `Updated: ${updatedAt || "--"}`;
    meta.appendChild(updated);

    const badge = document.createElement("span");
    badge.className = `hc-badge ${isFallback ? "hc-badge--neutral" : "hc-badge--ok"}`;
    badge.title = isFallback
      ? "Using fallback data source (DB unavailable or delayed)."
      : "Live data source.";
    badge.textContent = isFallback ? "DATA: FALLBACK" : "DATA: LIVE";
    meta.appendChild(badge);
  }

  function renderTopRisky(items) {
    if (!topList) return;
    topList.innerHTML = "";
    if (!Array.isArray(items) || items.length === 0) {
      const empty = document.createElement("li");
      empty.className = "hc-risklist__empty";
      empty.textContent = "No high-risk requests right now.";
      topList.appendChild(empty);
      return;
    }

    items.forEach((item) => {
      const li = document.createElement("li");
      li.className = "hc-riskitem";

      const link = document.createElement("a");
      link.className = "hc-riskitem__title";
      link.href = item.details_url || `/admin/requests/${item.id}`;
      link.textContent = `#${item.id} ${item.title || ""}`.trim();

      const metaRow = document.createElement("div");
      metaRow.className = "hc-riskitem__meta";
      const days = document.createElement("span");
      days.className = "hc-riskpill";
      days.textContent = `${item.days_open || 0}d open`;
      metaRow.appendChild(days);

      if (item.is_unassigned) {
        const unassigned = document.createElement("span");
        unassigned.className = "hc-riskpill hc-riskpill--warn";
        unassigned.textContent = "Unassigned";
        metaRow.appendChild(unassigned);
      }
      if ((item.not_seen_count || 0) > 0) {
        const notSeen = document.createElement("span");
        notSeen.className = "hc-riskpill hc-riskpill--danger";
        notSeen.textContent = `${item.not_seen_count} not seen`;
        metaRow.appendChild(notSeen);
      }

      li.appendChild(link);
      li.appendChild(metaRow);
      topList.appendChild(li);
    });
  }

  function render(d) {
    kStale.textContent = fmt(d.stale_count);
    kUnassigned.textContent = fmt(d.unassigned_count);
    kNotSeen.textContent = fmt(d.notified_not_seen);

    const conv =
      d.conversion_pct === null || d.conversion_pct === undefined
        ? "-"
        : `${d.conversion_pct}%`;
    kConv.textContent = conv;

    kStaleSub.textContent = `> ${d.stale_days} days, not closed`;
    kUnassignedSub.textContent = `> ${d.unassigned_days} days, unassigned`;
    if (kNotSeenSub) kNotSeenSub.textContent = "Volunteer attention risk";
    kConvSub.textContent = `Last ${d.window_days} days - ${d.assigned_7d} assigned / ${d.can_help_7d} CAN_HELP`;
    const isFallback = Boolean(d.notified_source && d.notified_source !== "notified_at");
    renderMeta(d.generated_at, isFallback);

    const notSeenCount = Number(d.notified_not_seen || 0);
    if (cardNotSeen) {
      cardNotSeen.classList.toggle("hc-riskcard--alert", notSeenCount > 0);
    }
    if (kNotSeenWarn) {
      kNotSeenWarn.hidden = !(notSeenCount > 0);
    }
    if (kNotSeenIcon) {
      kNotSeenIcon.hidden = !(notSeenCount > 0);
    }
    renderTopRisky(d.top_risky || []);
  }

  async function refresh() {
    try {
      const data = await load();
      render(data);
    } catch (_err) {
      renderMeta("Failed to load KPIs", true);
    }
  }

  refresh();
  setInterval(() => {
    if (document.visibilityState === "visible") {
      refresh();
    }
  }, POLL_MS);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      refresh();
    }
  });
})();
