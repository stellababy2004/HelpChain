(function () {
  "use strict";

  function initPreview(config) {
    var dialog = document.querySelector(config.dialog);
    var openButtons = document.querySelectorAll(config.openButton);
    var closeButton = document.querySelector(config.closeButton);
    if (!dialog || !openButtons.length || !closeButton || dialog.dataset.bound === "true") {
      return;
    }

    dialog.dataset.bound = "true";
    var lastFocused = null;

    function openDialog() {
      lastFocused = document.activeElement;
      if (typeof dialog.showModal === "function") {
        dialog.showModal();
      } else {
        dialog.setAttribute("open", "");
        dialog.classList.add("is-open");
      }
      closeButton.focus();
    }

    function closeDialog() {
      if (typeof dialog.close === "function") {
        dialog.close();
      } else {
        dialog.removeAttribute("open");
        dialog.classList.remove("is-open");
      }
    }

    openButtons.forEach(function (openButton) {
      openButton.addEventListener("click", openDialog);
      openButton.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openDialog();
        }
      });
    });
    closeButton.addEventListener("click", closeDialog);
    dialog.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeDialog();
      }
    });
    dialog.addEventListener("click", function (event) {
      if (event.target === dialog) {
        closeDialog();
      }
    });
    dialog.addEventListener("close", function () {
      if (lastFocused && typeof lastFocused.focus === "function") {
        lastFocused.focus();
      }
    });
  }

  function initPreviews() {
    initPreview({
      dialog: "[data-reporting-preview-dialog]",
      openButton: "[data-reporting-preview-open]",
      closeButton: "[data-reporting-preview-close]"
    });
    initPreview({
      dialog: "[data-hero-preview-dialog]",
      openButton: "[data-hero-preview-open]",
      closeButton: "[data-hero-preview-close]"
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPreviews, { once: true });
  } else {
    initPreviews();
  }
})();
