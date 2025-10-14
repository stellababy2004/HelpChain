(function () {
  const btn = document.getElementById("darkToggle");
  const KEY = "hc-theme";
  function applyTheme(t) {
    if (t === "dark") {
      document.body.setAttribute("data-theme", "dark");
      btn && btn.setAttribute("aria-pressed", "true");
    } else {
      document.body.removeAttribute("data-theme");
      btn && btn.setAttribute("aria-pressed", "false");
    }
    try {
      localStorage.setItem(KEY, t);
    } catch (e) {}
  }
  const saved =
    (function () {
      try {
        return localStorage.getItem(KEY);
      } catch (e) {
        return null;
      }
    })() ||
    (window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light");
  applyTheme(saved);
  if (btn)
    btn.addEventListener("click", () =>
      applyTheme(
        document.body.getAttribute("data-theme") === "dark" ? "light" : "dark",
      ),
    );

  function initDragGrid() {
    const grid = document.querySelector(".dashboard-grid");
    if (!grid) return;
    let dragEl = null;

    grid.querySelectorAll(".widget").forEach((w) => {
      w.setAttribute("draggable", "true");
      w.addEventListener("dragstart", (e) => {
        dragEl = e.currentTarget;
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", dragEl.dataset.id || "");
        dragEl.classList.add("dragging");
      });
      w.addEventListener("dragend", () => {
        if (dragEl) {
          dragEl.classList.remove("dragging");
          dragEl = null;
          saveOrder();
        }
      });
    });

    grid.addEventListener("dragover", (e) => {
      e.preventDefault();
      const after = getDragAfterElement(grid, e.clientY);
      const dragging = document.querySelector(".dragging");
      if (!dragging) return;
      if (after == null) grid.appendChild(dragging);
      else grid.insertBefore(dragging, after);
    });

    function getDragAfterElement(container, y) {
      const draggableElements = [
        ...container.querySelectorAll(".widget:not(.dragging)"),
      ];
      return (
        draggableElements.reduce((closest, child) => {
          const box = child.getBoundingClientRect();
          const offset = y - box.top - box.height / 2;
          if (offset < 0 && offset > (closest.offset || -Infinity)) {
            return { offset, element: child };
          } else return closest;
        }, {}).element || null
      );
    }

    function saveOrder() {
      try {
        const ids = [...grid.querySelectorAll(".widget")]
          .map((n) => n.dataset.id || n.id || "")
          .filter(Boolean);
        localStorage.setItem("hc-dashboard-order", JSON.stringify(ids));
      } catch (e) {}
    }

    (function restore() {
      try {
        const raw = JSON.parse(
          localStorage.getItem("hc-dashboard-order") || "[]",
        );
        if (!raw || raw.length === 0) return;
        raw.forEach((id) => {
          const node =
            grid.querySelector(`[data-id="${id}"]`) ||
            grid.querySelector(`#${id}`);
          if (node) grid.appendChild(node);
        });
      } catch (e) {}
    })();
  }

  document.addEventListener("DOMContentLoaded", initDragGrid);
})();
