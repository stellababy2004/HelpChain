(() => {
  const ENDPOINT = "/api/pilot-kpi";
  const TIMEOUT_MS = 3500;

  function setText(el, value) {
    if (!el) return;
    el.textContent = String(value ?? 0);
  }

  function hydrateKpis(data) {
    // Generic: any element with data-kpi="<key>"
    document.querySelectorAll("[data-kpi]").forEach((el) => {
      const key = el.getAttribute("data-kpi");
      if (!key) return;
      setText(el, data?.[key] ?? 0);
    });

    // Optional: status pill
    const pill = document.querySelector(".kpi-status");
    if (pill) {
      // Mark as live if endpoint answered
      pill.setAttribute("data-kpi-status", "live");
      pill.classList.add("is-live");
    }
  }

  async function fetchWithTimeout(url, ms) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), ms);
    try {
      const res = await fetch(url, {
        signal: ctrl.signal,
        headers: { Accept: "application/json" },
      });
      return res;
    } finally {
      clearTimeout(t);
    }
  }

  async function init() {
    try {
      const res = await fetchWithTimeout(ENDPOINT, TIMEOUT_MS);
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      hydrateKpis(data);
    } catch (e) {
      // Fail quietly: keep 0 fallbacks; just tag status
      const pill = document.querySelector(".kpi-status");
      if (pill) {
        pill.setAttribute("data-kpi-status", "offline");
        pill.classList.add("is-offline");
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
