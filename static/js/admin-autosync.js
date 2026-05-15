(() => {
  const root = document.querySelector('[data-hc-autosync="true"]');
  if (!root) return;

  const DEFAULT_INTERVAL_MS = 45000;
  const MIN_INTERVAL_MS = 30000;
  const RELOAD_THROTTLE_MS = 15000;
  const MARKER_KEY = "hc:autosync:last-reload";
  const SCROLL_KEY = "hc:autosync:scroll";
  const INTERACTION_COOLDOWN_MS = 10000;
  const isAdminRequestsPage = window.location.pathname === "/admin/requests";
  let lastInteractionAt = Date.now();

  const configuredInterval = Number.parseInt(root.dataset.hcAutosyncInterval || "", 10);
  const intervalMs = Number.isFinite(configuredInterval)
    ? Math.max(configuredInterval, MIN_INTERVAL_MS)
    : DEFAULT_INTERVAL_MS;

  const isEditableElement = (element) => {
    if (!element) return false;
    if (element.isContentEditable) return true;
    return !!element.closest(
      "input, textarea, select, [contenteditable='true'], [contenteditable='']"
    );
  };

  const hasDirtyForm = () =>
    !!root.querySelector("form[data-hc-autosync-dirty='true']");

  const isModalOpen = () =>
    !!document.querySelector(
      ".modal.show, dialog[open], [role='dialog'][aria-modal='true']"
    );

  const isDropdownOpen = () =>
    !!document.querySelector(
      ".dropdown-menu.show, details[open], .hc-rowmenu[open], .hc-statusmenu[open]"
    );

  const isControlFocused = () =>
    !!document.activeElement?.closest?.(
      "button, a, summary, [role='button'], [data-hc-tab], .hc-request-summary-card, .hc-quickchip, .hc-rowmenu, .hc-statusmenu, .hc-requests-toolbar"
    );

  const wasRecentlyInteracting = () =>
    Date.now() - lastInteractionAt < INTERACTION_COOLDOWN_MS;

  const isPaused = () =>
    document.hidden ||
    document.body.dataset.hcAutosyncPaused === "true" ||
    isEditableElement(document.activeElement) ||
    (isAdminRequestsPage &&
      (isControlFocused() || isDropdownOpen() || wasRecentlyInteracting())) ||
    hasDirtyForm() ||
    isModalOpen();

  const formatTime = (date) =>
    new Intl.DateTimeFormat("fr-FR", {
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);

  const ensureStatus = () => {
    const existing = root.querySelector("[data-hc-autosync-status]");
    if (existing) return existing;

    const status = document.createElement("div");
    status.className = "hc-autosync-status";
    status.dataset.hcAutosyncStatus = "true";
    status.setAttribute("aria-live", "polite");
    root.insertBefore(status, root.firstElementChild || null);
    return status;
  };

  const updateStatus = (message) => {
    const status = ensureStatus();
    status.textContent = message || `Derni\u00e8re synchronisation : ${formatTime(new Date())}`;
  };

  const readMarker = () => {
    try {
      return JSON.parse(sessionStorage.getItem(MARKER_KEY) || "null");
    } catch (_error) {
      return null;
    }
  };

  const writeMarker = () => {
    try {
      sessionStorage.setItem(
        MARKER_KEY,
        JSON.stringify({
          path: window.location.pathname,
          at: Date.now(),
        })
      );
    } catch (_error) {
      // Storage can be unavailable in hardened browsers; autosync still works.
    }
  };

  const writeScrollMarker = () => {
    if (!isAdminRequestsPage) return;
    try {
      sessionStorage.setItem(
        SCROLL_KEY,
        JSON.stringify({
          path: window.location.pathname,
          search: window.location.search,
          x: window.scrollX || 0,
          y: window.scrollY || 0,
          at: Date.now(),
        })
      );
    } catch (_error) {
      // Optional scroll restoration should never block sync.
    }
  };

  const restoreScrollMarker = () => {
    if (!isAdminRequestsPage) return;
    try {
      const marker = JSON.parse(sessionStorage.getItem(SCROLL_KEY) || "null");
      if (
        !marker ||
        marker.path !== window.location.pathname ||
        marker.search !== window.location.search ||
        Date.now() - Number(marker.at || 0) > 120000
      ) {
        return;
      }
      sessionStorage.removeItem(SCROLL_KEY);
      window.setTimeout(() => {
        window.scrollTo(Number(marker.x || 0), Number(marker.y || 0));
      }, 0);
    } catch (_error) {
      // Ignore malformed storage values.
    }
  };

  const wasRecentlyReloaded = () => {
    const marker = readMarker();
    if (!marker || marker.path !== window.location.pathname) return false;
    return Date.now() - Number(marker.at || 0) < RELOAD_THROTTLE_MS;
  };

  const markDirty = (event) => {
    const form = event.target.closest("form");
    if (form) form.dataset.hcAutosyncDirty = "true";
  };

  root.querySelectorAll("form").forEach((form) => {
    form.addEventListener("input", markDirty, true);
    form.addEventListener("change", markDirty, true);
    form.addEventListener("submit", () => {
      delete form.dataset.hcAutosyncDirty;
    });
    form.addEventListener("reset", () => {
      delete form.dataset.hcAutosyncDirty;
    });
  });

  if (isAdminRequestsPage) {
    const noteInteraction = () => {
      lastInteractionAt = Date.now();
    };
    root.addEventListener(
      "pointerdown",
      (event) => {
        if (
          event.target.closest(
            "form, input, textarea, select, button, a, summary, [role='button'], [data-hc-tab], .hc-request-summary-card, .hc-quickchip, .hc-rowmenu, .hc-statusmenu, .hc-requests-toolbar"
          )
        ) {
          noteInteraction();
        }
      },
      true
    );
    root.addEventListener(
      "keydown",
      (event) => {
        if (
          event.target.closest(
            "form, input, textarea, select, button, a, summary, [role='button'], [data-hc-tab], .hc-request-summary-card, .hc-quickchip, .hc-rowmenu, .hc-statusmenu, .hc-requests-toolbar"
          )
        ) {
          noteInteraction();
        }
      },
      true
    );
    restoreScrollMarker();
  }

  updateStatus();

  window.setInterval(() => {
    if (isPaused() || wasRecentlyReloaded()) return;
    updateStatus(`Synchronisation en cours... ${formatTime(new Date())}`);
    writeMarker();
    writeScrollMarker();
    window.location.reload();
  }, intervalMs);
})();
