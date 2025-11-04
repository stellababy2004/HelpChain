/**
 * HelpChain User Feedback System
 * Version 1.0 - October 2025
 */

class HelpChainFeedback {
  constructor() {
    this.toastContainer = null;
    this.loadingOverlay = null;
    this.init();
  }

  init() {
    this.createToastContainer();
    this.createLoadingOverlay();
    this.bindEvents();
  }

  createToastContainer() {
    this.toastContainer = document.createElement("div");
    this.toastContainer.className = "toast-container";
    this.toastContainer.setAttribute("aria-live", "polite");
    this.toastContainer.setAttribute("aria-atomic", "false");
    document.body.appendChild(this.toastContainer);
  }

  createLoadingOverlay() {
    this.loadingOverlay = document.createElement("div");
    this.loadingOverlay.className = "loading-overlay";
    this.loadingOverlay.innerHTML = `
      <div class="loading-spinner"></div>
      <div class="loading-text">Моля, изчакайте...</div>
    `;
    this.loadingOverlay.setAttribute("aria-hidden", "true");
    document.body.appendChild(this.loadingOverlay);
  }

  bindEvents() {
    // Handle escape key for closing toasts
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        this.hideAllToasts();
      }
    });
  }

  /**
   * Show a toast notification
   * @param {string} message - The message to display
   * @param {string} type - Type of toast: 'success', 'error', 'warning', 'info'
   * @param {string} title - Optional title
   * @param {number} duration - Duration in milliseconds (0 = persistent)
   */
  showToast(message, type = "info", title = "", duration = 5000) {
    const toast = document.createElement("div");
    toast.className = `toast-notification ${type}`;
    toast.setAttribute("role", "alert");
    toast.setAttribute("aria-live", "assertive");

    const iconMap = {
      success: "fas fa-check-circle",
      error: "fas fa-exclamation-circle",
      warning: "fas fa-exclamation-triangle",
      info: "fas fa-info-circle",
    };

    toast.innerHTML = `
      <div class="toast-icon">
        <i class="${iconMap[type]}" aria-hidden="true"></i>
      </div>
      <div class="toast-content">
        ${title ? `<div class="toast-title">${title}</div>` : ""}
        <div class="toast-message">${message}</div>
      </div>
      <button class="toast-close" aria-label="Затвори нотификацията">
        <i class="fas fa-times" aria-hidden="true"></i>
      </button>
    `;

    // Add close button functionality
    const closeBtn = toast.querySelector(".toast-close");
    closeBtn.addEventListener("click", () => this.hideToast(toast));

    this.toastContainer.appendChild(toast);

    // Trigger animation
    setTimeout(() => toast.classList.add("show"), 10);

    // Auto-hide if duration is set
    if (duration > 0) {
      setTimeout(() => this.hideToast(toast), duration);
    }

    // Announce to screen readers
    this.announceToScreenReader(`${title ? title + ": " : ""}${message}`);

    return toast;
  }

  /**
   * Hide a specific toast
   * @param {HTMLElement} toast - The toast element to hide
   */
  hideToast(toast) {
    toast.classList.add("hide");
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 300);
  }

  /**
   * Hide all visible toasts
   */
  hideAllToasts() {
    const toasts = this.toastContainer.querySelectorAll(".toast-notification");
    toasts.forEach((toast) => this.hideToast(toast));
  }

  /**
   * Show loading overlay
   * @param {string} message - Optional loading message
   */
  showLoading(message = "Моля, изчакайте...") {
    const textElement = this.loadingOverlay.querySelector(".loading-text");
    if (textElement) {
      textElement.textContent = message;
    }

    this.loadingOverlay.classList.add("show");
    this.loadingOverlay.setAttribute("aria-hidden", "false");

    // Disable body scroll
    document.body.style.overflow = "hidden";
  }

  /**
   * Hide loading overlay
   */
  hideLoading() {
    this.loadingOverlay.classList.remove("show");
    this.loadingOverlay.setAttribute("aria-hidden", "true");

    // Re-enable body scroll
    document.body.style.overflow = "";
  }

  /**
   * Show loading state on a button
   * @param {HTMLElement} button - The button element
   * @param {string} loadingText - Optional loading text
   */
  setButtonLoading(button, loadingText = "") {
    if (!button) return;

    button.classList.add("btn-loading");
    button.disabled = true;

    if (loadingText) {
      button.setAttribute("data-original-text", button.textContent);
      button.textContent = loadingText;
    }

    button.setAttribute("aria-busy", "true");
  }

  /**
   * Remove loading state from a button
   * @param {HTMLElement} button - The button element
   */
  removeButtonLoading(button) {
    if (!button) return;

    button.classList.remove("btn-loading");
    button.disabled = false;

    const originalText = button.getAttribute("data-original-text");
    if (originalText) {
      button.textContent = originalText;
      button.removeAttribute("data-original-text");
    }

    button.setAttribute("aria-busy", "false");
  }

  /**
   * Show confirmation dialog
   * @param {string} title - Dialog title
   * @param {string} message - Dialog message
   * @param {string} confirmText - Confirm button text
   * @param {string} cancelText - Cancel button text
   * @param {string} type - Dialog type: 'danger', 'warning', 'info'
   * @returns {Promise<boolean>} - Resolves to true if confirmed, false if cancelled
   */
  showConfirmDialog(
    title,
    message,
    confirmText = "Потвърди",
    cancelText = "Отказ",
    type = "warning",
  ) {
    return new Promise((resolve) => {
      const dialog = document.createElement("div");
      dialog.className = "confirm-dialog";
      dialog.setAttribute("role", "dialog");
      dialog.setAttribute("aria-modal", "true");
      dialog.setAttribute("aria-labelledby", "confirm-title");
      dialog.setAttribute("aria-describedby", "confirm-message");

      const iconMap = {
        danger: "fas fa-exclamation-triangle text-danger",
        warning: "fas fa-exclamation-circle text-warning",
        info: "fas fa-info-circle text-info",
      };

      dialog.innerHTML = `
        <div class="confirm-dialog-content">
          <div class="confirm-dialog-icon">
            <i class="${iconMap[type]}" aria-hidden="true"></i>
          </div>
          <div id="confirm-title" class="confirm-dialog-title">${title}</div>
          <div id="confirm-message" class="confirm-dialog-message">${message}</div>
          <div class="confirm-dialog-actions">
            <button class="btn btn-secondary" data-action="cancel">${cancelText}</button>
            <button class="btn btn-${
              type === "danger" ? "danger" : "primary"
            }" data-action="confirm">${confirmText}</button>
          </div>
        </div>
      `;

      document.body.appendChild(dialog);

      // Focus management
      const focusableElements = dialog.querySelectorAll("button");
      const firstFocusable = focusableElements[0];
      const lastFocusable = focusableElements[focusableElements.length - 1];

      setTimeout(() => {
        dialog.classList.add("show");
        firstFocusable.focus();
      }, 10);

      // Handle button clicks
      dialog.addEventListener("click", (e) => {
        const action = e.target.getAttribute("data-action");
        if (action) {
          dialog.classList.remove("show");
          setTimeout(() => {
            document.body.removeChild(dialog);
            resolve(action === "confirm");
          }, 200);
        }
      });

      // Handle keyboard navigation
      dialog.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
          dialog.classList.remove("show");
          setTimeout(() => {
            document.body.removeChild(dialog);
            resolve(false);
          }, 200);
        } else if (e.key === "Tab") {
          if (e.shiftKey) {
            if (document.activeElement === firstFocusable) {
              e.preventDefault();
              lastFocusable.focus();
            }
          } else {
            if (document.activeElement === lastFocusable) {
              e.preventDefault();
              firstFocusable.focus();
            }
          }
        }
      });
    });
  }

  /**
   * Show progress bar
   * @param {HTMLElement} container - Container element
   * @param {number} progress - Progress percentage (0-100)
   * @param {string} text - Optional progress text
   */
  showProgress(container, progress, text = "") {
    let progressBar = container.querySelector(".progress-bar");
    if (!progressBar) {
      progressBar = document.createElement("div");
      progressBar.className = "progress-bar";
      progressBar.innerHTML = '<div class="progress-fill"></div>';
      container.appendChild(progressBar);
    }

    const fill = progressBar.querySelector(".progress-fill");
    fill.style.width = `${Math.min(100, Math.max(0, progress))}%`;

    let progressText = container.querySelector(".progress-text");
    if (!progressText && text) {
      progressText = document.createElement("div");
      progressText.className = "progress-text";
      container.appendChild(progressText);
    }

    if (progressText) {
      progressText.textContent = text;
    }

    // Update ARIA attributes
    progressBar.setAttribute("role", "progressbar");
    progressBar.setAttribute("aria-valuenow", progress);
    progressBar.setAttribute("aria-valuemin", "0");
    progressBar.setAttribute("aria-valuemax", "100");
  }

  /**
   * Show status indicator
   * @param {HTMLElement} element - Element to add status to
   * @param {string} status - Status type: 'success', 'error', 'warning', 'info', 'loading'
   * @param {string} message - Status message
   */
  showStatus(element, status, message) {
    // Remove existing status
    const existingStatus = element.querySelector(".status-indicator");
    if (existingStatus) {
      existingStatus.remove();
    }

    const statusDiv = document.createElement("div");
    statusDiv.className = `status-indicator ${status}`;
    statusDiv.innerHTML = `
      <span class="sr-only">Статус: </span>
      ${message}
    `;

    element.appendChild(statusDiv);

    // Auto-remove loading status after animation
    if (status === "loading") {
      setTimeout(() => {
        if (statusDiv.parentNode) {
          statusDiv.remove();
        }
      }, 3000);
    }
  }

  /**
   * Announce message to screen readers
   * @param {string} message - Message to announce
   */
  announceToScreenReader(message) {
    const announcement = document.createElement("div");
    announcement.setAttribute("aria-live", "assertive");
    announcement.setAttribute("aria-atomic", "true");
    announcement.className = "sr-only";
    announcement.textContent = message;

    document.body.appendChild(announcement);

    setTimeout(() => {
      document.body.removeChild(announcement);
    }, 1000);
  }

  /**
   * Show alert banner
   * @param {string} message - Alert message
   * @param {string} type - Alert type: 'success', 'error', 'warning', 'info'
   * @param {string} title - Optional alert title
   * @param {boolean} dismissible - Whether the alert can be dismissed
   */
  showAlert(message, type = "info", title = "", dismissible = true) {
    const alert = document.createElement("div");
    alert.className = `alert-banner ${type}`;
    alert.setAttribute("role", "alert");

    alert.innerHTML = `
      <div class="alert-banner-icon">
        <i class="fas fa-${
          type === "success"
            ? "check-circle"
            : type === "error"
            ? "exclamation-circle"
            : type === "warning"
            ? "exclamation-triangle"
            : "info-circle"
        }" aria-hidden="true"></i>
      </div>
      <div class="alert-banner-content">
        ${title ? `<div class="alert-banner-title">${title}</div>` : ""}
        <div class="alert-banner-message">${message}</div>
      </div>
      ${
        dismissible
          ? '<button class="alert-banner-close" aria-label="Затвори"><i class="fas fa-times" aria-hidden="true"></i></button>'
          : ""
      }
    `;

    // Insert at the top of the main content
    const main = document.querySelector("main") || document.body;
    main.insertBefore(alert, main.firstChild);

    // Add close functionality
    if (dismissible) {
      const closeBtn = alert.querySelector(".alert-banner-close");
      closeBtn.addEventListener("click", () => {
        alert.remove();
      });
    }

    // Auto-remove after 10 seconds for non-error alerts
    if (type !== "error" && dismissible) {
      setTimeout(() => {
        if (alert.parentNode) {
          alert.remove();
        }
      }, 10000);
    }
  }

  /**
   * Show skeleton loading
   * @param {HTMLElement} element - Element to show skeleton in
   * @param {string} type - Skeleton type: 'text', 'title', 'avatar', 'button'
   */
  showSkeleton(element, type = "text") {
    const skeleton = document.createElement("div");
    skeleton.className = `skeleton skeleton-${type}`;

    // Replace element content with skeleton
    const originalContent = element.innerHTML;
    element.setAttribute("data-original-content", originalContent);
    element.innerHTML = "";
    element.appendChild(skeleton);

    return {
      hide: () => {
        element.innerHTML = element.getAttribute("data-original-content") || "";
        element.removeAttribute("data-original-content");
      },
    };
  }
}

// Global instance
const helpChainFeedback = new HelpChainFeedback();

// Export for use in other scripts
window.HelpChainFeedback = HelpChainFeedback;
window.helpChainFeedback = helpChainFeedback;
