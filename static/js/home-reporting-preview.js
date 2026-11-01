(function () {
  "use strict";

  function initReportingPreview() {
    var dialog = document.getElementById("hc-reporting-preview-dialog");
    var openButton = document.querySelector("[data-reporting-preview-open]");
    var closeButton = document.querySelector("[data-reporting-preview-close]");
    if (!dialog || !openButton || !closeButton || dialog.dataset.bound === "true") {
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

    openButton.addEventListener("click", openDialog);
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

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initReportingPreview, { once: true });
  } else {
    initReportingPreview();
  }
})();
