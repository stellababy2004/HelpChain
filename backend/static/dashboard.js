// Динамично зареждане на таблицата със заявки (HelpRequest)
function updateRequestsTable() {
  const filters = getFilters();
  const params = new URLSearchParams();
  for (const key in filters) {
    if (filters[key]) params.append(key, filters[key]);
  }
  // TODO: добави и други филтри при нужда
  fetch("/admin/requests-table.json?" + params.toString())
    .then((r) => r.json())
    .then((data) => {
      const tbody = document.getElementById("requests-table-body");
      tbody.innerHTML = "";
      if (!data.items || data.items.length === 0) {
        tbody.innerHTML =
          '<tr><td colspan="8" class="text-center text-secondary">Няма заявки</td></tr>';
        return;
      }
      data.items.forEach((req) => {
        tbody.innerHTML += `
                  <tr>
                    <td>${req.id}</td>
                    <td>${req.title || ""}</td>
                    <td>${req.category || ""}</td>
                    <td>${req.city || ""}</td>
                    <td>${req.status || ""}</td>
                    <td>${req.priority || ""}</td>
                    <td>${req.created_at || ""}</td>
                    <td><!-- Действия --></td>
                  </tr>
                `;
      });
    })
    .catch(() => {
      const tbody = document.getElementById("requests-table-body");
      tbody.innerHTML =
        '<tr><td colspan="8" class="text-center text-danger">Грешка при зареждане на заявки</td></tr>';
    });
}

// Hook: обнови таблицата при drilldown, филтри или смяна на таб
function setupRequestsTableHooks() {
  // При смяна на drilldown или филтри
  window._origUpdateDashboard = window.updateDashboard;
  window.updateDashboard = function () {
    window._origUpdateDashboard();
    updateRequestsTable();
  };
  // При смяна на таб
  const requestsTab = document.getElementById("requests-tab");
  if (requestsTab) {
    requestsTab.addEventListener("click", function () {
      updateRequestsTable();
    });
  }
  // Автоматично зареждане при първоначално показване
  if (document.getElementById("requests-panel").classList.contains("active")) {
    updateRequestsTable();
  }
}

// Инициализация на hook-овете след DOMContentLoaded
window.addEventListener("DOMContentLoaded", function () {
  setupRequestsTableHooks();
});
// Динамично зареждане на опции за език и категория във филтрите на feedback панела
function populateFeedbackFilters() {
  // Зареждане на език и категория от backend API
  fetch("/admin/feedback-filters.json")
    .then((r) => r.json())
    .then((data) => {
      const languages = data.languages || [];
      const categories = data.categories || [];
      const langSel = document.getElementById("fb-filter-language");
      const catSel = document.getElementById("fb-filter-category");
      if (langSel) {
        langSel.innerHTML =
          '<option value="">Всички</option>' +
          languages.map((l) => `<option value="${l}">${l}</option>`).join("");
      }
      if (catSel) {
        catSel.innerHTML =
          '<option value="">Всички</option>' +
          categories.map((c) => `<option value="${c}">${c}</option>`).join("");
      }
    })
    .catch(() => {
      // fallback: статични стойности
      const languages = ["Български", "English", "Deutsch"];
      const categories = ["Обща", "Техническа", "Административна"];
      const langSel = document.getElementById("fb-filter-language");
      const catSel = document.getElementById("fb-filter-category");
      if (langSel) {
        langSel.innerHTML =
          '<option value="">Всички</option>' +
          languages.map((l) => `<option value="${l}">${l}</option>`).join("");
      }
      if (catSel) {
        catSel.innerHTML =
          '<option value="">Всички</option>' +
          categories.map((c) => `<option value="${c}">${c}</option>`).join("");
      }
    });
}
// Guard: дефинирай празна функция, ако липсва updateFeedbackPanel, за да няма ReferenceError
if (typeof updateFeedbackPanel !== "function") {
  window.updateFeedbackPanel = function () {};
}
// Guard: дефинирай празни функции ако липсват (за skeleton-и)
if (typeof showKpiSkeletons !== "function") {
  window.showKpiSkeletons = function (show) {
    const ids = [
      "kpi-today",
      "kpi-week",
      "kpi-month",
      "kpi-ai",
      "kpi-faq",
      "kpi-human",
      "kpi-latency",
      "kpi-success",
    ];
    ids.forEach((id) => {
      const el = document.getElementById(id);
      if (el) {
        const skel = el.querySelector(".skeleton");
        if (skel) skel.style.display = show ? "inline-block" : "none";
        el.style.visibility = show ? "hidden" : "visible";
      }
    });
  };
}
if (typeof showTableSkeleton !== "function") {
  window.showTableSkeleton = function (show) {
    document.querySelectorAll(".skeleton-table-row").forEach((row) => {
      row.style.display = show ? "table-row" : "none";
    });
    document.querySelectorAll(".data-table-row").forEach((row) => {
      row.style.display = show ? "none" : "table-row";
    });
  };
}
if (typeof showChartSkeletons !== "function") {
  window.showChartSkeletons = function (show = true) {
    const pairs = [
      ["donutChart-skel", "donutChart"],
      ["requestsChart-skel", "requestsChart"],
      ["barChart-skel", "barChart"],
    ];
    pairs.forEach(([skel, chart]) => {
      const skelEl = document.getElementById(skel);
      const chartEl = document.getElementById(chart);
      if (skelEl) skelEl.style.display = show ? "block" : "none";
      if (chartEl) chartEl.style.display = show ? "none" : "block";
    });
  };
}

