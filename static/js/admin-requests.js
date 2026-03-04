(() => {
  const STORAGE_KEY = "hc.admin.requests.filters.v1";
  const form = document.getElementById("hcAdminFilterForm");
  const statusEl = document.getElementById("hcAdminFilterStatus");
  const searchEl = document.getElementById("hcAdminFilterSearch");
  const deletedEl = document.getElementById("filterDeleted");
  const hasQuery = new URLSearchParams(window.location.search);

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

  const menus = Array.from(document.querySelectorAll(".hc-rowmenu"));
  if (!menus.length) return;

  document.addEventListener(
    "toggle",
    (e) => {
      const menu = e.target;
      if (!(menu instanceof HTMLElement) || !menu.classList.contains("hc-rowmenu")) return;
      if (!menu.open) return;
      menus.forEach((m) => {
        if (m !== menu) m.open = false;
      });
    },
    true,
  );

  document.addEventListener("click", (e) => {
    if (e.target.closest(".hc-rowmenu")) return;
    menus.forEach((m) => {
      m.open = false;
    });
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    menus.forEach((m) => {
      m.open = false;
    });
  });
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
  const csrf = bulkBar?.dataset.csrf || "";
  const quickState = new Set();
  const quickChipsRoot = document.getElementById("hcQuickChips");

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

  let focusedIndex = -1;
  const rowCheckboxes = () => Array.from(document.querySelectorAll(".hc-row-select"));
  const visibleRows = () => rows.filter((r) => r.offsetParent !== null);

  function rowMatchesQuickFilters(row) {
    if (!quickState.size) return true;
    const hasNoOwner = !String(row.dataset.assignedVolunteerId || "").trim();
    const isUrgent = String(row.dataset.priority || "").toUpperCase() === "URGENT";
    const hasCanHelp = Number(row.dataset.sigCanHelp || 0) > 0;
    const isStale = !!row.querySelector('[title*="Stale request"], [title*="Stale"]');
    for (const key of quickState) {
      if (key === "no_owner" && !hasNoOwner) return false;
      if (key === "urgent" && !isUrgent) return false;
      if (key === "can_help" && !hasCanHelp) return false;
      if (key === "stale" && !isStale) return false;
    }
    return true;
  }

  function applyQuickFilters() {
    rows.forEach((row) => {
      row.style.display = rowMatchesQuickFilters(row) ? "" : "none";
    });
    paintQuickChipState();
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
  applyQuickFilters();
  updateBulkUi();
})();
