(() => {
  const STORAGE_KEY = "hc.admin.requests.filters.v1";
  const form = document.getElementById("hcAdminFilterForm");
  const statusEl = document.getElementById("hcAdminFilterStatus");
  const searchEl = document.getElementById("hcAdminFilterSearch");
  const deletedEl = document.getElementById("filterDeleted");
  const hasQuery = new URLSearchParams(window.location.search);
  const toolbar = document.getElementById("hcRequestsToolbar");
  const menus = Array.from(document.querySelectorAll(".hc-rowmenu"));
  const actionForms = Array.from(document.querySelectorAll(".hc-request-action-form"));
  const statusMenus = Array.from(document.querySelectorAll(".hc-statusmenu"));

  const ROW_FEEDBACK_MS = 3200;
  const ROW_ERROR_FLASH_MS = 1800;
  const MIN_VISIBLE_BUSY_MS = 400;
  const FLICKER_THRESHOLD_MS = 300;
  const OWNER_LABEL_SELF = "Vous";
  const STATUS_CLASSES = {
    pending: ["bg-primary"],
    open: ["bg-primary"],
    in_progress: ["bg-warning", "text-dark"],
    done: ["bg-success"],
    rejected: ["bg-secondary"],
    cancelled: ["bg-secondary"],
    closed: ["bg-secondary"],
  };
  const STATUS_TEXT = {
    pending: "New",
    open: "Open",
    in_progress: "In progress",
    done: "Completed",
    rejected: "Rejected",
    cancelled: "Cancelled",
    closed: "Closed",
  };

  function syncToolbarHeightVar() {
    if (!toolbar) return;
    const h = toolbar.getBoundingClientRect().height || 0;
    document.documentElement.style.setProperty(
      "--hc-requests-toolbar-height",
      `${Math.ceil(h)}px`,
    );
  }
  syncToolbarHeightVar();
  window.addEventListener("resize", syncToolbarHeightVar);
  window.addEventListener("load", syncToolbarHeightVar);

  if (form && statusEl && searchEl) {
    const saveFilters = () => {
      try {
        localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({
            status: statusEl.value || "",
            q: searchEl.value || "",
            deleted: !!(deletedEl && deletedEl.checked),
          }),
        );
      } catch {}
    };
    form.addEventListener("submit", saveFilters);
    statusEl.addEventListener("change", saveFilters);
    searchEl.addEventListener("change", saveFilters);
    if (deletedEl) deletedEl.addEventListener("change", saveFilters);

    const hasExplicitFilters = ["status", "q", "deleted", "category", "risk"].some(
      (k) => hasQuery.has(k),
    );
    if (hasExplicitFilters) {
      sessionStorage.removeItem("hcAdminFiltersRestored");
    }
    if (!hasExplicitFilters && !sessionStorage.getItem("hcAdminFiltersRestored")) {
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        const saved = raw ? JSON.parse(raw) : null;
        if (saved && (saved.status || saved.q || saved.deleted)) {
          if (saved.status) statusEl.value = saved.status;
          if (typeof saved.q === "string") searchEl.value = saved.q;
          if (deletedEl) deletedEl.checked = !!saved.deleted;
          sessionStorage.setItem("hcAdminFiltersRestored", "1");
          form.submit();
        }
      } catch {}
    }
  }

  if (!menus.length && !actionForms.length && !statusMenus.length) return;

  function wait(ms) {
    return new Promise((resolve) => {
      window.setTimeout(resolve, ms);
    });
  }

  async function ensureStableBusy(startedAt) {
    const elapsed = performance.now() - startedAt;
    if (elapsed > FLICKER_THRESHOLD_MS && elapsed < MIN_VISIBLE_BUSY_MS) {
      await wait(MIN_VISIBLE_BUSY_MS - elapsed);
    }
  }

  function getRowFromNode(node) {
    return node?.closest?.("tr[data-request-id]") || null;
  }

  function notify(message, kind = "info") {
    const text = String(message || "").trim();
    if (!text) return;
    if (window.hcToast) {
      if (kind === "success" && typeof window.hcToast.success === "function") {
        window.hcToast.success(text);
        return;
      }
      if (kind === "error" && typeof window.hcToast.error === "function") {
        window.hcToast.error(text, { duration: 4200 });
        return;
      }
      if (typeof window.hcToast.info === "function") {
        window.hcToast.info(text);
        return;
      }
    }
    window.alert(text);
  }

  function normalizeMessage(message) {
    const text = String(message || "").trim();
    const lower = text.toLowerCase();
    if (!text) return "";
    if (lower.includes("no status change")) return "Aucune modification necessaire";
    if (lower.includes("deja pris")) return "Impossible d'assigner - deja pris";
    if (lower.includes("deja assigne a vous")) return "Aucune modification necessaire";
    if (lower.includes("locked")) return "Action refusee - statut incompatible";
    if (lower.includes("forbidden") || lower.includes("unauthorized")) return "Action refusee - acces insuffisant";
    if (lower.includes("no assigned volunteer")) return "Impossible de relancer - aucun intervenant assigne";
    if (lower.includes("suppressed")) return "Aucune modification necessaire";
    if (lower.includes("assigned to volunteer")) return "Intervenant assigne";
    if (lower.includes("nudge sent")) return "Intervenant relance";
    if (lower.includes("status updated")) return "Statut mis a jour";
    if (lower.includes("request has been assigned to you")) return "Responsable assigne";
    return text;
  }

  function setRowFeedback(target, message, kind = "info", options = {}) {
    const row = getRowFromNode(target);
    const feedback = row?.querySelector("[data-request-feedback]");
    if (!feedback) return;
    feedback.textContent = String(message || "").trim();
    feedback.dataset.state = kind;
    window.clearTimeout(feedback._timerId);
    if (options.sticky !== false) {
      feedback._timerId = window.setTimeout(() => {
        feedback.textContent = "";
        feedback.dataset.state = "";
      }, ROW_FEEDBACK_MS);
    }
  }

  function setMenuFeedback(target, message, kind = "info") {
    const row = getRowFromNode(target);
    const feedback = row?.querySelector("[data-request-menu-feedback]");
    if (!feedback) return;
    feedback.textContent = String(message || "").trim();
    feedback.dataset.state = kind;
  }

  function clearMenuFeedback(target) {
    const row = getRowFromNode(target);
    const feedback = row?.querySelector("[data-request-menu-feedback]");
    if (!feedback) return;
    feedback.textContent = "";
    feedback.dataset.state = "";
  }

  function flashRowState(target, kind) {
    const row = getRowFromNode(target);
    if (!row) return;
    row.classList.remove("hc-request-row--success", "hc-request-row--error");
    if (!kind) return;
    row.classList.add(kind === "success" ? "hc-request-row--success" : "hc-request-row--error");
    const timeout = kind === "error" ? ROW_ERROR_FLASH_MS : ROW_FEEDBACK_MS;
    window.clearTimeout(row._stateTimerId);
    row._stateTimerId = window.setTimeout(() => {
      row.classList.remove("hc-request-row--success", "hc-request-row--error");
    }, timeout);
  }

  function setMenuExpanded(menu) {
    const summary = menu?.querySelector(".hc-rowmenu__summary");
    if (summary) summary.setAttribute("aria-expanded", menu.open ? "true" : "false");
  }

  function setStatusMenuExpanded(menu) {
    const summary = menu?.querySelector(".hc-statusmenu__summary");
    if (summary) summary.setAttribute("aria-expanded", menu.open ? "true" : "false");
  }

  function parseAlertState(markup) {
    const doc = new DOMParser().parseFromString(String(markup || ""), "text/html");
    const alert = doc.querySelector(".alert");
    const message = alert?.textContent?.trim() || "";
    let kind = "info";
    if (alert?.classList.contains("alert-success")) kind = "success";
    else if (alert?.classList.contains("alert-danger")) kind = "error";
    else if (alert?.classList.contains("alert-warning")) kind = "warning";
    return { doc, message, kind };
  }

  function setButtonBusy(button, busy) {
    if (!button) return;
    if (!button.dataset.originalLabel) {
      button.dataset.originalLabel = button.textContent.trim();
    }
    const loadingLabel = (button.dataset.loadingText || "Traitement...").trim();
    button.disabled = !!busy;
    button.dataset.loading = busy ? "true" : "false";
    button.setAttribute("aria-busy", busy ? "true" : "false");
    button.textContent = busy ? loadingLabel : button.dataset.originalLabel;
  }

  function updateOwnerUi(row, ownerState = "mine", ownerLabel = OWNER_LABEL_SELF) {
    if (!row) return;
    const ownerMeta = row.querySelector("[data-request-owner-label]");
    const ownerBadge = row.querySelector("[data-request-owner-badge]");
    const hasOwner = ownerState === "mine" || ownerState === "taken";
    row.dataset.ownerId = hasOwner ? row.dataset.ownerId || "assigned" : "";
    row.dataset.hasOwner = hasOwner ? "1" : "0";
    row.dataset.ownerMissing = hasOwner ? "0" : "1";
    row.dataset.ownerState = ownerState;
    if (ownerMeta) {
      ownerMeta.textContent = ownerState === "none" ? "Sans responsable" : ownerLabel;
      ownerMeta.title = ownerMeta.textContent;
    }
    if (ownerBadge) {
      ownerBadge.className = "badge ms-1";
      if (ownerState === "mine") {
        ownerBadge.classList.add("text-bg-success");
        ownerBadge.textContent = "Mine";
      } else if (ownerState === "taken") {
        ownerBadge.classList.add("text-bg-secondary");
        ownerBadge.textContent = "Taken";
      } else {
        ownerBadge.classList.add("text-bg-primary");
        ownerBadge.textContent = "Sans responsable";
      }
    }
  }

  function updatePrimaryActionUi(row) {
    const primaryAction = row?.querySelector("[data-request-primary-action]");
    const href = row?.dataset.href || "";
    if (!row || !primaryAction || !href) return;
    primaryAction.innerHTML =
      `<a class="btn btn-outline-primary btn-sm" href="${href}" data-no-rowclick ` +
      `title="Open request details" aria-label="Open request details">Ouvrir le dossier</a>`;
  }

  function updateStatusUi(row, statusKey, label) {
    if (!row) return;
    const canonical = String(statusKey || "").trim().toLowerCase();
    const statusMenu = row.querySelector(".hc-statusmenu");
    const summary = statusMenu?.querySelector(".hc-statusmenu__summary");
    const labelEl = statusMenu?.querySelector(".hc-statusmenu__label");
    const assignOwnerButton = row.querySelector('[data-request-action="assign-owner"] .hc-request-action-btn');
    const assignVolunteerButton = row.querySelector('[data-request-action="assign-volunteer"] .hc-request-action-btn');
    const isClosed = ["done", "rejected", "cancelled", "closed"].includes(canonical);
    const rowStateMap = {
      pending: "NEW",
      open: "NEW",
      in_progress: "IN_PROGRESS",
      done: "COMPLETED",
      rejected: "CLOSED",
      cancelled: "CLOSED",
      closed: "CLOSED",
    };
    row.dataset.hcStatusRow = rowStateMap[canonical] || row.dataset.hcStatusRow || "";
    if (summary) {
      summary.classList.remove("bg-primary", "bg-warning", "text-dark", "bg-success", "bg-secondary");
      const classes = STATUS_CLASSES[canonical] || STATUS_CLASSES.closed;
      summary.classList.add(...classes);
    }
    if (labelEl) {
      const text = label || STATUS_TEXT[canonical] || labelEl.textContent;
      labelEl.textContent = text;
    }
    if (statusMenu) statusMenu.dataset.initialLabel = labelEl?.textContent?.trim() || "";
    if (assignOwnerButton) {
      assignOwnerButton.disabled = isClosed;
      assignOwnerButton.setAttribute("aria-disabled", isClosed ? "true" : "false");
      assignOwnerButton.title = isClosed
        ? "Action refusee - statut incompatible"
        : "Assign yourself as owner";
      assignOwnerButton.setAttribute("aria-label", assignOwnerButton.title);
    }
    if (assignVolunteerButton) {
      assignVolunteerButton.disabled = isClosed || assignVolunteerButton.getAttribute("aria-disabled") === "true";
      if (isClosed) {
        assignVolunteerButton.setAttribute("aria-disabled", "true");
        assignVolunteerButton.title = "Action refusee - statut incompatible";
        assignVolunteerButton.setAttribute("aria-label", "Action refusee - statut incompatible");
      }
    }
  }

  function applyRowActionResult(form, result) {
    const row = getRowFromNode(form);
    if (!row) return;
    const actionKind = form.dataset.requestAction || "";
    if (actionKind === "assign-owner" && result.changed) {
      updateOwnerUi(row, "mine", OWNER_LABEL_SELF);
      updatePrimaryActionUi(row);
    }
    if (actionKind === "assign-volunteer" && result.changed) {
      const actionBtn = form.querySelector(".hc-request-action-btn");
      if (actionBtn) {
        actionBtn.disabled = true;
        actionBtn.setAttribute("aria-disabled", "true");
        actionBtn.title = "Intervenant deja assigne";
        actionBtn.setAttribute("aria-label", "Intervenant deja assigne");
      }
      row.dataset.assignedVolunteerId = "updated";
    }
  }

  function normalizeParsedResult(form, parsed) {
    const message = normalizeMessage(parsed.message);
    let kind = parsed.kind === "warning" ? "error" : parsed.kind || "info";
    let changed = parsed.kind === "success";
    if (message === "Aucune modification necessaire") {
      kind = "info";
      changed = false;
    }
    return { ...parsed, message, kind, changed };
  }

  async function submitActionForm(form) {
    const startedAt = performance.now();
    const body = new URLSearchParams(new FormData(form));
    const res = await fetch(form.action, {
      method: "POST",
      headers: {
        Accept: "text/html,application/xhtml+xml",
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
      },
      body,
      credentials: "same-origin",
    });
    const text = await res.text();
    await ensureStableBusy(startedAt);
    const normalized = normalizeParsedResult(form, parseAlertState(text));
    if (!res.ok) {
      throw new Error(normalized.message || "Action impossible pour le moment.");
    }
    return normalized;
  }

  function focusFirstMenuItem(menu) {
    const firstItem = menu?.querySelector(".hc-rowmenu__item");
    if (firstItem instanceof HTMLElement) firstItem.focus();
  }

  function handleRowMenuKeydown(e) {
    const menu = e.target.closest(".hc-rowmenu");
    if (!menu) return;
    const items = Array.from(menu.querySelectorAll(".hc-rowmenu__item"));
    const summary = menu.querySelector(".hc-rowmenu__summary");
    const currentIndex = items.indexOf(document.activeElement);

    if ((e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") && document.activeElement === summary) {
      e.preventDefault();
      if (!menu.open) menu.open = true;
      focusFirstMenuItem(menu);
      return;
    }
    if (e.key === "ArrowDown" && currentIndex >= 0) {
      e.preventDefault();
      items[(currentIndex + 1) % items.length]?.focus();
      return;
    }
    if (e.key === "ArrowUp" && currentIndex >= 0) {
      e.preventDefault();
      items[(currentIndex - 1 + items.length) % items.length]?.focus();
      return;
    }
    if (e.key === "Home" && items.length) {
      e.preventDefault();
      items[0]?.focus();
      return;
    }
    if (e.key === "End" && items.length) {
      e.preventDefault();
      items[items.length - 1]?.focus();
      return;
    }
    if (e.key === "Escape") {
      menu.open = false;
      setMenuExpanded(menu);
      summary?.focus();
    }
  }

  actionForms.forEach((formEl) => {
    formEl.addEventListener("submit", async (e) => {
      const submitter =
        e.submitter ||
        formEl.querySelector('button[type="submit"], input[type="submit"]');
      if (!(submitter instanceof HTMLElement) || formEl.dataset.submitting === "true") return;

      e.preventDefault();
      formEl.dataset.submitting = "true";
      clearMenuFeedback(formEl);
      setButtonBusy(submitter, true);
      setRowFeedback(formEl, submitter.dataset.loadingText || "Traitement...", "info", { sticky: false });

      try {
        const result = await submitActionForm(formEl);
        const message =
          result.message || formEl.dataset.successMessage || submitter.dataset.originalLabel || "Action effectuee.";

        applyRowActionResult(formEl, result);

        if (result.changed) {
          const menu = formEl.closest(".hc-rowmenu");
          if (menu) {
            menu.open = false;
            setMenuExpanded(menu);
          }
          setRowFeedback(formEl, message, "success");
          flashRowState(formEl, "success");
          notify(message, "success");
        } else {
          setRowFeedback(formEl, message, "info");
          setMenuFeedback(formEl, message, "info");
          notify(message, "info");
        }
      } catch (error) {
        const message = normalizeMessage(
          error instanceof Error ? error.message : "Action impossible pour le moment.",
        );
        setRowFeedback(formEl, message, "error");
        setMenuFeedback(formEl, message, "error");
        flashRowState(formEl, "error");
        notify(message, "error");
      } finally {
        formEl.dataset.submitting = "false";
        setButtonBusy(submitter, false);
      }
    });
  });

  document.addEventListener("keydown", handleRowMenuKeydown);

  document.addEventListener(
    "toggle",
    (e) => {
      const menu = e.target;
      if (!(menu instanceof HTMLElement) || !menu.classList.contains("hc-rowmenu")) return;
      setMenuExpanded(menu);
      if (!menu.open) return;
      menus.forEach((m) => {
        if (m !== menu) {
          m.open = false;
          setMenuExpanded(m);
        }
      });
    },
    true,
  );

  document.addEventListener(
    "toggle",
    (e) => {
      const menu = e.target;
      if (!(menu instanceof HTMLElement) || !menu.classList.contains("hc-statusmenu")) return;
      setStatusMenuExpanded(menu);
    },
    true,
  );

  document.addEventListener("click", (e) => {
    if (e.target.closest(".hc-rowmenu")) return;
    menus.forEach((m) => {
      m.open = false;
      setMenuExpanded(m);
    });
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    menus.forEach((m) => {
      m.open = false;
      setMenuExpanded(m);
    });
  });

  menus.forEach(setMenuExpanded);
  statusMenus.forEach(setStatusMenuExpanded);

  window.hcAdminRequestsUi = window.hcAdminRequestsUi || {};
  window.hcAdminRequestsUi.updateStatusRow = updateStatusUi;
  window.hcAdminRequestsUi.setRowFeedback = setRowFeedback;
  window.hcAdminRequestsUi.flashRowState = flashRowState;
  window.hcAdminRequestsUi.normalizeMessage = normalizeMessage;
})();

