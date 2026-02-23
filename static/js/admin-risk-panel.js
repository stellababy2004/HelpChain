(() => {
  const POLL_MS = 30000;
  const meta = document.getElementById("hcRiskMeta");
  const kStale = document.getElementById("kStale");
  const kUnassigned = document.getElementById("kUnassigned");
  const kNotSeen24 = document.getElementById("kNotSeen24");
  const kNotSeen48 = document.getElementById("kNotSeen48");
  const kNotSeen72 = document.getElementById("kNotSeen72");
  const kConv = document.getElementById("kConv");

  const kStaleSub = document.getElementById("kStaleSub");
  const kUnassignedSub = document.getElementById("kUnassignedSub");
  const kNotSeen24Sub = document.getElementById("kNotSeen24Sub");
  const kNotSeen48Sub = document.getElementById("kNotSeen48Sub");
  const kNotSeen72Sub = document.getElementById("kNotSeen72Sub");
  const kConvSub = document.getElementById("kConvSub");
  const kNotSeen24Warn = document.getElementById("kNotSeen24Warn");
  const kNotSeen48Warn = document.getElementById("kNotSeen48Warn");
  const kNotSeen72Warn = document.getElementById("kNotSeen72Warn");
  const kNotSeen24Icon = document.getElementById("kNotSeen24Icon");
  const kNotSeen48Icon = document.getElementById("kNotSeen48Icon");
  const kNotSeen72Icon = document.getElementById("kNotSeen72Icon");
  const cardNotSeen24 = document.getElementById("cardNotSeen24");
  const cardNotSeen48 = document.getElementById("cardNotSeen48");
  const cardNotSeen72 = document.getElementById("cardNotSeen72");
  const topList = document.getElementById("riskTopList");
  const slaHours = document.getElementById("hcSlaHours");

  async function load() {
    const params = new URLSearchParams(window.location.search || "");
    const sla = params.get("sla");
    const apiUrl = new URL("/admin/api/risk-kpis", window.location.origin);
    if (sla) apiUrl.searchParams.set("sla", sla);
    const res = await fetch(apiUrl.toString(), { credentials: "same-origin" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  }

  function fmt(v) {
    return v === null || v === undefined ? "-" : String(v);
  }

  function fmtDuration(sec) {
    if (sec === null || sec === undefined || Number.isNaN(Number(sec))) return "—";
    const s = Math.max(0, Math.round(Number(sec)));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    if (h <= 0) return `${m}m`;
    return `${h}h ${m}m`;
  }

  function fmtCompact(sec) {
    if (sec == null) return "—";
    const s = Math.max(0, Math.round(sec));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    if (h <= 0) return `${m}m`;
    return `${h}h ${m}m`;
  }

  function safeText(s) {
    return s == null ? "" : String(s);
  }

  function setText(selector, value) {
    const el = document.querySelector(selector);
    if (!el) return;
    el.textContent = value;
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
    if (slaHours) slaHours.textContent = fmt(d.sla_hours ?? 12);
    setText('[data-kpi="sla_hours"]', fmt(d.sla_hours ?? 12));
    setText('[data-kpi="sla_scope"]', String(d.sla_scope || "all_notified").toUpperCase());
    setText('[data-kpi="avg_first_seen"]', fmtDuration(d.avg_first_seen_seconds));
    setText('[data-kpi="avg_first_action"]', fmtDuration(d.avg_first_action_seconds));
    setText('[data-kpi="sla_under"]', Number(d.sla_under_12h_percent ?? 0).toFixed(1));
    setText('[data-kpi="sla_samples"]', fmt(d.sla_samples ?? 0));
    setText('[data-kpi="sla_outliers_limit"]', fmt(d.sla_outliers_limit ?? 5));
    const sampleCount = Number(d.sla_samples ?? 0);
    if (sampleCount > 0) {
      setText('[data-kpi="sla_hint"]', `Based on ${sampleCount} notified matches with an action.`);
    } else {
      setText('[data-kpi="sla_hint"]', "No SLA samples yet. We'll start measuring once volunteers receive notifications and respond.");
    }

    // Outliers (slowest first-action responses)
    const outList = document.getElementById("hcSlaOutliers");
    const outEmpty = document.getElementById("hcSlaOutliersEmpty");
    if (outList && outEmpty) {
      const out = Array.isArray(d.sla_outliers_action_7d) ? d.sla_outliers_action_7d : [];
      outList.innerHTML = "";
      if (!out.length) {
        outEmpty.hidden = false;
      } else {
        outEmpty.hidden = true;
        for (const row of out) {
          const reqId = row.request_id;
          const volId = row.volunteer_id;
          const delay = row.delay_seconds;

          const li = document.createElement("li");
          li.className = "hc-mini-list__item";

          const a = document.createElement("a");
          a.className = "hc-mini-list__link";
          a.href = `/admin/requests/${encodeURIComponent(reqId)}`;
          a.title = "Open request details";

          const left = document.createElement("div");
          left.className = "hc-mini-list__left";

          const title = document.createElement("div");
          title.className = "hc-mini-list__title";
          title.textContent = `#${safeText(reqId)}`;

          const sub = document.createElement("div");
          sub.className = "hc-mini-list__sub";
          sub.textContent = volId ? `Volunteer ${safeText(volId)}` : "Volunteer —";

          left.appendChild(title);
          left.appendChild(sub);

          const right = document.createElement("div");
          right.className = "hc-mini-list__right";

          const badge = document.createElement("span");
          badge.className = "hc-badge hc-badge--neutral";
          badge.textContent = fmtCompact(delay);

          right.appendChild(badge);
          a.appendChild(left);
          a.appendChild(right);
          li.appendChild(a);
          outList.appendChild(li);
        }
      }
    }

    kStale.textContent = fmt(d.stale_count);
    kUnassigned.textContent = fmt(d.unassigned_count);
    kNotSeen24.textContent = fmt(d.notseen24 ?? d.notified_not_seen);
    kNotSeen48.textContent = fmt(d.notseen48);
    kNotSeen72.textContent = fmt(d.notseen72);

    const conv =
      d.conversion_pct === null || d.conversion_pct === undefined
        ? "-"
        : `${d.conversion_pct}%`;
    kConv.textContent = conv;

    kStaleSub.textContent = `> ${d.stale_days} days, not closed`;
    kUnassignedSub.textContent = `> ${d.unassigned_days} days, unassigned`;
    if (kNotSeen24Sub) kNotSeen24Sub.textContent = "Volunteer attention risk";
    if (kNotSeen48Sub) kNotSeen48Sub.textContent = "Elevated attention risk";
    if (kNotSeen72Sub) kNotSeen72Sub.textContent = "Critical attention risk";
    kConvSub.textContent = `Last ${d.window_days} days - ${d.assigned_7d} assigned / ${d.can_help_7d} CAN_HELP`;
    const isFallback = Boolean(d.notified_source && d.notified_source !== "notified_at");
    renderMeta(d.generated_at, isFallback);

    const notSeen24 = Number(d.notseen24 ?? d.notified_not_seen ?? 0);
    const notSeen48 = Number(d.notseen48 || 0);
    const notSeen72 = Number(d.notseen72 || 0);
    if (cardNotSeen24) cardNotSeen24.classList.toggle("hc-riskcard--alert", notSeen24 > 0);
    if (cardNotSeen48) cardNotSeen48.classList.toggle("hc-riskcard--alert", notSeen48 > 0);
    if (cardNotSeen72) cardNotSeen72.classList.toggle("hc-riskcard--alert", notSeen72 > 0);
    if (kNotSeen24Warn) kNotSeen24Warn.hidden = !(notSeen24 > 0);
    if (kNotSeen48Warn) kNotSeen48Warn.hidden = !(notSeen48 > 0);
    if (kNotSeen72Warn) kNotSeen72Warn.hidden = !(notSeen72 > 0);
    if (kNotSeen24Icon) kNotSeen24Icon.hidden = !(notSeen24 > 0);
    if (kNotSeen48Icon) kNotSeen48Icon.hidden = !(notSeen48 > 0);
    if (kNotSeen72Icon) kNotSeen72Icon.hidden = !(notSeen72 > 0);
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
