(() => {
  const root = document.querySelector('[data-hc-autosync="true"]');
  if (!root) return;

  const DEFAULT_INTERVAL_MS = 45000;
  const MIN_INTERVAL_MS = 30000;
  const RELOAD_THROTTLE_MS = 15000;
  const MARKER_KEY = "hc:autosync:last-reload";

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

  const isPaused = () =>
    document.hidden ||
    document.body.dataset.hcAutosyncPaused === "true" ||
    isEditableElement(document.activeElement) ||
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

  updateStatus();

  window.setInterval(() => {
    if (isPaused() || wasRecentlyReloaded()) return;
    updateStatus(`Synchronisation en cours... ${formatTime(new Date())}`);
    writeMarker();
    window.location.reload();
  }, intervalMs);
})();