(() => {
  const rows = Array.from(document.querySelectorAll("tr[data-href]"));
  const searchEl = document.getElementById("hcAdminFilterSearch");
  const selectAll = document.getElementById("hcSelectAllVisible");
  const bulkCount = document.getElementById("hcBulkCount");
  const bulkAction = document.getElementById("hcBulkAction");
  const bulkApply = document.getElementById("hcBulkApply");
  const bulkClear = document.getElementById("hcBulkClear");
  const bulkBar = document.getElementById("hcBulkBar");
  const noMatch = document.getElementById("hcRequestsNoMatch");
  const csrf = bulkBar?.dataset.csrf || "";
  const quickState = new Set();
  const quickChipsRoot = document.getElementById("hcQuickChips");
  const riskShortcutLinks = Array.from(document.querySelectorAll("[data-risk-shortcut]"));
  const riskCountEls = Array.from(document.querySelectorAll("[data-risk-count]"));
  let activeRiskShortcut =
    riskShortcutLinks.find((link) => link.classList.contains("is-active"))?.dataset.riskShortcut || "";

  function paintQuickChipState() {
    quickChipsRoot?.querySelectorAll(".hc-quickchip").forEach((btn) => {
      const key = btn.dataset.quickFilter;
      btn.classList.toggle("is-active", !!key && quickState.has(key));
    });
  }

  quickChipsRoot?.addEventListener("click", (e) => {
    const btn = e.target.closest(".hc-quickchip");
    if (!btn) return;
    const key = btn.dataset.quickFilter;
    if (!key) return;
    if (key === "clear") quickState.clear();
    else if (quickState.has(key)) quickState.delete(key);
    else quickState.add(key);
    paintQuickChipState();
    if (typeof applyQuickFilters === "function") applyQuickFilters();
  });

  if (!rows.length) {
    paintQuickChipState();
    return;
  }

  function normalize(v) {
    return String(v || "").trim().toLowerCase();
  }

  const tableFilters = (() => {
    const predicates = new Map();
    const subscribers = new Set();

    function evaluateRow(row, options = {}) {
      const exclude = new Set(options.exclude || []);
      for (const [name, predicate] of predicates.entries()) {
        if (exclude.has(name)) continue;
        if (typeof predicate === "function" && !predicate(row)) return false;
      }
      return true;
    }

    function notifySubscribers() {
      subscribers.forEach((fn) => {
        try {
          fn();
        } catch {}
      });
    }

    function apply() {
      let visibleCount = 0;
      rows.forEach((row) => {
        const show = evaluateRow(row);
        row.style.display = show ? "" : "none";
        if (show) visibleCount += 1;
      });
      if (noMatch) noMatch.hidden = visibleCount > 0;
      notifySubscribers();
      return visibleCount;
    }

    return {
      setPredicate(name, predicate) {
        predicates.set(name, predicate);
        return apply();
      },
      removePredicate(name) {
        predicates.delete(name);
        return apply();
      },
      subscribe(fn) {
        subscribers.add(fn);
        return () => subscribers.delete(fn);
      },
      apply,
      countMatching(predicate, options = {}) {
        let count = 0;
        rows.forEach((row) => {
          if (evaluateRow(row, options) && predicate(row)) count += 1;
        });
        return count;
      },
      rows,
    };
  })();

  window.hcAdminRequestsTableFilters = tableFilters;

  let focusedIndex = -1;
  const rowCheckboxes = () => Array.from(document.querySelectorAll(".hc-row-select"));
  const visibleRows = () => rows.filter((r) => r.offsetParent !== null);

  function rowMatchesQuickFilters(row) {
    if (!quickState.size) return true;
    const hasNoOwner = row.dataset.ownerMissing === "1";
    const isUrgent = String(row.dataset.priority || "").toUpperCase() === "URGENT";
    const hasCanHelp = Number(row.dataset.sigCanHelp || 0) > 0;
    const isStale = row.dataset.stale72h === "1";
    for (const key of quickState) {
      if (key === "no_owner" && !hasNoOwner) return false;
      if (key === "urgent" && !isUrgent) return false;
      if (key === "can_help" && !hasCanHelp) return false;
      if (key === "stale" && !isStale) return false;
    }
    return true;
  }

  function matchesRiskShortcutKey(row, shortcutKey) {
    const riskLevel = normalize(row.dataset.riskLevel);
    const hasNoOwner = row.dataset.ownerMissing === "1";
    const isStale = row.dataset.stale72h === "1";
    if (shortcutKey === "critical") return riskLevel === "critical";
    if (shortcutKey === "attention") return riskLevel === "attention";
    if (shortcutKey === "no_owner") return hasNoOwner;
    if (shortcutKey === "stale") return isStale;
    return true;
  }

  function rowMatchesRiskShortcut(row) {
    return !activeRiskShortcut || matchesRiskShortcutKey(row, activeRiskShortcut);
  }

  function paintRiskShortcutState() {
    riskShortcutLinks.forEach((link) => {
      const isActive = !!activeRiskShortcut && link.dataset.riskShortcut === activeRiskShortcut;
      link.classList.toggle("is-active", isActive);
      link.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
  }

  function updateRiskShortcutCounts() {
    const countFor = (shortcut) => tableFilters.countMatching(
      (row) => matchesRiskShortcutKey(row, shortcut),
      { exclude: ["riskShortcut"] },
    );

    riskCountEls.forEach((el) => {
      const key = el.dataset.riskCount;
      el.textContent = String(countFor(key));
    });
  }

  function applyQuickFilters() {
    paintQuickChipState();
    paintRiskShortcutState();
    tableFilters.setPredicate("quickChips", rowMatchesQuickFilters);
    tableFilters.setPredicate("riskShortcut", rowMatchesRiskShortcut);
    updateRiskShortcutCounts();
    updateBulkUi();
    const vis = visibleRows();
    if (!vis.includes(rows[focusedIndex])) {
      focusedIndex = vis.length ? rows.indexOf(vis[0]) : -1;
      syncRowFocus();
    }
  }

  function syncRowFocus() {
    rows.forEach((r, i) => r.classList.toggle("hc-row-focus", i === focusedIndex));
  }

  function selectedBoxes() {
    return rowCheckboxes().filter((cb) => cb.checked && cb.closest("tr")?.offsetParent !== null);
  }

  function updateBulkUi() {
    const selected = selectedBoxes();
    if (bulkCount) bulkCount.textContent = `${selected.length} selected`;
    if (selectAll) {
      const visibleChecks = rowCheckboxes().filter((cb) => cb.closest("tr")?.offsetParent !== null);
      selectAll.checked = visibleChecks.length > 0 && visibleChecks.every((cb) => cb.checked);
      selectAll.indeterminate = visibleChecks.some((cb) => cb.checked) && !selectAll.checked;
    }
  }

  rowCheckboxes().forEach((cb) => {
    cb.addEventListener("change", updateBulkUi);
    cb.addEventListener("click", (e) => e.stopPropagation());
  });

  if (selectAll) {
    selectAll.addEventListener("change", () => {
      const on = !!selectAll.checked;
      rowCheckboxes().forEach((cb) => {
        if (cb.closest("tr")?.offsetParent !== null) cb.checked = on;
      });
      updateBulkUi();
    });
  }

  if (bulkClear) {
    bulkClear.addEventListener("click", () => {
      rowCheckboxes().forEach((cb) => {
        cb.checked = false;
      });
      updateBulkUi();
    });
  }

  riskShortcutLinks.forEach((link) => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const key = link.dataset.riskShortcut || "";
      activeRiskShortcut = activeRiskShortcut === key ? "" : key;
      applyQuickFilters();
    });
  });

  async function postForm(url, data) {
    const body = new URLSearchParams(data);
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
      body,
      credentials: "same-origin",
    });
    return res.ok;
  }

  if (bulkApply) {
    bulkApply.addEventListener("click", async () => {
      const action = bulkAction?.value || "";
      const selected = selectedBoxes();
      if (!action || !selected.length) return;

      const ids = selected.map((cb) => cb.value);
      const links = selected.map((cb) => cb.dataset.link).filter(Boolean);

      if (action === "open") {
        links.forEach((href) => window.open(href, "_blank", "noopener"));
        return;
      }
      if (action === "copy_ids") {
        await navigator.clipboard.writeText(ids.join(", "));
        return;
      }
      if (action === "copy_links") {
        await navigator.clipboard.writeText(links.join("\n"));
        return;
      }

      bulkApply.disabled = true;
      const oldLabel = bulkApply.textContent;
      bulkApply.textContent = "Working...";
      let okCount = 0;
      try {
        if (action === "nudge") {
          for (const id of ids) {
            const ok = await postForm(`/admin/requests/${id}/nudge`, { csrf_token: csrf });
            if (ok) okCount += 1;
          }
        } else if (action === "claim_me") {
          for (const id of ids) {
            const ok = await postForm(`/admin/requests/${id}/assign`, {
              csrf_token: csrf,
              next: "/admin/requests",
            });
            if (ok) okCount += 1;
          }
        } else if (action.startsWith("status:")) {
          const status = action.split(":", 2)[1];
          for (const id of ids) {
            const ok = await postForm(`/admin/requests/${id}/status`, { csrf_token: csrf, status });
            if (ok) okCount += 1;
          }
        }
      } finally {
        bulkApply.disabled = false;
        bulkApply.textContent = oldLabel;
      }

      if (okCount > 0) window.location.reload();
    });
  }

  document.addEventListener("keydown", (e) => {
    const target = e.target;
    const inInput =
      target && (target.matches?.("input, textarea, select") || target.closest?.('[contenteditable="true"]'));
    if (e.key === "/" && !inInput) {
      e.preventDefault();
      if (searchEl) {
        searchEl.focus();
        searchEl.select();
      }
      return;
    }
    if (inInput) return;

    const vis = visibleRows();
    if (!vis.length) return;
    if (e.key === "j" || e.key === "J") {
      e.preventDefault();
      const currentRow = focusedIndex >= 0 ? rows[focusedIndex] : null;
      const currentVisibleIdx = currentRow ? vis.indexOf(currentRow) : -1;
      const nextVisible = vis[Math.min((currentVisibleIdx < 0 ? -1 : currentVisibleIdx) + 1, vis.length - 1)];
      focusedIndex = rows.indexOf(nextVisible);
      syncRowFocus();
      nextVisible?.scrollIntoView({ block: "nearest" });
      return;
    }
    if (e.key === "k" || e.key === "K") {
      e.preventDefault();
      const currentRow = focusedIndex >= 0 ? rows[focusedIndex] : null;
      const currentVisibleIdx = currentRow ? vis.indexOf(currentRow) : vis.length;
      const prevVisible = vis[Math.max((currentVisibleIdx < 0 ? vis.length : currentVisibleIdx) - 1, 0)];
      focusedIndex = rows.indexOf(prevVisible);
      syncRowFocus();
      prevVisible?.scrollIntoView({ block: "nearest" });
      return;
    }
    if (e.key === "Enter" && focusedIndex >= 0) {
      const row = rows[focusedIndex];
      if (!row || document.activeElement?.closest(".hc-rowmenu")) return;
      e.preventDefault();
      const href = row.dataset.href;
      if (href) window.location.href = href;
    }
    if (e.key === "x" || e.key === "X") {
      if (focusedIndex >= 0) {
        const cb = rows[focusedIndex].querySelector(".hc-row-select");
        if (cb) {
          cb.checked = !cb.checked;
          updateBulkUi();
        }
      }
    }
  });

  const firstVisible = visibleRows()[0];
  if (firstVisible) {
    focusedIndex = rows.indexOf(firstVisible);
    syncRowFocus();
  }
  tableFilters.subscribe(() => {
    updateRiskShortcutCounts();
    updateBulkUi();
  });
  applyQuickFilters();
  updateBulkUi();
})();
