(() => {
  const drawerEl = document.getElementById("hcVolunteerDrawer");
  if (!drawerEl) return;

  const titleEl = document.getElementById("hcVolunteerDrawerLabel");
  const bodyEl = document.getElementById("hcVolBody");
  const btnCopyEmail = document.getElementById("hcVolCopyEmail");
  const btnCopyPhone = document.getElementById("hcVolCopyPhone");
  const btnAssign = document.getElementById("hcDrawerAssignBtn") || document.getElementById("hcVolAssignBtn");
  const btnProfile = document.getElementById("hcVolProfileBtn");
  const hintEl = document.getElementById("hcVolHint");
  const assignHintEl = document.getElementById("hcDrawerAssignHint");

  if (!titleEl || !bodyEl || !btnCopyEmail || !btnCopyPhone || !btnAssign || !btnProfile || !hintEl) {
    return;
  }

  let currentVolId = null;
  let currentReqId = null;
  let currentProfileUrl = "#";
  let currentEmail = "";
  let currentPhone = "";

  function esc(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  async function copyText(text) {
    const value = String(text || "").trim();
    if (!value) return false;

    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(value);
        return true;
      } catch (_) {
        // fallback below
      }
    }

    try {
      const ta = document.createElement("textarea");
      ta.value = value;
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch (_) {
      return false;
    }
  }

  function showMiniToast(message, ok = true) {
    let t = document.getElementById("hcToast");
    if (!t) {
      t = document.createElement("div");
      t.id = "hcToast";
      t.className = "hc-toast";
      t.innerHTML = `<span class="hc-toast__dot" aria-hidden="true"></span><span class="hc-toast__msg"></span>`;
      document.body.appendChild(t);
    }
    t.classList.toggle("hc-toast--ok", !!ok);
    t.classList.toggle("hc-toast--bad", !ok);
    const msgEl = t.querySelector("#hcToastMsg") || t.querySelector(".hc-toast__msg");
    if (msgEl) msgEl.textContent = message;
    t.classList.add("hc-toast--show");
    clearTimeout(window.__hcToastTimer);
    window.__hcToastTimer = setTimeout(() => {
      t.classList.remove("hc-toast--show");
    }, 1400);
  }

  function setLoading(volId) {
    titleEl.textContent = `Volunteer #${volId}`;
    bodyEl.innerHTML = `
      <div class="hc-skel"></div>
      <div class="hc-skel"></div>
      <div class="hc-skel"></div>
    `;
    hintEl.textContent = "";
    btnAssign.disabled = true;
    btnCopyEmail.disabled = true;
    btnCopyPhone.disabled = true;
    btnProfile.setAttribute("href", "#");
    btnProfile.setAttribute("aria-disabled", "true");
  }

  function setError(message) {
    bodyEl.innerHTML = `<div class="alert alert-warning mb-0">${esc(message)}</div>`;
    hintEl.textContent = "";
    btnAssign.disabled = true;
    btnCopyEmail.disabled = true;
    btnCopyPhone.disabled = true;
    btnProfile.setAttribute("href", "#");
    btnProfile.setAttribute("aria-disabled", "true");
  }

  function findAssignForm(volId, reqId) {
    const safeVolId = String(volId || "");
    const safeReqId = String(reqId || "");

    let form = null;
    if (safeVolId && safeReqId) {
      form = document.querySelector(
        `.hc-assign-form[data-volunteer-id="${safeVolId}"][data-request-id="${safeReqId}"]`
      );
      if (form) return form;
    }

    const rowSelector = safeVolId && safeReqId
      ? `[data-volunteer-id="${safeVolId}"][data-request-id="${safeReqId}"]`
      : safeVolId
        ? `[data-volunteer-id="${safeVolId}"]`
        : "";
    const row = rowSelector ? document.querySelector(rowSelector) : null;
    if (row) {
      form = row.querySelector(`form.hc-assign-form[data-volunteer-id="${safeVolId}"]`);
      if (form) return form;
      form = row.querySelector("form");
      if (form) return form;
    }
    return null;
  }

  function wireDrawerAssign(volId, reqId) {
    if (!btnAssign) return;
    const form = findAssignForm(volId, reqId);

    if (!form) {
      btnAssign.disabled = true;
      btnAssign.classList.add("disabled");
      if (assignHintEl) assignHintEl.classList.remove("d-none");
      btnAssign.onclick = null;
      return;
    }

    btnAssign.disabled = false;
    btnAssign.classList.remove("disabled");
    if (assignHintEl) assignHintEl.classList.add("d-none");
    btnAssign.onclick = (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (typeof form.requestSubmit === "function") form.requestSubmit();
      else form.submit();
    };
  }

  function renderCard(data) {
    const name = data.name || `Volunteer #${data.id}`;
    const emailValue = data.email ? String(data.email) : "";
    const phoneValue = data.phone ? String(data.phone) : "";
    const email = emailValue;
    const phone = phoneValue;
    const location = data.location || data.city || "";
    const languages = Array.isArray(data.languages)
      ? data.languages
      : data.languages
        ? [data.languages]
        : [];
    const roles = Array.isArray(data.roles) ? data.roles : data.roles ? [data.roles] : [];
    const availability = data.availability || "";
    const lastActive = data.last_active || "";
    const notifiedAt = data.notified_at || "";
    const seenAt = data.seen_at || "";
    const canHelpCount = Number.parseInt(data.can_help_count || 0, 10) || 0;
    const history = Array.isArray(data.history) ? data.history : [];

    currentProfileUrl = data.profile_url || "#";
    currentEmail = emailValue;
    currentPhone = phoneValue;
    titleEl.textContent = name;

    const historyHtml = history.length
      ? `<div class="hc-vol-history">${history
          .map(
            (h) => `
          <div class="hc-vol-history__item">
            <span class="hc-vol-history__action">${esc(h.action || "—")}</span>
            <span class="hc-vol-history__meta">Req #${esc(h.request_id || "—")} · ${esc(h.at || "—")}</span>
          </div>
        `
          )
          .join("")}</div>`
      : `<div class="text-muted small">No recent actions.</div>`;

    bodyEl.innerHTML = `
      <div class="hc-volcard">
        <div class="hc-volcard__row">
          <div class="hc-volcard__label">Email</div>
          <div class="hc-volcard__val">
            ${
              emailValue
                ? `<a href="mailto:${esc(emailValue)}"
                    class="hc-vol-link"
                    title="Envoyer un email">${esc(emailValue)}</a>`
                : "—"
            }
          </div>
        </div>
        <div class="hc-volcard__row">
          <div class="hc-volcard__label">Phone</div>
          <div class="hc-volcard__val">${phone ? `<a href="tel:${esc(phone)}">${esc(phone)}</a>` : "—"}</div>
        </div>
        <div class="hc-volcard__row">
          <div class="hc-volcard__label">Location</div>
          <div class="hc-volcard__val">${location ? esc(location) : "—"}</div>
        </div>
        <div class="hc-volcard__row">
          <div class="hc-volcard__label">Languages</div>
          <div class="hc-volcard__val">${languages.length ? languages.map(esc).join(", ") : "—"}</div>
        </div>
        <div class="hc-volcard__row">
          <div class="hc-volcard__label">Roles</div>
          <div class="hc-volcard__val">${roles.length ? roles.map(esc).join(", ") : "—"}</div>
        </div>
        <div class="hc-volcard__row">
          <div class="hc-volcard__label">Availability</div>
          <div class="hc-volcard__val">${availability ? esc(availability) : "—"}</div>
        </div>
        <div class="hc-volcard__row">
          <div class="hc-volcard__label">Last activity</div>
          <div class="hc-volcard__val">${lastActive ? esc(lastActive) : "—"}</div>
        </div>
        <div class="hc-volcard__row">
          <div class="hc-volcard__label">CAN_HELP count</div>
          <div class="hc-volcard__val">${canHelpCount}</div>
        </div>
        <div class="hc-volcard__row">
          <div class="hc-volcard__label">Notified</div>
          <div class="hc-volcard__val">${notifiedAt ? esc(notifiedAt) : "—"}</div>
        </div>
        <div class="hc-volcard__row">
          <div class="hc-volcard__label">Seen</div>
          <div class="hc-volcard__val">${seenAt ? esc(seenAt) : "—"}</div>
        </div>
      </div>
      <div class="mt-2">
        <div class="hc-offcanvas__kicker mb-1">Last actions</div>
        ${historyHtml}
      </div>
    `;

    btnCopyEmail.disabled = !emailValue;
    btnCopyPhone.disabled = !phoneValue;
    btnCopyEmail.setAttribute("data-hc-copy", "email");
    btnCopyEmail.setAttribute("data-hc-copy-value", emailValue);
    btnCopyPhone.setAttribute("data-hc-copy", "phone");
    btnCopyPhone.setAttribute("data-hc-copy-value", phoneValue);

    wireDrawerAssign(String(data.id), String(currentReqId || ""));
    btnProfile.setAttribute("href", currentProfileUrl || "#");
    btnProfile.setAttribute("aria-disabled", currentProfileUrl ? "false" : "true");
  }

  async function fetchVolunteer(volId, reqId) {
    const params = new URLSearchParams();
    if (reqId) params.set("req_id", String(reqId));
    const query = params.toString();
    const url = `/admin/api/volunteers/${encodeURIComponent(volId)}${query ? `?${query}` : ""}`;
    const res = await fetch(url, { credentials: "same-origin" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  document.addEventListener("click", async (event) => {
    const trigger = event.target.closest(".hc-vol-link[data-volunteer-id]");
    if (!trigger) return;

    const volId = trigger.getAttribute("data-volunteer-id");
    const reqId = trigger.getAttribute("data-request-id");
    if (!volId) return;

    currentVolId = volId;
    currentReqId = reqId || null;
    setLoading(volId);

    try {
      const data = await fetchVolunteer(volId, currentReqId);
      renderCard(data);
    } catch (_) {
      setError("Could not load volunteer details.");
    }
  });

  drawerEl.addEventListener(
    "click",
    async (event) => {
      const copyBtn = event.target.closest(".hc-copy-inline[data-hc-copy]");
      if (!copyBtn) return;
      const kind = (copyBtn.getAttribute("data-hc-copy") || "").toLowerCase();
      const value = copyBtn.getAttribute("data-hc-copy-value") || "";
      if (!value) return;
      event.preventDefault();
      event.stopPropagation();
      const ok = await copyText(value);
      if (ok) {
        hintEl.textContent = "Copied.";
        showMiniToast(kind === "phone" ? "Téléphone copié" : "Email copié", true);
      } else {
        hintEl.textContent = "Copy failed.";
        showMiniToast("Impossible de copier", false);
      }
    },
    true
  );

  btnCopyEmail.onclick = async (event) => {
    event.preventDefault();
    event.stopPropagation();
    const ok = await copyText(String(currentEmail || "").trim());
    if (ok) {
      hintEl.textContent = "Copied.";
      showMiniToast("Email copié", true);
    } else {
      hintEl.textContent = "Copy failed.";
      showMiniToast("Impossible de copier", false);
    }
  };

  btnCopyPhone.onclick = async (event) => {
    event.preventDefault();
    event.stopPropagation();
    const ok = await copyText(String(currentPhone || "").trim());
    if (ok) {
      hintEl.textContent = "Copied.";
      showMiniToast("Téléphone copié", true);
    } else {
      hintEl.textContent = "Copy failed.";
      showMiniToast("Impossible de copier", false);
    }
  };

})();
