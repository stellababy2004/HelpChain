// Volunteer join (Step 1): limit selectable skills to MAX_SKILLS (frontend-only).
(() => {
  const MAX_SKILLS = 5;

  function init() {
    const form = document.querySelector(".hc-vol-join form");
    const btn = document.getElementById("magicLinkBtn");
    const msg = document.getElementById("magicLinkMsg");

    const skillInputs = Array.from(
      document.querySelectorAll('input[name="skills"][type="checkbox"]')
    );

    function applyLimit(changed) {
      const checked = skillInputs.filter((i) => i.checked);

      // If the user tries to pick a 6th skill, immediately revert it.
      if (changed && changed.checked && checked.length > MAX_SKILLS) {
        changed.checked = false;
      }

      const checkedNow = skillInputs.filter((i) => i.checked).length;
      const capReached = checkedNow >= MAX_SKILLS;
      skillInputs.forEach((i) => {
        i.disabled = capReached && !i.checked;
      });
    }

    if (skillInputs.length) {
      skillInputs.forEach((input) => {
        input.addEventListener("change", () => applyLimit(input));
      });
      applyLimit(null);
    }

    // Step 1.5 (frontend-only, privacy-safe): simulate magic-link sending.
    if (form && btn && msg) {
      const btnText = btn.querySelector(".btn-text");
      const btnSpinner = btn.querySelector(".btn-spinner");
      let busy = false;

      form.addEventListener("submit", (e) => {
        // Do not perform a real POST yet; keep UX on-page and avoid account enumeration.
        e.preventDefault();
        if (busy) return;
        busy = true;

        btn.disabled = true;
        if (btnSpinner) btnSpinner.style.display = "inline-block";
        if (btnText) btnText.textContent = "Envoi…";

        const delayMs = 800 + Math.floor(Math.random() * 401); // 800..1200ms
        window.setTimeout(() => {
          msg.style.display = "block";
          msg.textContent =
            "Si cet e-mail existe, un lien de connexion vient d’être envoyé. Vérifiez votre boîte de réception (et vos spams).";
        }, delayMs);

        // Cooldown to prevent spam clicks.
        window.setTimeout(() => {
          btn.disabled = false;
          if (btnSpinner) btnSpinner.style.display = "none";
          if (btnText) btnText.textContent = "Recevoir mon lien d’accès";
          busy = false;
        }, 8000);
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
