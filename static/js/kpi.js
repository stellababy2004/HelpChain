// static/js/kpi.js
(() => {
  const ENDPOINT = "/api/pilot-kpi";
  const TIMEOUT_MS = 6000;

  function $(sel, root = document) {
    return root.querySelector(sel);
  }

  function clampNumber(v) {
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  }

  function animateCount(el, to, duration = 700) {
    // Respect reduced motion
    const reduce =
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      el.textContent = String(to);
      return;
    }

    const from = clampNumber(el.textContent);
    const start = performance.now();
    const diff = to - from;

    function frame(now) {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
      const value = Math.round(from + diff * eased);
      el.textContent = String(value);
      if (t < 1) requestAnimationFrame(frame);
    }

    requestAnimationFrame(frame);
  }

  async function fetchWithTimeout(url, timeoutMs) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(url, {
        method: "GET",
        headers: { Accept: "application/json" },
        signal: controller.signal,
        credentials: "same-origin",
      });
      return res;
    } finally {
      clearTimeout(timer);
    }
  }

  async function hydrateKpis() {
    const kpiNodes = Array.from(document.querySelectorAll("[data-kpi]"));
    if (kpiNodes.length === 0) return; // nothing to do on this page

    try {
      const res = await fetchWithTimeout(ENDPOINT, TIMEOUT_MS);
      if (!res.ok) throw new Error(`KPI fetch failed: ${res.status}`);
      const data = await res.json();

      // Fill counters
      for (const el of kpiNodes) {
        const key = el.getAttribute("data-kpi");
        if (!key) continue;

        const value = clampNumber(data[key]);
        animateCount(el, value);
      }

      // Optional: status pill
      const pill = $(".kpi-status[data-kpi-status]");
      if (pill) {
        // You can define what should be shown. Default: "Live" if ok.
        pill.textContent = "Live";
        pill.setAttribute("data-kpi-status", "ok");
      }
    } catch (err) {
      // Soft-fail: keep 0s and mark pill as degraded (no console spam for users)
      const pill = $(".kpi-status[data-kpi-status]");
      if (pill) {
        pill.textContent = "Offline";
        pill.setAttribute("data-kpi-status", "degraded");
      }
      // Dev hint:
      console.warn("[kpi] hydration failed:", err);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", hydrateKpis);
  } else {
    hydrateKpis();
  }
})();
