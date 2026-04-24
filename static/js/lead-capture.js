(function () {
  const path = window.location.pathname;
  const intentPages = ["/offre", "/deploiement", "/professionnels", "/collectivites"];
  const isIntentPage = intentPages.some((p) => path.startsWith(p));

  if (!isIntentPage) return;
  if (localStorage.getItem("hc_lead_capture_closed") === "1") return;

  function showCapture() {
    if (document.querySelector(".hc-lead-capture")) return;

    const box = document.createElement("div");
    box.className = "hc-lead-capture is-visible";
    box.innerHTML = `
      <button class="hc-lead-capture__close" type="button" aria-label="Fermer">×</button>

      <div class="hc-lead-capture__title">
        Voir comment HelpChain fonctionnerait dans votre structure ?
      </div>

      <div class="hc-lead-capture__text">
        En 15 minutes, nous vous montrons un cas concret adapté à votre organisation.
      </div>

      <input
        class="hc-lead-capture__input"
        id="hc-lead-email"
        type="email"
        placeholder="Email professionnel (ex: mairie, association, CCAS)"
        autocomplete="email"
      />

      <div style="font-size:13px;color:#64748b;margin-bottom:10px;">
        ✔ Réponse rapide sous 24h · ✔ Déploiement progressif · ✔ Cadre maîtrisé
      </div>

      <div style="font-size:13px;color:#dc2626;margin-bottom:10px;">
        ⚠ Déploiement pilote limité — créneaux en cours cette semaine
      </div>

      <div class="hc-lead-capture__actions">
        <button class="hc-lead-capture__primary" id="hc-lead-submit" type="button">
          Voir un exemple concret
        </button>
        <a class="hc-lead-capture__secondary" href="/deploiement">
          Voir le déploiement
        </a>
      </div>
    `;

    document.body.appendChild(box);

    box.querySelector(".hc-lead-capture__close").addEventListener("click", function () {
      localStorage.setItem("hc_lead_capture_closed", "1");
      box.remove();
    });

    box.querySelector("#hc-lead-submit").addEventListener("click", async function () {
      const emailInput = box.querySelector("#hc-lead-email");
      emailInput.value = emailInput.value.toLowerCase();

      const email = emailInput.value.trim();

      if (!email) {
        alert("Veuillez entrer un email professionnel.");
        emailInput.focus();
        return;
      }

      const submitButton = box.querySelector("#hc-lead-submit");
      submitButton.disabled = true;
      submitButton.textContent = "Envoi...";

      try {
        const response = await fetch("/api/lead-capture", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            email: email,
            page: window.location.pathname,
            intent: "high",
            source: "lead_capture_popup"
          })
        });

        if (!response.ok) {
          throw new Error("Lead capture failed: " + response.status);
        }

        localStorage.setItem("hc_lead_email", email);
        localStorage.setItem("hc_lead_capture_closed", "1");

        box.innerHTML = `
          <div class="hc-lead-capture__title">C’est fait.</div>

          <div class="hc-lead-capture__text">
            👉 Plus vous donnez de contexte, plus la démonstration sera pertinente.
          </div>

          <div class="hc-lead-capture__actions">
            <a class="hc-lead-capture__primary" href="/contact">
              Finaliser en 30 secondes
            </a>
          </div>
        `;

        console.log("HC_LEAD_CAPTURED", email);
      } catch (error) {
        console.error("HC_LEAD_CAPTURE_API_FAILED", error);

        submitButton.disabled = false;
        submitButton.textContent = "Voir un exemple concret";

        alert("Erreur temporaire. Vous pouvez finaliser votre demande via le formulaire de contact.");
      }
    });
  }

  setTimeout(showCapture, 8000);

  let maxScroll = 0;

  window.addEventListener("scroll", function () {
    const scrollTop = window.scrollY || document.documentElement.scrollTop;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;

    if (docHeight <= 0) return;

    maxScroll = Math.max(maxScroll, scrollTop / docHeight);

    if (maxScroll > 0.55) {
      showCapture();
    }
  });
})();