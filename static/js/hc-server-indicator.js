(function () {
  const el = document.getElementById("hcServerIndicator");
  const text = document.getElementById("hcServerIndicatorText");
  if (!el || !text) return;

  const checkBtn = document.getElementById("hcHealthCheckBtn");
  const toast = document.getElementById("hc-toast");

  function showToast(message) {
    if (!toast) {
      try { window.alert(message); } catch (_) {}
      return;
    }
    toast.textContent = message;
    toast.classList.add("hc-toast--show");
    window.setTimeout(() => {
      toast.classList.remove("hc-toast--show");
    }, 1800);
  }

  async function ping() {
    try {
      const res = await fetch("/health", { cache: "no-store" });
      if (res.ok) {
        el.setAttribute("data-state", "up");
        el.title = "Server status: UP";
        text.textContent = "Server OK";
        return;
      }
    } catch (e) {}
    el.setAttribute("data-state", "down");
    el.title = "Server status: DOWN";
    text.textContent = "Server DOWN";
  }

  async function runHealthCheck() {
    if (checkBtn) {
      checkBtn.disabled = true;
      checkBtn.textContent = "Checking...";
    }
    try {
      const res = await fetch("/health", { cache: "no-store" });
      if (!res.ok) {
        el.setAttribute("data-state", "down");
        el.title = `Server status: DOWN (${res.status})`;
        text.textContent = "Server DOWN";
        showToast(`Health check failed (${res.status})`);
        return;
      }
      const data = await res.json();
      const marker = (data && data.hc_code_marker) ? ` (${data.hc_code_marker})` : "";
      el.setAttribute("data-state", "up");
      el.title = "Server status: UP";
      text.textContent = "Server OK";
      showToast(`Health OK${marker}`);
    } catch (e) {
      el.setAttribute("data-state", "down");
      el.title = "Server status: DOWN";
      text.textContent = "Server DOWN";
      showToast("Health check failed (network)");
    } finally {
      if (checkBtn) {
        checkBtn.disabled = false;
        checkBtn.textContent = "Health check";
      }
    }
  }

  ping();
  window.setInterval(ping, 7000);
  if (checkBtn) {
    checkBtn.addEventListener("click", runHealthCheck);
  }
})();
