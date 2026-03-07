(async function () {
  const buttons = document.querySelectorAll("[data-hc-suggest-btn]");
  if (!buttons.length) return;

  const key = buttons[0].getAttribute("data-key") || "";
  const localeSel = document.querySelector("[data-hc-locale]");
  const textarea = document.querySelector("[data-hc-translation-text]");
  const list = document.querySelector("[data-hc-suggest-list]");
  const status = document.querySelector("[data-hc-suggest-status]");
  const csrf = buttons[0].getAttribute("data-csrf") || "";

  if (!key || !textarea || !list || !status) return;

  async function loadSuggestions(btn) {
    const endpoint = btn.getAttribute("data-endpoint") || "/admin/translations/suggest";
    const provider = btn.getAttribute("data-provider") || "";
    status.textContent = "Loading suggestions...";
    list.innerHTML = "";

    const locale = (localeSel && localeSel.value) ? localeSel.value : (btn.getAttribute("data-locale") || "");
    const body = new URLSearchParams();
    body.set("key", key);
    body.set("locale", locale);
    if (provider) body.set("provider", provider);
    if (csrf) body.set("csrf_token", csrf);

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: body.toString(),
      });

      if (!res.ok) {
        status.textContent = "Failed to load suggestions.";
        return;
      }

      const data = await res.json();
      const providerLabel = data.provider ? ` (${data.provider})` : "";
      status.textContent = `Loaded suggestions${providerLabel}.`;

      (data.suggestions || []).forEach((s, idx) => {
        const item = document.createElement("div");
        item.className = "hc-suggest-item border rounded p-2 mb-2";
        item.innerHTML = `
          <label class="d-flex align-items-start gap-2 mb-0">
            <input type="radio" name="hc_suggest" value="${idx}" class="mt-1">
            <span>
              <span class="d-block fw-semibold hc-suggest-text"></span>
              <span class="d-block text-muted small hc-suggest-reason"></span>
            </span>
          </label>
        `;

        const textEl = item.querySelector(".hc-suggest-text");
        const reasonEl = item.querySelector(".hc-suggest-reason");
        const inputEl = item.querySelector("input");
        textEl.textContent = s.text || "";
        reasonEl.textContent = s.reason || "";
        inputEl.addEventListener("change", () => {
          textarea.value = s.text || "";
        });
        list.appendChild(item);
      });
    } catch (_) {
      status.textContent = "Failed to load suggestions.";
    }
  }

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => loadSuggestions(btn));
  });
})();
