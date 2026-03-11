(function () {
  "use strict";

  function onReady(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  onReady(function () {
    const form = document.querySelector(
      'form[action*="/submit_request"], form[action*="submit_request"]',
    );
    if (!form) return;

    const steps = Array.from(form.querySelectorAll(".hc-form-step[data-step]"));
    const indicators = Array.from(
      form.querySelectorAll(".hc-step-indicator [data-step-indicator]"),
    );
    if (!steps.length) return;

    function getStep(stepNumber) {
      return steps.find((el) => Number(el.dataset.step) === Number(stepNumber));
    }

    function updateReview() {
      const read = (selector) => form.querySelector(selector);
      const val = (selector) => (read(selector)?.value || "").trim();
      const categorySelect = read("#srCategory");
      const categoryText =
        categorySelect && categorySelect.selectedIndex >= 0
          ? categorySelect.options[categorySelect.selectedIndex].textContent.trim()
          : "";

      const model = {
        name: val("#srName"),
        email: val("#srEmail"),
        phone: val("#srPhone"),
        category: categoryText && categoryText !== "Choisir…" ? categoryText : "",
        title: val("#srTitle"),
        description: val("#srDesc"),
      };

      Object.keys(model).forEach((key) => {
        const node = form.querySelector(`[data-review="${key}"]`);
        if (!node) return;
        node.textContent = model[key] || "—";
      });
    }

    function setActiveStep(stepNumber, options) {
      const opts = options || {};
      const step = Number(stepNumber);
      steps.forEach((el) => {
        const active = Number(el.dataset.step) === step;
        el.classList.toggle("active", active);
        el.setAttribute("aria-hidden", active ? "false" : "true");
      });
      indicators.forEach((el) => {
        const active = Number(el.dataset.stepIndicator) === step;
        el.classList.toggle("is-active", active);
      });
      if (step === 3) updateReview();
      if (opts.focus !== false) {
        const firstField = getStep(step)?.querySelector(
          "input:not([type='hidden']), select, textarea, button",
        );
        if (firstField && typeof firstField.focus === "function") {
          firstField.focus({ preventScroll: false });
        }
      }
    }

    function validateStep(stepEl) {
      const controls = Array.from(
        stepEl.querySelectorAll("input, select, textarea"),
      ).filter((el) => {
        if (!el || el.disabled) return false;
        const type = (el.getAttribute("type") || "").toLowerCase();
        return type !== "hidden";
      });

      for (const control of controls) {
        if (!control.checkValidity()) {
          control.reportValidity();
          return false;
        }
      }
      return true;
    }

    form.querySelectorAll(".hc-step-next").forEach((btn) => {
      btn.addEventListener("click", () => {
        const currentStep = btn.closest(".hc-form-step");
        const nextStep = Number(btn.dataset.nextStep || 0);
        if (!currentStep || !nextStep) return;
        if (!validateStep(currentStep)) return;
        setActiveStep(nextStep);
      });
    });

    form.querySelectorAll(".hc-step-back").forEach((btn) => {
      btn.addEventListener("click", () => {
        const prevStep = Number(btn.dataset.prevStep || 0);
        if (!prevStep) return;
        setActiveStep(prevStep);
      });
    });

    const firstInvalid = form.querySelector(".is-invalid");

    if (firstInvalid) {
      const invalidStep = firstInvalid.closest(".hc-form-step[data-step]");
      if (invalidStep) {
        setActiveStep(Number(invalidStep.dataset.step), { focus: false });
      } else {
        setActiveStep(1, { focus: false });
      }
      firstInvalid.focus({ preventScroll: false });
      return;
    }

    setActiveStep(1, { focus: false });

    const summary = document.getElementById("form-error-summary");
    if (summary) summary.focus({ preventScroll: false });
  });

  // Sticky CTA: hide when the real submit button is visible.
  onReady(function () {
    const bar = document.querySelector(".hc-sticky-cta");
    if (!bar) return;

    const form = bar.closest("form") || document.querySelector("form");
    const realSubmit =
      form?.querySelector(
        'button[type="submit"]:not(.hc-sticky-cta__submit), input[type="submit"]:not(.hc-sticky-cta__submit)',
      ) || null;

    if (!realSubmit) return;

    if (!("IntersectionObserver" in window)) {
      bar.classList.add("is-visible");
      bar.classList.remove("is-hidden");
      return;
    }

    const barHeight = Math.ceil(bar.getBoundingClientRect().height || 0);
    const bottomMargin = Math.min(240, Math.max(80, barHeight + 16));

    const io = new IntersectionObserver(
      (entries) => {
        const isVisible = entries[0]?.isIntersecting === true;
        bar.classList.toggle("is-visible", !isVisible);
        bar.classList.toggle("is-hidden", isVisible);
      },
      {
        threshold: 0.15,
        rootMargin: `0px 0px -${bottomMargin}px 0px`,
      },
    );

    io.observe(realSubmit);
  });

  // Step 1.5.A: frontend-only anti-bot + single-submit (no enumeration).
  onReady(function () {
    const MIN_MS = 2500;
    const form = document.querySelector('form[data-hc-magic-link="request"]');
    if (!form) return;

    const GENERIC_OK =
      form.dataset.hcGenericOk ||
      "Si l'adresse est valide, vous recevrez un lien de connexion sous quelques minutes.";

    const started = Date.now();
    const startedAt = form.querySelector("#started_at");
    if (startedAt) startedAt.value = String(started);

    const msgBox = form.querySelector("[data-hc-form-msg]");
    let locked = false;

    function showGenericOk() {
      if (!msgBox) return;
      msgBox.style.display = "block";
      msgBox.textContent = GENERIC_OK;
      msgBox.classList.add("is-ok");
    }

    form.addEventListener("submit", (e) => {
      if (locked) {
        e.preventDefault();
        return;
      }

      const hp = form.querySelector("#hp_website");
      const t = form.querySelector("#started_at");
      const elapsedMs = Date.now() - (t ? parseInt(t.value || "0", 10) : started);

      if ((hp && (hp.value || "").trim().length > 0) || elapsedMs < MIN_MS) {
        e.preventDefault();
        showGenericOk();
        return;
      }

      locked = true;
      showGenericOk();
      const submits = Array.from(
        form.querySelectorAll('button[type="submit"], input[type="submit"]'),
      );
      submits.forEach((el) => {
        el.disabled = true;
        if (el.tagName === "BUTTON") {
          el.dataset.originalText = el.textContent;
          el.textContent = "Envoi…";
        }
      });
    });
  });

  // SR-1: fire once when the user starts interacting with the form
  onReady(function () {
    const form = document.querySelector(
      'form[action*="/submit_request"], form[action*="submit_request"]',
    );
    if (!form) return;

    let fired = false;
    const fire = () => {
      if (fired) return;
      fired = true;

      if (typeof window.hcTrack === "function") {
        window.hcTrack("sr_form_start", { cta: "submit_request_form" });
      } else if (typeof window.plausible === "function") {
        window.plausible("sr_form_start", { props: { cta: "submit_request_form" } });
      }
    };

    form.addEventListener("focusin", fire, { once: true });
    form.addEventListener("input", fire, { once: true });
  });

  // Lightweight category suggestions (frontend-only, backend-compatible).
  onReady(function () {
    const form = document.querySelector(
      'form[action*="/submit_request"], form[action*="submit_request"]',
    );
    if (!form) return;

    const categoryField = form.querySelector('[name="category"]');
    const pills = Array.from(form.querySelectorAll(".hc-suggestion-pill"));
    if (!categoryField || !pills.length) return;

    const isSelect = categoryField.tagName.toLowerCase() === "select";

    function normalize(value) {
      return (value || "")
        .toString()
        .trim()
        .toLowerCase();
    }

    const canonicalLabelByValue = {
      medical: "aide médicale",
      social: "soutien social",
      admin: "accès administratif",
      tech: "accès numérique",
    };

    let lastPickedLabel = "";
    let selectingFromPill = false;

    function syncPillsFromField() {
      const current = normalize(categoryField.value);
      let activeLabel = "";

      if (isSelect) {
        const hasLastPicked =
          !!lastPickedLabel &&
          pills.some(
            (pill) =>
              normalize(pill.dataset.suggestionLabel || "") === lastPickedLabel &&
              normalize(pill.dataset.suggestionValue || "") === current,
          );

        activeLabel = hasLastPicked
          ? lastPickedLabel
          : normalize(canonicalLabelByValue[current] || "");
      } else {
        activeLabel = normalize(categoryField.value);
      }

      pills.forEach((pill) => {
        const label = normalize(pill.dataset.suggestionLabel || "");
        const active = !!activeLabel && label === activeLabel;
        pill.classList.toggle("is-active", active);
        pill.setAttribute("aria-pressed", active ? "true" : "false");
      });
    }

    pills.forEach((pill) => {
      pill.addEventListener("click", () => {
        const targetValue = (pill.dataset.suggestionValue || "").trim();
        if (!targetValue) return;
        lastPickedLabel = normalize(pill.dataset.suggestionLabel || "");

        if (isSelect) {
          const match = Array.from(categoryField.options).find(
            (opt) => normalize(opt.value) === normalize(targetValue),
          );
          if (match) {
            selectingFromPill = true;
            categoryField.value = match.value;
            categoryField.dispatchEvent(new Event("change", { bubbles: true }));
            selectingFromPill = false;
          }
        } else {
          categoryField.value = pill.dataset.suggestionLabel || targetValue;
          categoryField.dispatchEvent(new Event("input", { bubbles: true }));
        }

        syncPillsFromField();
        categoryField.focus({ preventScroll: true });
      });
    });

    categoryField.addEventListener("change", () => {
      if (!selectingFromPill) lastPickedLabel = "";
      syncPillsFromField();
    });
    categoryField.addEventListener("input", () => {
      if (!selectingFromPill) lastPickedLabel = "";
      syncPillsFromField();
    });
    syncPillsFromField();
  });
})();
