function initPublicNav() {
  var navRoots = document.querySelectorAll("[data-hc-public-nav]");
  if (!navRoots.length) return;
  if (document.documentElement.hasAttribute("data-hc-public-nav-ready")) return;
  document.documentElement.setAttribute("data-hc-public-nav-ready", "true");

  var openRoot = null;

  function closeMega(root) {
    if (!root) return;
    var trigger = root.querySelector("[data-hc-mega-trigger]");
    var panel = root.querySelector("[data-hc-mega-panel]");
    root.classList.remove("is-open");
    if (trigger) trigger.setAttribute("aria-expanded", "false");
    if (panel) panel.hidden = true;
    if (openRoot === root) openRoot = null;
  }

  function openMega(root) {
    if (!root) return;
    if (openRoot && openRoot !== root) closeMega(openRoot);
    var trigger = root.querySelector("[data-hc-mega-trigger]");
    var panel = root.querySelector("[data-hc-mega-panel]");
    root.classList.add("is-open");
    if (trigger) trigger.setAttribute("aria-expanded", "true");
    if (panel) {
      panel.hidden = false;
      panel.removeAttribute("hidden");
    }
    openRoot = root;
  }

  function containsFocus(root) {
    return root && root.contains(document.activeElement);
  }

  navRoots.forEach(function (navRoot) {
    navRoot.querySelectorAll("[data-hc-mega]").forEach(function (megaRoot) {
      var trigger = megaRoot.querySelector("[data-hc-mega-trigger]");
      var panel = megaRoot.querySelector("[data-hc-mega-panel]");
      var closeTimer = null;
      if (!trigger || !panel) return;

      function cancelPendingClose() {
        if (!closeTimer) return;
        window.clearTimeout(closeTimer);
        closeTimer = null;
      }

      function scheduleClose() {
        cancelPendingClose();
        closeTimer = window.setTimeout(function () {
          closeMega(megaRoot);
        }, 140);
      }

      panel.hidden = true;
      panel.setAttribute("hidden", "hidden");
      trigger.setAttribute("aria-expanded", "false");

      trigger.addEventListener("keydown", function (event) {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        trigger.click();
      });

    });

    navRoot.addEventListener("click", function (event) {
      var trigger = event.target.closest("[data-hc-mega-trigger]");
      if (!trigger || !navRoot.contains(trigger)) return;
      var megaRoot = trigger.closest("[data-hc-mega]");
      if (!megaRoot) return;
      event.preventDefault();
      if (megaRoot.classList.contains("is-open")) closeMega(megaRoot);
      else openMega(megaRoot);
    });
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && openRoot) {
      var trigger = openRoot.querySelector("[data-hc-mega-trigger]");
      closeMega(openRoot);
      if (trigger) trigger.focus({ preventScroll: true });
    }
  });

  document.addEventListener("pointerdown", function (event) {
    if (openRoot && !openRoot.contains(event.target)) {
      closeMega(openRoot);
    }
  }, true);

  document.addEventListener("click", function (event) {
    if (openRoot && !openRoot.contains(event.target)) {
      closeMega(openRoot);
    }
  });

}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initPublicNav, { once: true });
} else {
  initPublicNav();
}
