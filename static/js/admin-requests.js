(() => {
  const form = document.getElementById("hcAdminFilters");
  if (!form) return;

  const qInput = document.getElementById("hcAdminQ");
  if (!qInput) return;

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

  form.addEventListener("submit", () => {
    setLoading(true);
  });

  showClearIfNeeded();
})();