// Drilldown state
let drilldown = { type: null, value: null };

function setupDrilldownCharts() {
  // Пример: barChart по категории (ако има)
  if (barChart && barChart.options) {
    barChart.options.onClick = function (evt, elements) {
      if (elements && elements.length) {
        const idx = elements[0].index;
        const label = barChart.data.labels[idx];
        applyDrilldown("category", label);
      }
    };
    barChart.update();
  }
  // Пример: donutChart по канал
  if (donutChart && donutChart.options) {
    donutChart.options.onClick = function (evt, elements) {
      if (elements && elements.length) {
        const idx = elements[0].index;
        const label = donutChart.data.labels[idx];
        applyDrilldown("channel", label);
      }
    };
    donutChart.update();
  }
  // Пример: requestsChart по час (може да се разшири)
  if (window.requestsChart && window.requestsChart.options) {
    window.requestsChart.options.onClick = function (evt, elements) {
      if (elements && elements.length) {
        const idx = elements[0].index;
        const label = window.requestsChart.data.labels[idx];
        applyDrilldown("hour", label);
      }
    };
    window.requestsChart.update();
  }
}

function applyDrilldown(type, value) {
  drilldown.type = type;
  drilldown.value = value;
  updateDashboard();
  showDrilldownBreadcrumb();
}

function resetDrilldown() {
  drilldown.type = null;
  drilldown.value = null;
  updateDashboard();
  showDrilldownBreadcrumb();
}

function showDrilldownBreadcrumb() {
  let el = document.getElementById("drilldown-breadcrumb");
  if (!el) {
    el = document.createElement("div");
    el.id = "drilldown-breadcrumb";
    el.className = "mb-2";
    const container =
      document.querySelector(".dashboard-header") || document.body;
    container.insertBefore(el, container.firstChild);
  }
  if (drilldown.type && drilldown.value) {
    el.innerHTML = `<span class="badge bg-info">Филтър: ${drilldown.type} = ${drilldown.value}</span> <button class="btn btn-sm btn-outline-secondary ms-2" onclick="resetDrilldown()">Изчисти</button>`;
    el.style.display = "block";
  } else {
    el.innerHTML = "";
    el.style.display = "none";
  }
}
// HelpChain AI Dashboard - външен JS за CSP
// Всички функции и логика, изнесени от шаблона

let donutChart, barChart;
let fbFiltersEl;

function getFilters() {
  const filters = {
    date_from: document.getElementById("filter-date-from")?.value || "",
    date_to: document.getElementById("filter-date-to")?.value || "",
    channel: document.getElementById("filter-channel")?.value || "",
    language: document.getElementById("filter-language")?.value || "",
    status: document.getElementById("filter-status")?.value || "",
  };
  // Добави drilldown филтър ако е активен
  if (drilldown.type && drilldown.value) {
    filters[drilldown.type] = drilldown.value;
  }
  return filters;
}

