(() => {
  const maxSkills = 5;
  const MIN_MS = 900;

  function init() {
    const form = document.querySelector('form[data-hc-magic-link="volunteer"]');
    const checkboxes = Array.from(
      document.querySelectorAll('input[name="skills"][type="checkbox"]')
    );
    const hint = document.getElementById("skills-hint");
    const btn = document.getElementById("magicLinkBtn");
    const msg = document.getElementById("magicLinkMsg");

    if (checkboxes.length && hint) {
      const selectedTemplate =
        hint.dataset.selectedTemplate || "({count}/{max}) skills selected";
      const maxTemplate =
        hint.dataset.maxTemplate || "Maximum {max} skills. You can adjust later.";
      const fmt = (tpl, vars) =>
        String(tpl).replace(/\{(\w+)\}/g, (_, k) =>
          Object.prototype.hasOwnProperty.call(vars, k) ? String(vars[k]) : ""
        );
      const update = () => {
        const checked = checkboxes.filter((c) => c.checked);
        hint.textContent = fmt(selectedTemplate, {
          count: checked.length,
          max: maxSkills,
        });
        hint.classList.remove("hc-error");
      };

      checkboxes.forEach((cb) => {
        cb.addEventListener("change", () => {
          const checked = checkboxes.filter((c) => c.checked);
          if (checked.length > maxSkills) {
            cb.checked = false;
            hint.textContent = fmt(maxTemplate, { max: maxSkills });
            hint.classList.add("hc-error");
          } else {
            update();
          }
        });
      });

      update();
    }

    if (!form || !btn) return;

    const btnText = btn.querySelector(".btn-text");
    const btnSpinner = btn.querySelector(".btn-spinner");
    const defaultBtnLabel = btnText ? btnText.textContent : "";
    const sendingBtnLabel = form.dataset.hcSendingLabel || "Sending…";

    let busy = false;
    const started = Date.now();
    const startedAt = form.querySelector("#started_at");
    if (startedAt) startedAt.value = String(started);

    function setSendingState(isSending) {
      btn.disabled = !!isSending;
      if (btnSpinner) btnSpinner.style.display = isSending ? "inline-block" : "none";
      if (btnText)
        btnText.textContent = isSending ? sendingBtnLabel : defaultBtnLabel;
    }

    form.addEventListener("submit", (e) => {
      const hp = form.querySelector("#hp_company_fax") || form.querySelector("#hp_website");
      if (hp) hp.value = "";
      const t = form.querySelector("#started_at");
      const elapsedMs =
        Date.now() - (t ? parseInt(t.value || "0", 10) : started);

      const GENERIC_OK =
        form.dataset.hcGenericOk ||
        "Si l'adresse est valide, vous recevrez un lien de connexion sous quelques minutes.";

      if (busy) {
        e.preventDefault();
        return;
      }
      busy = true;
      setSendingState(true);
      // Keep submission server-driven. Backend already applies honeypot/timing/rate-limit.
      if (msg && ((hp && (hp.value || "").trim().length > 0) || elapsedMs < MIN_MS)) {
        msg.style.display = "block";
        msg.textContent = GENERIC_OK;
        msg.classList.add("is-ok");
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
