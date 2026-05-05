(() => {
  const ROOT_ID = "hc-toast-root";
  const DEFAULT_DURATION = 3200;
  const TYPE_CLASS_MAP = {
    success: "alert-success",
    error: "alert-danger",
    info: "alert-primary",
  };

  function ensureRoot() {
    if (!document.body) {
      return null;
    }

    let root = document.getElementById(ROOT_ID);
    if (root) {
      return root;
    }

    root = document.createElement("div");
    root.id = ROOT_ID;
    root.className = "position-fixed bottom-0 end-0 p-3 d-flex flex-column gap-2";
    root.setAttribute("aria-live", "polite");
    root.setAttribute("aria-atomic", "true");
    root.setAttribute("aria-relevant", "additions");
    document.body.appendChild(root);
    return root;
  }

  function removeToast(node) {
    if (node && node.parentNode) {
      node.parentNode.removeChild(node);
    }
  }

  function showToast(message, type = "info", options = {}) {
    const root = ensureRoot();
    if (!root) {
      return { close() {} };
    }

    const toast = document.createElement("div");
    const toneClass = TYPE_CLASS_MAP[type] || TYPE_CLASS_MAP.info;
    const duration = Number(options.duration) > 0 ? Number(options.duration) : DEFAULT_DURATION;

    toast.className = `alert ${toneClass} shadow-sm border-0 mb-0`;
    toast.setAttribute("role", type === "error" ? "alert" : "status");

    const content = document.createElement("div");
    content.className = "d-flex align-items-start gap-2";

    const body = document.createElement("div");
    body.className = "flex-grow-1";
    body.textContent = String(message || "");

    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.className = "btn-close";
    closeButton.setAttribute("aria-label", "Fermer");

    content.appendChild(body);
    content.appendChild(closeButton);
    toast.appendChild(content);
    root.appendChild(toast);

    let timerId = window.setTimeout(() => {
      removeToast(toast);
    }, duration);

    function close() {
      if (timerId) {
        window.clearTimeout(timerId);
        timerId = 0;
      }
      removeToast(toast);
    }

    closeButton.addEventListener("click", close, { once: true });

    return { close };
  }

  const api = function hcToast(message, type = "info", options = {}) {
    return showToast(message, type, options);
  };

  api.show = showToast;
  api.success = function success(message, options = {}) {
    return showToast(message, "success", options);
  };
  api.error = function error(message, options = {}) {
    return showToast(message, "error", options);
  };
  api.info = function info(message, options = {}) {
    return showToast(message, "info", options);
  };

  window.hcToast = api;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ensureRoot, { once: true });
  } else {
    ensureRoot();
  }
})();
