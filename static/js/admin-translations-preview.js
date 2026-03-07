(function () {
  const previewBox = document.getElementById("hc-i18n-preview");
  const previewTitle = document.getElementById("hc-i18n-preview-title");
  const previewTitleText = document.getElementById("hc-i18n-preview-title-text");
  const previewBody = document.getElementById("hc-i18n-preview-body");
  const modeBadge = document.getElementById("hc-i18n-preview-mode-badge");
  const runNowBtn = document.getElementById("hc-i18n-run-now");
  const buttons = document.querySelectorAll("[data-hc-i18n-preview]");
  if (
    !previewBox ||
    !previewTitle ||
    !previewTitleText ||
    !previewBody ||
    !modeBadge ||
    !buttons.length
  ) {
    return;
  }
  const canRun = Boolean(runNowBtn);

  const state = {
    mode: "",
    locale: "",
    view: "",
    limit: "",
  };

  function showInfo(title, body, isError) {
    previewBox.classList.remove("d-none", "alert-info", "alert-danger");
    if (isError) {
      previewBox.classList.add("alert-danger");
    } else if (!previewBox.classList.contains("alert-primary") && !previewBox.classList.contains("alert-secondary")) {
      previewBox.classList.add("alert-info");
    }
    previewTitleText.textContent = title;
    previewBody.textContent = body;
  }

  function hideRunNow() {
    if (runNowBtn) {
      runNowBtn.classList.add("d-none");
    }
  }

  function showRunNow(mode) {
    if (!runNowBtn) {
      return;
    }
    runNowBtn.textContent = mode === "po" ? "Run now (PO)" : "Run now (rules)";
    runNowBtn.classList.remove("d-none");
  }

  function setRunBusy(isBusy) {
    if (!runNowBtn) {
      return;
    }
    runNowBtn.disabled = isBusy;
    if (isBusy) {
      runNowBtn.dataset.originalText = runNowBtn.textContent;
      runNowBtn.textContent = "Running...";
    } else if (runNowBtn.dataset.originalText) {
      runNowBtn.textContent = runNowBtn.dataset.originalText;
    }
  }

  function setModeUI(mode) {
    const modeLabel = mode === "po" ? "PO" : "RULES";
    modeBadge.classList.remove("d-none", "text-bg-primary", "text-bg-secondary", "text-bg-warning", "text-bg-success");
    previewBox.classList.remove("alert-info", "alert-primary", "alert-secondary", "alert-danger");
    if (mode === "po") {
      modeBadge.textContent = modeLabel;
      modeBadge.classList.add("text-bg-secondary");
      previewBox.classList.add("alert-secondary");
    } else {
      modeBadge.textContent = modeLabel;
      modeBadge.classList.add("text-bg-primary");
      previewBox.classList.add("alert-primary");
    }
  }

  function setBadgeState(state) {
    const baseMode = state.mode === "po" ? "PO" : "RULES";
    modeBadge.classList.remove("text-bg-warning", "text-bg-success", "text-bg-primary", "text-bg-secondary");
    if (state.kind === "running") {
      modeBadge.textContent = baseMode + " • RUNNING";
      modeBadge.classList.add("text-bg-warning");
      return;
    }
    if (state.kind === "done") {
      modeBadge.textContent = baseMode + " • DONE";
      modeBadge.classList.add("text-bg-success");
      return;
    }
    if (state.mode === "po") {
      modeBadge.textContent = baseMode;
      modeBadge.classList.add("text-bg-secondary");
    } else {
      modeBadge.textContent = baseMode;
      modeBadge.classList.add("text-bg-primary");
    }
  }

  function endpointFor(mode) {
    if (mode === "po") {
      return "/admin/translations/bootstrap-from-po";
    }
    return "/admin/translations/bulk-suggest-apply";
  }

  function renderReportTitle(mode, isDryRun) {
    if (mode === "po") {
      return isDryRun ? "PO dry-run report" : "PO run report";
    }
    return isDryRun ? "Rules dry-run report" : "Rules run report";
  }

  function renderReportBody(mode, data) {
    if (mode === "po") {
      return (
        "missing_total=" + (data.missing_total ?? 0) +
        ", po_found_applied=" + (data.po_found_applied ?? 0) +
        ", db_existing_skipped=" + (data.db_existing_skipped ?? 0) +
        ", po_not_found_skipped=" + (data.po_not_found_skipped ?? 0) +
        ", limit_hit=" + (data.limit_hit ? "yes" : "no") +
        (data.limit_hit ? " (increase limit or rerun)" : "")
      );
    }
    return (
      "missing=" + (data.missing ?? 0) +
      ", applied=" + (data.applied ?? 0) +
      ", skipped=" + (data.skipped ?? 0) +
      ", limit_hit=" + (data.limit_hit ? "yes" : "no") +
      (data.limit_hit ? " (increase limit or rerun)" : "")
    );
  }

  async function postAction(mode, locale, view, limit, isDryRun) {
    const endpoint = endpointFor(mode);
    const body = new URLSearchParams();
    body.set("locale", locale);
    body.set("view", view);
    body.set("limit", limit);
    if (isDryRun) {
      body.set("dry_run", "1");
    }
    body.set("format", "json");
    const res = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: body.toString(),
    });
    const data = await res.json();
    return { res, data };
  }

  async function runPreview(btn) {
    const mode = btn.getAttribute("data-hc-i18n-preview") || "rules";
    const locale = btn.getAttribute("data-locale") || "fr";
    const view = btn.getAttribute("data-view") || "ops";
    const limit = btn.getAttribute("data-limit") || (mode === "po" ? "300" : "200");

    showInfo("Running preview...", "Please wait.", false);
    hideRunNow();

    try {
      const { res, data } = await postAction(mode, locale, view, limit, true);
      if (!res.ok || !data || data.ok === false) {
        const msg = (data && (data.error || data.message)) || "Preview failed.";
        showInfo("Preview failed", msg, true);
        return;
      }

      state.mode = mode;
      state.locale = locale;
      state.view = view;
      state.limit = limit;
      setModeUI(mode);
      setBadgeState({ kind: "idle", mode });
      showInfo(
        renderReportTitle(mode, true),
        renderReportBody(mode, data) + " | Scope: locale=" + locale + ", view=" + view + ", limit=" + limit,
        false
      );
      showRunNow(mode);
    } catch (_err) {
      showInfo("Preview failed", "Preview failed due to network/server error.", true);
    }
  }

  async function runNow() {
    if (!canRun) {
      showInfo("Run blocked", "Read-only mode: preview is available, execute is disabled.", true);
      return;
    }
    if (!state.mode || !state.locale || !state.view || !state.limit) {
      showInfo("Run blocked", "Please run a preview first.", true);
      return;
    }
    if (!window.confirm("Execute real run now? This will write DB overrides.")) {
      return;
    }

    setRunBusy(true);
    setBadgeState({ kind: "running", mode: state.mode });
    try {
      const { res, data } = await postAction(state.mode, state.locale, state.view, state.limit, false);
      if (!res.ok || !data || data.ok === false) {
        const msg = (data && (data.error || data.message)) || "Run failed.";
        showInfo("Run failed", msg, true);
        return;
      }
      setModeUI(state.mode);
      setBadgeState({ kind: "done", mode: state.mode });
      showInfo(
        renderReportTitle(state.mode, false),
        renderReportBody(state.mode, data) +
          " | Scope: locale=" +
          state.locale +
          ", view=" +
          state.view +
          ", limit=" +
          state.limit,
        false
      );
      previewBody.textContent += " | Done. Reloading to update KPI...";
      setTimeout(() => {
        window.location.reload();
      }, 600);
    } catch (_err) {
      showInfo("Run failed", "Run failed due to network/server error.", true);
    } finally {
      setRunBusy(false);
    }
  }

  buttons.forEach((btn) => {
    btn.addEventListener("click", function () {
      runPreview(btn);
    });
  });

  if (runNowBtn) {
    runNowBtn.addEventListener("click", runNow);
  }
})();