function updateDashboard() {
  const filters = getFilters();
  const params = new URLSearchParams();
  for (const key in filters) {
    if (filters[key]) params.append(key, filters[key]);
  }
  fetch("/admin/ai-stats.json?" + params.toString())
    .then((r) => r.json())
    .then((data) => {
      document.getElementById("kpi-today").textContent = data.requests_today;
      document.getElementById("kpi-week").textContent = data.requests_week;
      document.getElementById("kpi-month").textContent = data.requests_month;
      document.getElementById("kpi-ai").textContent = data.percent_ai + "%";
      document.getElementById("kpi-faq").textContent = data.percent_faq + "%";
      document.getElementById("kpi-human").textContent =
        data.percent_human + "%";
      document.getElementById("kpi-latency").textContent = data.avg_latency;
      document.getElementById("kpi-success").textContent =
        data.success_rate + "%";
      let status = data.status;
      let statusEl = document.getElementById("ai-status");
      if (status === "online")
        statusEl.innerHTML = '<span class="status-online">Online</span>';
      else if (status === "degraded")
        statusEl.innerHTML = '<span class="status-degraded">Degraded</span>';
      else statusEl.innerHTML = '<span class="status-offline">Offline</span>';
      if (window.requestsChart) {
        window.requestsChart.data.labels = data.chart.labels;
        window.requestsChart.data.datasets[0].data = data.chart.data;
        window.requestsChart.update();
      }
      if (donutChart) {
        donutChart.data.datasets[0].data = [
          data.percent_faq,
          data.percent_ai,
          data.percent_human,
        ];
        donutChart.update();
      }
      if (barChart && data.avg_by_channel) {
        barChart.data.datasets[0].data = [
          data.avg_by_channel.faq,
          data.avg_by_channel.ai,
          data.avg_by_channel.human,
        ];
        barChart.update();
      }
    });
}

window.addEventListener("DOMContentLoaded", function () {
  // Показване на skeleton-и при зареждане
  if (typeof showKpiSkeletons === "function") showKpiSkeletons(true);
  if (typeof showChartSkeletons === "function") showChartSkeletons(true);
  if (typeof showTableSkeleton === "function") showTableSkeleton(true);
  setTimeout(() => {
    if (typeof showKpiSkeletons === "function") showKpiSkeletons(false);
    if (typeof showChartSkeletons === "function") showChartSkeletons(false);
    if (typeof showTableSkeleton === "function") showTableSkeleton(false);
  }, 1200);

  // Инициализация на drilldown
  setupDrilldownCharts();

  // Попълни опциите за език и категория във feedback филтрите
  populateFeedbackFilters();

  fbFiltersEl = document.getElementById("fb-filters");
  let ctx = document.getElementById("requestsChart");
  if (ctx) {
    ctx = ctx.getContext("2d");
    window.requestsChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "Заявки (час)",
            data: [],
            borderColor: "#4ade80",
            backgroundColor: "rgba(74,222,128,0.1)",
            tension: 0.3,
          },
        ],
      },
      options: {
        plugins: { legend: { labels: { color: "#fff" } } },
        scales: {
          x: { ticks: { color: "#b0b8c1" } },
          y: { ticks: { color: "#b0b8c1" } },
        },
      },
    });
  }
  let donutCtx = document.getElementById("donutChart");
  if (donutCtx) {
    donutCtx = donutCtx.getContext("2d");
    donutChart = new Chart(donutCtx, {
      type: "doughnut",
      data: {
        labels: ["FAQ", "AI", "Human"],
        datasets: [
          {
            data: [0, 0, 0],
            backgroundColor: ["#60a5fa", "#4ade80", "#facc15"],
            borderWidth: 1,
          },
        ],
      },
      options: {
        plugins: { legend: { labels: { color: "#fff" } } },
      },
    });
  }
  let barCtx = document.getElementById("barChart");
  if (barCtx) {
    barCtx = barCtx.getContext("2d");
    barChart = new Chart(barCtx, {
      type: "bar",
      data: {
        labels: ["FAQ", "AI", "Human"],
        datasets: [
          {
            label: "Средно време (ms)",
            data: [0, 0, 0],
            backgroundColor: ["#60a5fa", "#4ade80", "#facc15"],
          },
        ],
      },
      options: {
        plugins: { legend: { labels: { color: "#fff" } } },
        scales: {
          x: { ticks: { color: "#b0b8c1" } },
          y: { ticks: { color: "#b0b8c1" } },
        },
      },
    });
  }
  updateDashboard();
  setInterval(updateDashboard, 10000);
  const filtersForm = document.getElementById("filters-form");
  if (filtersForm) {
    filtersForm.addEventListener("change", function () {
      updateDashboard();
    });
  }
  if (typeof updateFeedbackPanel === "function") {
    updateFeedbackPanel();
    setInterval(updateFeedbackPanel, 10000);
  }
  if (fbFiltersEl) {
    fbFiltersEl.addEventListener("change", updateFeedbackPanel);
  }
});
