async function loadFunnel() {
  const days = document.getElementById("days").value;

  const res = await fetch("/admin/api/conversion-funnel?days=" + encodeURIComponent(days), {
    credentials: "same-origin"
  });

  const data = await res.json();

  const s = data.summary || {};
  document.getElementById("events").textContent = s.events ?? 0;
  document.getElementById("views").textContent = s.page_views ?? 0;
  document.getElementById("clicks").textContent = s.cta_clicks ?? 0;
  document.getElementById("v2c").textContent = (s.view_to_click ?? 0) + "%";
  document.getElementById("c2s").textContent = (s.click_to_submit ?? 0) + "%";

  const rows = (data.pages || []).map(row => `
    <tr>
      <td><strong>${row.page}</strong></td>
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
}

document.addEventListener("DOMContentLoaded", function () {
  document.getElementById("days").addEventListener("change", loadFunnel);
  loadFunnel();
});

