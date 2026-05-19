(function () {
  function toArray(value) {
    return Array.prototype.slice.call(value || []);
  }

  function setText(el, text) {
    if (el) {
      el.textContent = text || "";
    }
  }

  function createStatus(root) {
    var existing = root.querySelector("[data-map-live-status]");
    if (existing) {
      return existing;
    }
    var status = document.createElement("div");
    status.className = "hc-map-live-status";
    status.setAttribute("data-map-live-status", "true");
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    status.innerHTML =
      '<span class="hc-map-live-status__dot" aria-hidden="true"></span>' +
      '<span class="hc-map-live-status__label"></span>';
    root.appendChild(status);
    return status;
  }

  function create(root, options) {
    var settings = options || {};
    var status = createStatus(root);
    var label = status.querySelector(".hc-map-live-status__label");
    var stableTimer = null;
    var hideTimer = null;
    var targets = [];
    var skeletonSelectors = [
      ".hc-risk-map-kpi",
      ".hc-command-map-kpi",
      ".hc-kpi",
      ".hc-command-map-drawer",
      ".hc-map-command-panel",
      ".hc-map-overlay",
      ".hc-risk-map-contextbar",
      ".hc-risk-map-queue-note",
      ".hc-map-action-bar",
      ".hc-audience-detailCard",
      ".audience-radar-list",
      ".audience-opportunity-grid",
      ".audience-founder-queue",
      ".audience-forecast-card",
      ".audience-shortlist",
      ".audience-signal-list",
      ".audience-action-list"
    ];

    function collectTargets() {
      targets = [];
      skeletonSelectors.forEach(function (selector) {
        targets = targets.concat(toArray(root.querySelectorAll(selector)));
      });
      targets.forEach(function (node) {
        node.classList.add("hc-map-live-target", "hc-map-live-skeleton");
        node.setAttribute("data-live-refresh", "true");
      });
    }

    function clearTimers() {
      if (stableTimer) {
        window.clearTimeout(stableTimer);
        stableTimer = null;
      }
      if (hideTimer) {
        window.clearTimeout(hideTimer);
        hideTimer = null;
      }
    }

    function setState(state, text) {
      clearTimers();
      collectTargets();
      root.classList.remove("is-map-loading", "is-map-refreshing", "is-map-stable");
      root.classList.add("is-map-" + state);
      root.classList.toggle("is-map-transitioning", state === "loading" || state === "refreshing");
      status.setAttribute("data-state", state);
      setText(label, text);
    }

    function stable(text, delay) {
      clearTimers();
      collectTargets();
      stableTimer = window.setTimeout(function () {
        root.classList.remove("is-map-loading", "is-map-refreshing");
        root.classList.remove("is-map-transitioning");
        root.classList.add("is-map-stable");
        status.setAttribute("data-state", "stable");
        setText(label, text || settings.stableText || "LIVE");
        hideTimer = window.setTimeout(function () {
          root.classList.remove("is-map-stable");
        }, 1800);
      }, typeof delay === "number" ? delay : 140);
    }

    function refresh(text) {
      setState("refreshing", text || settings.refreshText || "Actualisation...");
    }

    function loading(text) {
      setState("loading", text || settings.loadingText || "Synchronisation...");
    }

    function transition(text, callback) {
      refresh(text);
      window.requestAnimationFrame(function () {
        if (typeof callback === "function") {
          callback();
        }
        stable(settings.stableText || "LIVE", 180);
      });
    }

    root.classList.add("is-map-loading");
    collectTargets();
    setText(label, settings.loadingText || "Synchronisation...");
    status.setAttribute("data-state", "loading");

    return {
      loading: loading,
      refresh: refresh,
      refreshing: refresh,
      stable: stable,
      transition: transition,
      collectTargets: collectTargets
    };
  }

  window.HCMapsLive = {
    create: create
  };
})();
