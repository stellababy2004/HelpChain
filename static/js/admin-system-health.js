(function () {
  const root = document.querySelector("[data-system-health-root]");
  if (!root) {
    return;
  }

  const endpoint = root.dataset.endpoint;
  const refreshMs = Number(root.dataset.refreshMs || 2000);
  const unavailableText = "Unavailable";

  const healthState = document.getElementById("hc-health-state");
  const healthUpdated = document.getElementById("hc-health-updated");
  const cpuEl = document.getElementById("cpu");
  const ramEl = document.getElementById("ram");
  const diskEl = document.getElementById("disk");
  const pythonEl = document.getElementById("python");
  const flaskEl = document.getElementById("flask");
  const apiEl = document.getElementById("api");

  let requestInFlight = false;

  function setBadge(el, text, tone) {
    if (!el) {
      return;
    }
    el.className = "badge " + tone + " hc-system-health-badge";
    el.innerText = text;
  }

  function isFiniteNumber(value) {
    return typeof value === "number" && Number.isFinite(value);
  }

  function formatPercent(value) {
    return isFiniteNumber(value) ? String(value) + "%" : unavailableText;
  }

  function formatRam(used, total) {
    if (!isFiniteNumber(used) || !isFiniteNumber(total)) {
      return unavailableText;
    }
    return String(used) + " / " + String(total) + " MB";
  }

  function formatCount(value) {
    return isFiniteNumber(value) ? String(value) : unavailableText;
  }

  function renderHeaderState(data) {
    const status = data && typeof data.status === "string" ? data.status : "error";
    const risk = data && typeof data.system_risk === "string" ? data.system_risk : "unknown";

    if (status === "ok") {
      if (risk === "high") {
        setBadge(healthState, "High risk", "text-bg-danger");
        return;
      }
      if (risk === "medium") {
        setBadge(healthState, "Watch", "text-bg-warning text-dark");
        return;
      }
      setBadge(healthState, "Healthy", "text-bg-success");
      return;
    }

    if (status === "degraded") {
      setBadge(healthState, "Partial data", "text-bg-warning text-dark");
      return;
    }

    setBadge(healthState, "Error", "text-bg-danger");
  }

  function renderFlaskState(data) {
    const status = data && typeof data.flask_status === "string" ? data.flask_status : "";
    if (status === "running" || data.flask_running === true) {
      setBadge(flaskEl, "ON", "text-bg-success");
      return;
    }
    if (status === "stopped" || data.flask_running === false) {
      setBadge(flaskEl, "OFF", "text-bg-danger");
      return;
    }
    setBadge(flaskEl, "UNKNOWN", "text-bg-warning text-dark");
  }

  function renderApiState(data) {
    const status = data && typeof data.api_status === "string" ? data.api_status : "";
    if (status === "online" || data.api_ok === true) {
      setBadge(apiEl, "ONLINE", "text-bg-success");
      return;
    }
    if (status === "degraded") {
      setBadge(apiEl, "DEGRADED", "text-bg-warning text-dark");
      return;
    }
    if (status === "error") {
      setBadge(apiEl, "ERROR", "text-bg-danger");
      return;
    }
    if (data.api_ok === false) {
      setBadge(apiEl, "OFFLINE", "text-bg-danger");
      return;
    }
    setBadge(apiEl, "UNKNOWN", "text-bg-warning text-dark");
  }

  function renderSnapshot(data) {
    const snapshot = data && typeof data === "object" ? data : { status: "error" };
    renderHeaderState(snapshot);
    cpuEl.innerText = formatPercent(snapshot.cpu);
    ramEl.innerText = formatRam(snapshot.ram_used, snapshot.ram_total);
    diskEl.innerText = formatPercent(snapshot.disk);
    pythonEl.innerText = formatCount(snapshot.python_procs);
    renderFlaskState(snapshot);
    renderApiState(snapshot);
    healthUpdated.innerText = snapshot.last_updated_at || unavailableText.toLowerCase();
  }

  async function readJson(response) {
    try {
      return await response.json();
    } catch (_) {
      return null;
    }
  }

  async function loadHealth() {
    if (requestInFlight || !endpoint) {
      return;
    }
    requestInFlight = true;

    try {
      const response = await fetch(endpoint, {
        credentials: "same-origin",
        cache: "no-store",
      });
      const data = await readJson(response);
      if (data) {
        renderSnapshot(data);
      } else {
        renderSnapshot({
          status: "error",
          api_status: "error",
          flask_status: "running",
        });
      }
    } catch (_) {
      renderSnapshot({ status: "error", api_status: "error" });
    } finally {
      requestInFlight = false;
    }
  }

  loadHealth();
  window.setInterval(loadHealth, refreshMs);
})();
