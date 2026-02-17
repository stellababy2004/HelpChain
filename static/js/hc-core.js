/* HelpChain Core UI Engine (Phase 5.1)
 * - window.hc csrf/post helpers
 * - shared actions: copyText, copyFromTarget, clickTarget, confirmSubmit
 * - delegated actions ([data-action])
 * - telemetry (.js-track)
 * - rowlink (.js-rowlink)
 * - a11y drawer state + focus trap
 * - dev cache/service-worker cleanup on localhost
 */
(function () {
  "use strict";

  window.hc = window.hc || {};
  window.hc.csrf = function () {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") || "" : "";
  };
  window.hc.post = async function (url, data) {
    return fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": window.hc.csrf(),
      },
      body: JSON.stringify(data || {}),
      credentials: "same-origin",
    });
  };

  window.copyText = async function (el) {
    var text = el && el.getAttribute ? el.getAttribute("data-copy") || "" : "";
    if (!text) return;

    try {
      await navigator.clipboard.writeText(text);
      if (el && el.classList) {
        el.classList.add("is-copied");
        setTimeout(function () {
          el.classList.remove("is-copied");
        }, 900);
      }
      return;
    } catch (_) {}

    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "absolute";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
      if (el && el.classList) {
        el.classList.add("is-copied");
        setTimeout(function () {
          el.classList.remove("is-copied");
        }, 900);
      }
    } catch (_) {}
    document.body.removeChild(ta);
  };

  window.copyFromTarget = function (el) {
    var selector = el && el.getAttribute ? el.getAttribute("data-target") || "" : "";
    var node = selector ? document.querySelector(selector) : null;
    var text = node ? node.innerText || node.textContent || "" : "";
    if (!text) return;
    var proxy = {
      getAttribute: function (k) {
        return k === "data-copy" ? text : null;
      },
      classList: el && el.classList ? el.classList : { add: function () {}, remove: function () {} },
    };
    return window.copyText(proxy);
  };

  window.clickTarget = function (el) {
    var selector = el && el.getAttribute ? el.getAttribute("data-target") || "" : "";
    var node = selector ? document.querySelector(selector) : null;
    if (node && typeof node.click === "function") node.click();
  };

  window.confirmSubmit = function (el) {
    var msg =
      (el && el.getAttribute && el.getAttribute("data-confirm")) || "Are you sure?";
    if (!confirm(msg)) return;

    var form = el && el.closest ? el.closest("form") : null;
    if (form) {
      form.submit();
      return;
    }

    var href =
      (el && el.getAttribute && el.getAttribute("data-href")) ||
      (el && el.getAttribute && el.getAttribute("href")) ||
      "";
    if (href) window.location.href = href;
  };

  (function () {
    var submitTracked = new WeakSet();

    function safeTrack(name, payload) {
      try {
        if (typeof window.hcTrack === "function") window.hcTrack(name, payload || {});
      } catch (_) {}
    }

    document.addEventListener("click", function (e) {
      var el = e.target.closest(".js-track");
      if (!el) return;

      var name = el.getAttribute("data-track");
      if (!name) return;

      var payload = { path: window.location.pathname };
      var reqId = el.getAttribute("data-request-id");
      var pct = el.getAttribute("data-pct");

      if (reqId !== null && reqId !== "") payload.request_id = Number(reqId);
      if (pct !== null && pct !== "") payload.pct = Number(pct);

      if (
        el.tagName === "BUTTON" &&
        (el.getAttribute("type") || "").toLowerCase() === "submit"
      ) {
        var formForButton = el.closest("form");
        if (formForButton) submitTracked.add(formForButton);
      }

      safeTrack(name, payload);
    });

    document.addEventListener(
      "submit",
      function (e) {
        var form = e.target.closest("form");
        if (!form) return;

        if (submitTracked.has(form)) {
          submitTracked.delete(form);
          return;
        }

        var el = form.querySelector(".js-track[data-track]");
        if (!el) return;

        var name = el.getAttribute("data-track");
        if (!name) return;

        var payload = { path: window.location.pathname };
        var reqId = el.getAttribute("data-request-id");
        var pct = el.getAttribute("data-pct");

        if (reqId !== null && reqId !== "") payload.request_id = Number(reqId);
        if (pct !== null && pct !== "") payload.pct = Number(pct);

        safeTrack(name, payload);
      },
      true,
    );
  })();

  (function () {
    function hcSendInternalEvent(eventName, props) {
      try {
        var payload = JSON.stringify({
          event: eventName,
          props: props || {},
        });

        if (navigator.sendBeacon) {
          var blob = new Blob([payload], { type: "application/json" });
          navigator.sendBeacon("/events", blob);
          return;
        }

        fetch("/events", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: payload,
          keepalive: true,
          credentials: "same-origin",
        }).catch(function () {});
      } catch (_) {}
    }

    function hcTrack(eventName, props) {
      try {
        if (typeof window.plausible === "function") {
          window.plausible(eventName, { props: props || {} });
        }
      } catch (_) {}

      hcSendInternalEvent(eventName, props);
    }

    document.addEventListener(
      "click",
      function (e) {
        var el = e.target.closest("[data-hc-event]");
        if (!el) return;

        var eventName = el.getAttribute("data-hc-event");
        if (!eventName) return;

        var props = {
          page: window.location.pathname,
          lang: document.documentElement.lang || "bg",
          cta: el.getAttribute("data-hc-cta") || undefined,
          intent: el.getAttribute("data-hc-intent") || undefined,
          category: el.getAttribute("data-hc-category") || undefined,
        };

        hcTrack(eventName, props);
      },
      true,
    );
  })();

  (function () {
    function safeCall(fnName, el) {
      try {
        var fn = window[fnName];
        if (typeof fn === "function") return fn(el);
      } catch (_) {}
      return undefined;
    }

    document.addEventListener("click", function (e) {
      var el = e.target.closest("[data-action]");
      if (!el) return;

      var action = el.getAttribute("data-action");
      if (!action) return;

      if (el.tagName === "A") e.preventDefault();
      safeCall(action, el);
    });

    document.addEventListener(
      "submit",
      function (e) {
        var form = e.target;
        if (!form) return;

        var action = form.getAttribute("data-action");
        if (!action) return;

        safeCall(action, form);
      },
      true,
    );
  })();

  (function () {
    document.addEventListener("click", function (e) {
      var row = e.target.closest(".js-rowlink");
      if (!row) return;

      if (
        e.target.closest(
          "a,button,input,select,textarea,label,form,[data-action],[data-bs-toggle]",
        )
      ) {
        return;
      }

      var href = row.getAttribute("data-href");
      if (href) window.location.href = href;
    });
  })();

  (function () {
    var STORAGE_KEY = "hc_a11y_v1";
    var btn = document.getElementById("hcA11yBtn");
    var drawer = document.getElementById("hcA11yDrawer");
    if (!btn || !drawer) return;

    var closeEls = drawer.querySelectorAll('[data-a11y-close="true"]');
    var contrast = document.getElementById("hcA11yContrast");
    var text = document.getElementById("hcA11yText");
    var motion = document.getElementById("hcA11yMotion");
    var simple = document.getElementById("hcA11ySimple");
    var reset = document.getElementById("hcA11yReset");
    var lastTrigger = null;

    function getFocusable(container) {
      return Array.from(
        container.querySelectorAll('a, button, input, select, textarea, [tabindex]:not([tabindex="-1"])'),
      ).filter(function (el) {
        return !el.hasAttribute("disabled") && el.getAttribute("aria-hidden") !== "true";
      });
    }

    function setHtmlAttr(name, value) {
      document.documentElement.setAttribute(name, value);
    }

    function loadState() {
      try {
        var raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return { contrast: false, text: false, motion: false, simple: false };
        var s = JSON.parse(raw);
        return {
          contrast: !!s.contrast,
          text: !!s.text,
          motion: !!s.motion,
          simple: !!s.simple,
        };
      } catch (_) {
        return { contrast: false, text: false, motion: false, simple: false };
      }
    }

    function saveState(state) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      } catch (_) {}
    }

    function applyState(state) {
      setHtmlAttr("data-a11y-contrast", state.contrast ? "high" : "normal");
      setHtmlAttr("data-a11y-text", state.text ? "large" : "normal");
      setHtmlAttr("data-a11y-motion", state.motion ? "reduced" : "normal");
      setHtmlAttr("data-a11y-simple", state.simple ? "on" : "off");
      if (contrast) contrast.checked = !!state.contrast;
      if (text) text.checked = !!state.text;
      if (motion) motion.checked = !!state.motion;
      if (simple) simple.checked = !!state.simple;
    }

    function currentState() {
      return {
        contrast: !!(contrast && contrast.checked),
        text: !!(text && text.checked),
        motion: !!(motion && motion.checked),
        simple: !!(simple && simple.checked),
      };
    }

    function openDrawer(trigger) {
      lastTrigger = trigger || btn;
      drawer.hidden = false;
      drawer.setAttribute("aria-hidden", "false");
      btn.setAttribute("aria-expanded", "true");
      document.body.classList.add("hc-modal-open");
      var focusable = getFocusable(drawer);
      if (focusable.length) {
        focusable[0].focus({ preventScroll: false });
      } else {
        drawer.focus({ preventScroll: false });
      }
    }

    function closeDrawer() {
      drawer.hidden = true;
      drawer.setAttribute("aria-hidden", "true");
      btn.setAttribute("aria-expanded", "false");
      document.body.classList.remove("hc-modal-open");
      if (lastTrigger) lastTrigger.focus({ preventScroll: false });
    }

    var hasExisting = !!localStorage.getItem(STORAGE_KEY);
    var initial = loadState();
    if (
      !hasExisting &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      initial.motion = true;
    }
    applyState(initial);

    drawer.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        e.preventDefault();
        closeDrawer();
        return;
      }
      if (e.key !== "Tab") return;

      var focusables = getFocusable(drawer);
      if (!focusables.length) return;
      var first = focusables[0];
      var last = focusables[focusables.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else if (document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    });

    btn.addEventListener("click", function () {
      openDrawer(btn);
    });
    closeEls.forEach(function (el) {
      el.addEventListener("click", closeDrawer);
    });

    [contrast, text, motion, simple].forEach(function (el) {
      if (!el) return;
      el.addEventListener("change", function () {
        var s = currentState();
        applyState(s);
        saveState(s);
      });
    });

    if (reset) {
      reset.addEventListener("click", function () {
        var s = { contrast: false, text: false, motion: false, simple: false };
        applyState(s);
        saveState(s);
      });
    }
  })();

  (function () {
    var host = window.location.hostname || "";
    if (host !== "127.0.0.1" && host !== "localhost") return;

    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.getRegistrations().then(function (regs) {
        regs.forEach(function (r) {
          r.unregister();
        });
      });
    }

    if (window.caches) {
      caches.keys().then(function (keys) {
        keys.forEach(function (k) {
          caches.delete(k);
        });
      });
    }
  })();

  // --- HC: data-hc-width applier (CSP-friendly) ---
  function hcClampPct(v) {
    var n = Number(v);
    if (!Number.isFinite(n)) return 0;
    return Math.max(0, Math.min(100, n));
  }

  function hcApplyWidths(root) {
    var scope = root || document;
    var nodes = scope.querySelectorAll("[data-hc-width]");
    nodes.forEach(function (el) {
      var v = el.getAttribute("data-hc-width");
      var pct = hcClampPct(v);
      el.style.width = pct + "%";
      if (
        el.parentElement &&
        el.parentElement.getAttribute("role") === "progressbar"
      ) {
        el.parentElement.setAttribute("aria-valuenow", String(Math.round(pct)));
      }
    });
  }

  function hcHydrateHeroKPIs() {
    var els = {
      helped: document.querySelector('[data-hc-kpi="helped"]'),
      volunteers: document.querySelector('[data-hc-kpi="volunteers"]'),
      countries: document.querySelector('[data-hc-kpi="countries"]'),
      closed: document.querySelector('[data-hc-kpi="closed"]'),
    };

    if (!els.helped || !els.volunteers || !els.countries) return;

    fetch("/api/pilot-kpi", { credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) return null;
        return r.json();
      })
      .then(function (data) {
        if (!data) return;

        var helped = data.helped;
        if (typeof helped === "undefined") helped = data.requests_helped;
        if (typeof helped === "undefined") helped = data.total_helped;

        var volunteers = data.active_volunteers;
        if (typeof volunteers === "undefined") volunteers = data.volunteers;

        var countries = data.countries;
        if (typeof countries === "undefined") countries = data.countries_served;

        var closed = data.closed;
        if (typeof closed === "undefined") closed = data.closed_requests;

        if (typeof helped !== "undefined") els.helped.textContent = String(helped);
        if (typeof volunteers !== "undefined") els.volunteers.textContent = String(volunteers);
        if (typeof countries !== "undefined") els.countries.textContent = String(countries);
        if (els.closed && typeof closed !== "undefined") els.closed.textContent = String(closed);

        if (typeof window.hcTrack === "function") {
          window.hcTrack("home_kpi_loaded", {
            helped: helped,
            active_volunteers: volunteers,
            countries: countries,
            closed: closed,
          });
        }
      })
      .catch(function () {});
  }

  document.addEventListener("DOMContentLoaded", function () {
    hcApplyWidths(document);
    if (document.body.classList.contains("hc-page-home")) {
      hcHydrateHeroKPIs();
    }
  });

  document.addEventListener("DOMContentLoaded", () => {
    const desc = document.getElementById("srDesc") || document.getElementById("sr-description");
    const status = document.getElementById("sr-desc-status");
    const email = document.getElementById("srEmail");
    const phone = document.getElementById("srPhone");
    const contactWarning = document.getElementById("srContactWarn");

    if (desc && status) {
      const updateDescStatus = () => {
        const value = desc.value.trim();
        if (value.length >= 20) {
          status.textContent = "✓ Sufficient information";
          status.classList.remove("hc-sr__status--hidden");
          status.classList.add("hc-sr__status--ok");
        } else {
          status.textContent = "";
          status.classList.remove("hc-sr__status--ok");
          status.classList.add("hc-sr__status--hidden");
        }
      };

      desc.addEventListener("input", updateDescStatus);
      updateDescStatus();
    }

    const updateContactState = () => {
      if (!contactWarning) return;
      const hasPhone = phone && phone.value.trim().length >= 6;
      const hasEmail = email && email.value.trim().length >= 3;
      const ok = hasPhone || hasEmail;

      contactWarning.classList.toggle("is-ok", ok);
      contactWarning.classList.toggle("is-warn", !ok);
    };

    if (phone) phone.addEventListener("input", updateContactState);
    if (email) email.addEventListener("input", updateContactState);
    updateContactState();
  });

  (function () {
    function initSubmitRequestAutoTitle() {
      const form = document.querySelector("form[data-hc-autotitle-template]");
      if (!form) return;

      const titleEl = document.getElementById("srTitle");
      const descEl = document.getElementById("srDesc");
      const catEl = document.getElementById("srCategory");
      const hintEl = document.getElementById("srTitleHint");

      if (!titleEl || !descEl) return;

      const tpl = form.getAttribute("data-hc-autotitle-template") || "Request: {snippet}";
      const tplCat =
        form.getAttribute("data-hc-autotitle-template-cat") || "{cat}: {snippet}";
      const hintOk = form.getAttribute("data-hc-hint-ok") || "Sufficient info";
      const hintMin = form.getAttribute("data-hc-hint-min") || "";
      let descTouched = false;

      const USER_EDITED_KEY = "hcTitleUserEdited";
      titleEl.addEventListener("input", () => {
        titleEl.dataset.hcUserEdited = "1";
        titleEl.dataset.hcAutoFilled = "0";
        titleEl.dataset.hcAutofill = "0";
        try {
          sessionStorage.setItem(USER_EDITED_KEY, "1");
        } catch (_) {}
      });

      try {
        if (sessionStorage.getItem(USER_EDITED_KEY) === "1") {
          titleEl.dataset.hcUserEdited = "1";
        }
      } catch (_) {}

      function setHint(state) {
        if (!hintEl) return;
        if (titleEl.dataset.hcUserEdited === "1") {
          hintEl.textContent = "";
          return;
        }
        if (state === "ok") {
          hintEl.textContent = `✓ ${hintOk}`;
          return;
        }
        if (state === "min") {
          hintEl.textContent = hintMin || "";
          const len = (descEl && descEl.value ? descEl.value : "").trim().length;
          if (!descTouched || len === 0) {
            hintEl.textContent = "";
          }
          return;
        }
        hintEl.textContent = "";
      }

      function cleanSnippet(text) {
        const t = (text || "").replace(/\s+/g, " ").trim();
        if (!t) return "";

        const first = t.split(/[\n\r]+/)[0].split(/[.!?]/)[0].trim();
        const base = (first || t).trim();
        const max = 64;
        if (base.length <= max) return base;
        return base.slice(0, max).replace(/\s+\S*$/, "") + "…";
      }

      function buildTitle() {
        const desc = descEl.value || "";
        const descTrim = desc.trim();
        if (!descTrim) {
          setHint("empty");
          return null;
        }
        const snippet = cleanSnippet(desc);
        if (snippet.length < 12) {
          setHint("min");
          return null;
        }

        const cat =
          catEl && catEl.value
            ? (catEl.options[catEl.selectedIndex] &&
                catEl.options[catEl.selectedIndex].textContent) ||
              ""
            : "";
        const category = (cat || "").trim();
        const template = category ? tplCat : tpl;
        return template
          .replace("{cat}", category)
          .replace("{snippet}", snippet)
          .trim();
      }

      function applyAutoTitle() {
        if (titleEl.dataset.hcUserEdited === "1") {
          setHint("min");
          return;
        }

        const isAuto =
          titleEl.dataset.hcAutoFilled === "1" || titleEl.dataset.hcAutofill === "1";
        const canAutoFill = !titleEl.value.trim() || isAuto;
        if (!canAutoFill) {
          setHint("ok");
          return;
        }

        const suggestion = buildTitle();
        if (!suggestion) return;

        titleEl.value = suggestion;
        titleEl.dataset.hcAutoFilled = "1";
        titleEl.dataset.hcAutofill = "1";
        setHint("ok");
      }

      descEl.addEventListener("input", () => {
        descTouched = true;
        applyAutoTitle();
      });
      if (catEl) catEl.addEventListener("change", applyAutoTitle);
      applyAutoTitle();

      document.addEventListener("click", (e) => {
        const a = e.target && e.target.closest ? e.target.closest("a") : null;
        if (!a) return;
        if (a.href && a.href.includes("/lang/")) {
          try {
            sessionStorage.removeItem(USER_EDITED_KEY);
          } catch (_) {}
        }
      });
    }

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", initSubmitRequestAutoTitle);
    } else {
      initSubmitRequestAutoTitle();
    }
  })();

  window.hcApplyWidths = hcApplyWidths;

})();
