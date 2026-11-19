async function loadFunnel() {
  const days = document.getElementById("days").value;

  const res = await fetch(hcAnalyticsUrl("/admin/api/conversion-funnel?days=" + encodeURIComponent(days)), {
    credentials: "same-origin"
  });

  const data = await res.json();
  if (!res.ok) {
    document.getElementById("pagesBody").innerHTML =
      '<tr><td colspan="7" class="hc-conv-empty">Données indisponibles.</td></tr>';
    document.getElementById("acquisitionBody").innerHTML =
      '<tr><td colspan="7" class="hc-conv-empty">Données indisponibles.</td></tr>';
    return;
  }

  const s = data.summary || {};
  document.getElementById("events").textContent = displayCount(s.events);
  document.getElementById("views").textContent = displayCount(s.page_views);
  document.getElementById("clicks").textContent = displayCount(s.cta_clicks);
  document.getElementById("v2c").textContent = displayRate(s.view_to_click, s.page_views);
  document.getElementById("c2s").textContent = displayRate(s.click_to_submit, s.cta_clicks);

  const rows = (data.pages || []).map(row => `
    <tr>
      <td><strong>${hcAnalyticsEscape(row.page)}</strong></td>
      <td>${displayCount(row.views)}</td>
      <td>${displayCount(row.clicks)}</td>
      <td>${displayCount(row.submits)}</td>
      <td>${displayRate(row.view_to_click, row.views)}</td>
      <td>${displayRate(row.click_to_submit, row.clicks)}</td>
      <td>${displayCount(row.dropoff_after_click)}</td>
    </tr>
  `).join("");

  document.getElementById("pagesBody").innerHTML =
    rows || '<tr><td colspan="7" class="hc-conv-empty">Données insuffisantes pour analyser les conversions.</td></tr>';

  const acquisitionRows = (data.acquisition || []).map(row => `
    <tr>
      <td><strong>${hcAnalyticsEscape(row.source)}</strong></td>
      <td>${hcAnalyticsEscape(row.medium)}</td>
      <td>${hcAnalyticsEscape(row.campaign)}</td>
      <td>${displayCount(row.sessions)}</td>
      <td>${displayCount(row.cta_clicks)}</td>
      <td>${displayCount(row.form_submits)}</td>
      <td><strong>${displayRate(row.conversion_rate, row.sessions)}</strong></td>
    </tr>
  `).join("");

  document.getElementById("acquisitionBody").innerHTML =
    acquisitionRows ||
    '<tr><td colspan="7" class="hc-conv-empty">Données insuffisantes pour analyser l’acquisition.</td></tr>';
}

function displayCount(value) {
  return Number.isFinite(Number(value)) ? String(value) : "Données insuffisantes";
}

function displayRate(value, denominator) {
  if (!Number.isFinite(Number(value)) || !Number.isFinite(Number(denominator)) || Number(denominator) <= 0) {
    return "Données insuffisantes";
  }
  return String(value) + "%";
}

function hcAnalyticsUrl(path) {
  const url = new URL(path, window.location.origin);
  const scope = new URLSearchParams(window.location.search);
  for (const key of ["structure_id", "organization_id", "site_id", "tracking_id"]) {
    for (const value of scope.getAll(key)) url.searchParams.append(key, value);
  }
  return url.pathname + url.search;
}

function hcAnalyticsEscape(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
}

document.addEventListener("DOMContentLoaded", function () {
  document.getElementById("days").addEventListener("change", loadFunnel);
  loadFunnel();
});

