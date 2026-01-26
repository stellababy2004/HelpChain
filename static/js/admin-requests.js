(() => {
  const form = document.getElementById("hcAdminFilters");
  if (!form) return;

  const qInput = document.getElementById("hcAdminQ");
  if (!qInput) return;

  // --- Scroll restore (Gmail-style) ---
  const SCROLL_KEY = "hc_admin_requests_scrollY";

  try {
    const saved = sessionStorage.getItem(SCROLL_KEY);
    if (saved) {
      sessionStorage.removeItem(SCROLL_KEY);
      const y = parseInt(saved, 10);
      if (!Number.isNaN(y) && y > 0) {
        requestAnimationFrame(() => window.scrollTo(0, y));
      }
    }
  } catch (_) {}

  const btnClear = document.getElementById("hcAdminQClear");
  const spinner = document.getElementById("hcAdminQSpinner");

  let t = null;
  let lastValue = (qInput.value || "").trim();

  function setLoading(on) {
    if (spinner) spinner.style.display = on ? "" : "none";
    qInput.readOnly = !!on;
    if (btnClear) btnClear.disabled = !!on;
  }

  function showClearIfNeeded() {
    if (!btnClear) return;
    const has = (qInput.value || "").trim().length > 0;
    btnClear.style.display = has ? "" : "none";
  }

  function submitNow() {
    setLoading(true);

    try {
      sessionStorage.setItem(SCROLL_KEY, String(window.scrollY || 0));
    } catch (_) {}

    form.submit();
  }

  qInput.addEventListener("input", () => {
    showClearIfNeeded();

    const v = (qInput.value || "").trim();
    if (v === lastValue) return;

    if (t) clearTimeout(t);
    t = setTimeout(() => {
      lastValue = v;
      submitNow();
    }, 400);
  });

  qInput.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      qInput.value = "";
      showClearIfNeeded();
      lastValue = "";
      submitNow();
    }
  });

  if (btnClear) {
    btnClear.addEventListener("click", () => {
      qInput.value = "";
      showClearIfNeeded();
      lastValue = "";
      submitNow();
    });
  }

  const clearBarBtn = document.getElementById("hcClearSearchBtn");
  if (clearBarBtn && btnClear) {
    clearBarBtn.addEventListener("click", () => btnClear.click());
  }

  form.addEventListener("submit", () => {
    setLoading(true);
  });

  showClearIfNeeded();
})();

(() => {
  const bulkApply = document.getElementById("hcBulkApply");
  const bulkAction = document.getElementById("hcBulkAction");
  const bulkCount = document.getElementById("hcBulkCount");
  const selectAllPage = document.getElementById("hcSelectAllPage");
  const selectAllHeader = document.getElementById("hcSelectAllHeader");
  const rowChecks = Array.from(document.querySelectorAll(".hc-row-check"));

  const selectedLabel = bulkCount ? (bulkCount.dataset.selectedLabel || "selected") : "selected";

  function getSelectedIds() {
    return rowChecks
      .filter(c => c.checked)
      .map(c => parseInt(c.value, 10))
      .filter(n => Number.isFinite(n));
  }

  function updateBulkUI() {
    const n = getSelectedIds().length;
    if (bulkCount) bulkCount.textContent = `${n} ${selectedLabel}`;
    const canApply = n > 0 && bulkAction && bulkAction.value;
    if (bulkApply) bulkApply.disabled = !canApply;

    const allOn = rowChecks.length > 0 && rowChecks.every(c => c.checked);
    if (selectAllPage) selectAllPage.checked = allOn;
    if (selectAllHeader) selectAllHeader.checked = allOn;
  }

  function setAll(checked) {
    rowChecks.forEach(c => { c.checked = checked; });
    updateBulkUI();
  }

  rowChecks.forEach(c => {
    c.addEventListener("click", (e) => e.stopPropagation());
    c.addEventListener("change", updateBulkUI);
  });

  if (selectAllPage) {
    selectAllPage.addEventListener("change", () => setAll(selectAllPage.checked));
  }
  if (selectAllHeader) {
    selectAllHeader.addEventListener("change", () => setAll(selectAllHeader.checked));
  }

  if (bulkAction) bulkAction.addEventListener("change", updateBulkUI);

  function getCSRFToken() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : null;
  }

  async function postBulk(action, ids) {
    const csrf = getCSRFToken();
    const headers = { "Content-Type": "application/json" };
    if (csrf) headers["X-CSRFToken"] = csrf;

    const res = await fetch("/admin/requests/bulk", {
      method: "POST",
      headers,
      body: JSON.stringify({ action, ids }),
      credentials: "same-origin",
    });

    let data = null;
    try { data = await res.json(); } catch (_) {}
    if (!res.ok || !data || data.ok !== true) {
      throw new Error((data && data.error) ? data.error : `HTTP_${res.status}`);
    }
    return data;
  }

  if (bulkApply) {
    bulkApply.addEventListener("click", async () => {
      const action = bulkAction ? bulkAction.value : "";
      const ids = getSelectedIds();
      if (!action || ids.length === 0) return;

      if (action === "delete") {
        const ok = confirm("Delete moves requests to Deleted. Only archived requests will be deleted. Continue?");
        if (!ok) return;
      }

      bulkApply.disabled = true;

      try {
        const result = await postBulk(action, ids);

        if (result.blocked && result.blocked.length) {
          const blockedNotArchived = result.blocked
            .filter(x => x.reason === "not_archived")
            .map(x => x.id);
          if (blockedNotArchived.length) {
            alert(`Blocked (not archived): ${blockedNotArchived.join(", ")}`);
          }
        }

        window.location.reload();
      } catch (e) {
        alert(`Bulk action failed: ${e.message || e}`);
        updateBulkUI();
      }
    });
  }

  updateBulkUI();
})();
