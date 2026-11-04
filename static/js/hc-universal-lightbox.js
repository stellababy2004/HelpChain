(function () {
  "use strict";

  function init() {
    var images = Array.prototype.slice.call(document.querySelectorAll("[data-hc-lightbox]"));
    var triggers = Array.prototype.slice.call(document.querySelectorAll("[data-hc-lightbox-open]"));
    if (!images.length && !triggers.length) return;

    var dialog = document.createElement("dialog");
    dialog.className = "hc-universal-lightbox";
    dialog.setAttribute("data-hc-universal-lightbox", "true");
    dialog.setAttribute("aria-labelledby", "hc-universal-lightbox-title");
    dialog.innerHTML =
      '<div class="hc-universal-lightbox__head">' +
      '<h2 class="hc-universal-lightbox__title" id="hc-universal-lightbox-title"></h2>' +
      '<button type="button" class="hc-universal-lightbox__close" aria-label="Fermer l’image agrandie">&times;</button>' +
      '</div>' +
      '<div class="hc-universal-lightbox__body">' +
      '<img class="hc-universal-lightbox__image" alt="">' +
      '<p class="hc-universal-lightbox__caption" aria-live="polite"></p>' +
      '</div>';
    document.body.appendChild(dialog);

    var closeButton = dialog.querySelector(".hc-universal-lightbox__close");
    var body = dialog.querySelector(".hc-universal-lightbox__body");
    var image = dialog.querySelector(".hc-universal-lightbox__image");
    var caption = dialog.querySelector(".hc-universal-lightbox__caption");
    var lastFocused = null;
    var previousOverflow = "";
    var scale = 1;
    var offsetX = 0;
    var offsetY = 0;
    var pointers = new Map();
    var pinchDistance = 0;
    var pinchScale = 1;

    function applyTransform() {
      image.style.transform = "translate(" + offsetX + "px, " + offsetY + "px) scale(" + scale + ")";
    }

    function resetTransform() {
      scale = 1;
      offsetX = 0;
      offsetY = 0;
      pointers.clear();
      pinchDistance = 0;
      pinchScale = 1;
      applyTransform();
    }

    function open(source) {
      lastFocused = document.activeElement;
      var sourceAlt = source.getAttribute("alt") || "Image agrandie";
      image.src = source.currentSrc || source.src;
      image.alt = sourceAlt;
      dialog.querySelector(".hc-universal-lightbox__title").textContent =
        source.getAttribute("data-hc-lightbox-title") || sourceAlt;
      caption.textContent = source.getAttribute("data-hc-lightbox-caption") || "";
      resetTransform();
      previousOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
      closeButton.focus();
    }

    function close() {
      if (typeof dialog.close === "function") dialog.close();
      else dialog.removeAttribute("open");
    }

    images.forEach(function (source) {
      if (!source.hasAttribute("tabindex")) source.setAttribute("tabindex", "0");
      if (!source.hasAttribute("role")) source.setAttribute("role", "button");
      source.addEventListener("click", function () { open(source); });
      source.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          open(source);
        }
      });
    });

    triggers.forEach(function (trigger) {
      trigger.addEventListener("click", function () {
        var target = document.querySelector(trigger.getAttribute("data-hc-lightbox-target"));
        if (target) open(target);
      });
    });

    closeButton.addEventListener("click", close);
    dialog.addEventListener("click", function (event) {
      if (event.target === dialog) close();
    });
    dialog.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
      }
    });
    dialog.addEventListener("close", function () {
      document.body.style.overflow = previousOverflow;
      resetTransform();
      if (lastFocused && typeof lastFocused.focus === "function") lastFocused.focus();
    });

    body.addEventListener("wheel", function (event) {
      if (event.ctrlKey) {
        event.preventDefault();
        scale = Math.min(4, Math.max(1, scale - event.deltaY * 0.01));
        applyTransform();
      }
    }, { passive: false });

    body.addEventListener("pointerdown", function (event) {
      pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
      body.setPointerCapture(event.pointerId);
      if (pointers.size === 2) {
        var points = Array.from(pointers.values());
        pinchDistance = Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y);
        pinchScale = scale;
      }
    });
    body.addEventListener("pointermove", function (event) {
      if (!pointers.has(event.pointerId)) return;
      pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
      if (pointers.size === 2) {
        var points = Array.from(pointers.values());
        var distance = Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y);
        if (pinchDistance) scale = Math.min(4, Math.max(1, pinchScale * distance / pinchDistance));
      } else if (scale > 1) {
        offsetX += event.movementX;
        offsetY += event.movementY;
      }
      applyTransform();
    });
    ["pointerup", "pointercancel"].forEach(function (name) {
      body.addEventListener(name, function (event) { pointers.delete(event.pointerId); });
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
