(() => {
  const menus = Array.from(document.querySelectorAll(".hc-statusmenu[data-request-id]"));
  if (!menus.length) return;

  const MIN_VISIBLE_BUSY_MS = 400;
  const FLICKER_THRESHOLD_MS = 300;

  function closeOthers(current) {
    menus.forEach((menu) => {
      if (menu !== current) menu.open = false;
    });
  }

  function placeMenu(menu) {
    const summary = menu.querySelector(".hc-statusmenu__summary");
    const list = menu.querySelector(".hc-statusmenu__list");
    if (!summary || !list || !menu.open) return;

    const summaryRect = summary.getBoundingClientRect();
    const viewportW = window.innerWidth || document.documentElement.clientWidth;
    const viewportH = window.innerHeight || document.documentElement.clientHeight;

    const preferredWidth = Math.max(168, Math.ceil(summaryRect.width + 36));
    list.style.minWidth = `${preferredWidth}px`;

    const listRect = list.getBoundingClientRect();
    const menuHeight = Math.max(120, Math.ceil(listRect.height || 180));
    const menuWidth = Math.max(preferredWidth, Math.ceil(listRect.width || preferredWidth));

    let left = Math.round(summaryRect.left);
    if (left + menuWidth > viewportW - 10) left = Math.max(10, viewportW - menuWidth - 10);

    let top = Math.round(summaryRect.bottom + 6);
    if (top + menuHeight > viewportH - 10 && summaryRect.top > menuHeight + 12) {
      top = Math.max(10, Math.round(summaryRect.top - menuHeight - 6));
    }

    list.style.left = `${left}px`;
    list.style.top = `${top}px`;
  }

  function showFlash(menu, message, kind) {
    const wrap = menu.closest(".hc-statusmenu-wrap");
    const flash = wrap?.querySelector(".hc-statusmenu__flash");
    if (!flash) return;

    flash.textContent = message;
    flash.classList.remove("is-ok", "is-error");
    if (kind) flash.classList.add(kind);

    window.clearTimeout(flash._timerId);
    flash._timerId = window.setTimeout(() => {
      flash.textContent = "";
      flash.classList.remove("is-ok", "is-error");
    }, 2200);
  }

  function showToast(message, kind) {
    const text = String(message || "").trim();
    if (!text || !window.hcToast) return;
    if (kind === "is-ok" && typeof window.hcToast.success === "function") {
      window.hcToast.success(text);
      return;
    }
    if (kind === "is-error" && typeof window.hcToast.error === "function") {
      window.hcToast.error(text, { duration: 4200 });
      return;
    }
    if (typeof window.hcToast.info === "function") {
      window.hcToast.info(text);
    }
  }

  function reloadCurrentQueue() {
    window.setTimeout(() => {
      window.location.reload();
    }, 120);
  }

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

  function setBusy(menu, busy, activeItem) {
    const summary = menu.querySelector(".hc-statusmenu__summary");
    const labelEl = menu.querySelector(".hc-statusmenu__label");
    const items = Array.from(menu.querySelectorAll(".hc-statusmenu__item[data-status-target]"));
    if (!menu.dataset.initialLabel && labelEl) {
      menu.dataset.initialLabel = labelEl.textContent.trim();
    }
    menu.dataset.busy = busy ? "true" : "false";
    menu.setAttribute("aria-busy", busy ? "true" : "false");
    if (summary) summary.setAttribute("aria-disabled", busy ? "true" : "false");
    if (labelEl) {
      labelEl.textContent = busy ? "Traitement..." : menu.dataset.initialLabel || labelEl.textContent;
    }
    items.forEach((item) => {
      item.disabled = !!busy;
      item.dataset.loading = item === activeItem && busy ? "true" : "false";
    });
  }

  async function submitStatus(menu, nextStatus, nextLabel) {
    const reqId = menu.dataset.requestId;
    const csrf = menu.dataset.csrf || "";
    if (!reqId || !nextStatus || !csrf) return { changed: false, message: "Action impossible." };

    const startedAt = performance.now();
    const body = new URLSearchParams({
      csrf_token: csrf,
      status: nextStatus,
    });

    const res = await fetch(`/admin/requests/${encodeURIComponent(reqId)}/status`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        Accept: "application/json",
      },
      credentials: "same-origin",
      body,
    });

    let data = {};
    try {
      data = await res.json();
    } catch {
      data = {};
    }
    await ensureStableBusy(startedAt);

    const ui = window.hcAdminRequestsUi || {};
    const normalizeMessage = typeof ui.normalizeMessage === "function"
      ? ui.normalizeMessage
      : (message) => String(message || "").trim();

    if (!res.ok) {
      throw new Error(normalizeMessage(data.message || "Echec de la mise a jour."));
    }

    if (data.success === false) {
      return {
        changed: false,
        message: normalizeMessage(data.message || "No status change."),
      };
    }

    const row = menu.closest("tr[data-request-id]");
    if (typeof ui.updateStatusRow === "function") {
      ui.updateStatusRow(row, data.status || nextStatus, nextLabel);
    }
    return {
      changed: true,
      message: "Statut mis a jour.",
    };
  }

  menus.forEach((menu) => {
    menu.addEventListener("toggle", () => {
      if (menu.open) {
        closeOthers(menu);
        window.requestAnimationFrame(() => placeMenu(menu));
      }
    });

    const items = Array.from(menu.querySelectorAll(".hc-statusmenu__item[data-status-target]"));
    items.forEach((item) => {
      item.addEventListener("click", async (e) => {
        e.preventDefault();
        e.stopPropagation();

        const nextStatus = (item.dataset.statusTarget || "").trim();
        const nextLabel = (item.dataset.statusLabel || item.textContent || "").trim();
        if (!nextStatus || menu.dataset.busy === "true") return;

        try {
          setBusy(menu, true, item);
          const result = await submitStatus(menu, nextStatus, nextLabel);
          const ui = window.hcAdminRequestsUi || {};
          if (result.changed) {
            showFlash(menu, result.message, "is-ok");
            showToast(result.message, "is-ok");
            if (typeof ui.setRowFeedback === "function") {
              ui.setRowFeedback(menu, result.message, "success");
            }
            if (typeof ui.flashRowState === "function") {
              ui.flashRowState(menu, "success");
            }
            menu.open = false;
            reloadCurrentQueue();
          } else {
            showFlash(menu, result.message, "");
            showToast(result.message, "");
            if (typeof ui.setRowFeedback === "function") {
              ui.setRowFeedback(menu, result.message, "info");
            }
          }
        } catch (error) {
          const message = error instanceof Error ? error.message : "Mise a jour impossible.";
          const ui = window.hcAdminRequestsUi || {};
          showFlash(menu, message, "is-error");
          showToast(message, "is-error");
          if (typeof ui.setRowFeedback === "function") {
            ui.setRowFeedback(menu, message, "error");
          }
          if (typeof ui.flashRowState === "function") {
            ui.flashRowState(menu, "error");
          }
        } finally {
          setBusy(menu, false, null);
        }
      });
    });
  });

  document.addEventListener("click", (e) => {
    if (e.target.closest(".hc-statusmenu")) return;
    menus.forEach((menu) => {
      menu.open = false;
    });
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    menus.forEach((menu) => {
      menu.open = false;
    });
  });

  const closeAll = () => {
    menus.forEach((menu) => {
      menu.open = false;
    });
  };
  window.addEventListener("resize", closeAll);
  window.addEventListener("scroll", closeAll, true);
})();
