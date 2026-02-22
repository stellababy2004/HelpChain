// --- Sticky CTA: hide when the real submit button is visible ---
(() => {
  const bar = document.querySelector(".hc-sticky-cta");
  if (!bar) return;

  // Exclude the sticky bar's own submit button.
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

  // Treat the bottom area occupied by the sticky bar as "not visible",
  // otherwise we may hide the bar while the real submit is still behind it.
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
})();

// --- Step 1.5.A: frontend-only anti-bot + single-submit (no enumeration) ---
(() => {
  const MIN_MS = 2500;

  function init() {
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
      const elapsedMs =
        Date.now() - (t ? parseInt(t.value || "0", 10) : started);

      // Bot signals: honeypot filled OR submitted too fast.
      if ((hp && (hp.value || "").trim().length > 0) || elapsedMs < MIN_MS) {
        e.preventDefault();
        showGenericOk();
        return;
      }

      locked = true;
      // Show the same neutral message even for normal submits (anti-enumeration UX).
      // The page will typically redirect quickly, but users still get immediate feedback.
      showGenericOk();
      const submits = Array.from(form.querySelectorAll('button[type="submit"], input[type="submit"]'));
      submits.forEach((el) => {
        el.disabled = true;
        if (el.tagName === "BUTTON") {
          el.dataset.originalText = el.textContent;
          el.textContent = "Envoi…";
        }
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
