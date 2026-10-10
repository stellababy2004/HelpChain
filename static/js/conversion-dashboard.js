async function loadFunnel() {
  const days = document.getElementById("days").value;

  const res = await fetch(hcAnalyticsUrl("/admin/api/conversion-funnel?days=" + encodeURIComponent(days)), {
    credentials: "same-origin"
  });

  const data = await res.json();
  if (!res.ok) {
    document.getElementById("pagesBody").innerHTML =
      '<tr><td colspan="7">Analytics unavailable.</td></tr>';
    document.getElementById("acquisitionBody").innerHTML =
      '<tr><td colspan="7">Analytics unavailable.</td></tr>';
    return;
  }

  const s = data.summary || {};
  document.getElementById("events").textContent = s.events ?? 0;
  document.getElementById("views").textContent = s.page_views ?? 0;
  document.getElementById("clicks").textContent = s.cta_clicks ?? 0;
  document.getElementById("v2c").textContent = (s.view_to_click ?? 0) + "%";
  document.getElementById("c2s").textContent = (s.click_to_submit ?? 0) + "%";

  const rows = (data.pages || []).map(row => `
    <tr>
      <td><strong>${hcAnalyticsEscape(row.page)}</strong></td>
      <td>${row.views}</td>
      <td>${row.clicks}</td>
      <td>${row.submits}</td>
      <td>${row.view_to_click}%</td>
      <td>${row.click_to_submit}%</td>
      <td>${row.dropoff_after_click}</td>
    </tr>
  `).join("");

  document.getElementById("pagesBody").innerHTML =
    rows || '<tr><td colspan="7" class="text-muted">No conversion data.</td></tr>';

  const acquisitionRows = (data.acquisition || []).map(row => `
    <tr>
      <td><strong>${hcAnalyticsEscape(row.source)}</strong></td>
      <td>${hcAnalyticsEscape(row.medium)}</td>
      <td>${hcAnalyticsEscape(row.campaign)}</td>
      <td>${row.sessions ?? 0}</td>
      <td>${row.cta_clicks ?? 0}</td>
      <td>${row.form_submits ?? 0}</td>
      <td><strong>${row.conversion_rate ?? 0}%</strong></td>
    </tr>
  `).join("");

  document.getElementById("acquisitionBody").innerHTML =
    acquisitionRows ||
    '<tr><td colspan="7" class="text-muted">No acquisition data.</td></tr>';
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

