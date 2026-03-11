(() => {
  const menus = Array.from(document.querySelectorAll(".hc-statusmenu[data-request-id]"));
  if (!menus.length) return;

  const STATUS_CLASS = {
    open: "bg-primary",
    in_progress: "bg-warning text-dark",
    done: "bg-success",
    cancelled: "bg-secondary",
  };

  const ROW_STATUS_MAP = {
    open: "NEW",
    in_progress: "IN_PROGRESS",
    done: "COMPLETED",
    cancelled: "CLOSED",
  };

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

  function updateBadge(menu, status, label) {
    const summary = menu.querySelector(".hc-statusmenu__summary");
    const labelEl = menu.querySelector(".hc-statusmenu__label");
    if (!summary || !labelEl) return;

    summary.classList.remove("bg-primary", "bg-warning", "text-dark", "bg-success", "bg-secondary");
    const classes = (STATUS_CLASS[status] || STATUS_CLASS.cancelled).split(/\s+/).filter(Boolean);
    summary.classList.add(...classes);
    labelEl.textContent = label || labelEl.textContent;
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
    }, 2000);
  }

  async function submitStatus(menu, nextStatus, nextLabel) {
    const reqId = menu.dataset.requestId;
    const csrf = menu.dataset.csrf || "";
    if (!reqId || !nextStatus || !csrf) return;

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

    if (!res.ok || data.success === false) {
      throw new Error(data.message || "Échec de la mise à jour");
    }

    const row = menu.closest("tr[data-hc-status-row]");
    const canonical = String(data.status || nextStatus).trim().toLowerCase();
    const rowStatus = ROW_STATUS_MAP[canonical];
    if (row && rowStatus) row.dataset.hcStatusRow = rowStatus;

    updateBadge(menu, canonical, nextLabel);
    showFlash(menu, "Statut mis à jour", "is-ok");
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
        if (!nextStatus) return;

        try {
          item.disabled = true;
          await submitStatus(menu, nextStatus, nextLabel);
          menu.open = false;
        } catch {
          showFlash(menu, "Mise à jour impossible", "is-error");
        } finally {
          item.disabled = false;
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
