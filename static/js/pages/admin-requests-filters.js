(() => {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  if (path !== "/admin/requests") return;

  const rows = Array.from(document.querySelectorAll("tr[data-request-id]"));
  const cards = Array.from(document.querySelectorAll("[data-hc-filter-card]"));
  if (!rows.length || !cards.length) return;

  const clearControls = Array.from(document.querySelectorAll("[data-hc-filter-clear]"));
  const noMatch = document.querySelector("[data-hc-filter-empty]") || document.getElementById("hcRequestsNoMatch");
  const FILTER_PARAM = "filters";
  const SERVER_PARAMS = [
    "filter",
    "filters",
    "risk",
    "risk_level",
    "no_owner",
    "not_seen_72h",
    "queue",
    "sla_kind",
    "sla_days",
  ];

  const state = {
    tab: "",
    filter: "",
  };

  const normalize = (value) => String(value || "").trim().toLowerCase().replace(/-/g, "_");
  const normalizeTab = (value) => {
    const tab = String(value || "").trim().toUpperCase();
    const allowed = new Set(["NEW", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "CLOSED"]);
    if (tab === "COMPLETED") return "CLOSED";
    return allowed.has(tab) ? tab : "";
  };
  const normalizeFilter = (value) => {
    const key = normalize(value);
    if (key === "actionable" || key === "urgent_actionable") return "urgent_actionable";
    if (key === "urgent") return "critical";
    if (key === "stale" || key === "not_seen_72h") return "stale_72h";
    if (key === "owner_assignment_overdue" || key === "sla_attribution") return "unassigned_48h";
    if (key === "none") return "no_owner";
    const allowed = new Set(["critical", "attention", "assigned", "no_owner", "stale_72h", "unassigned_48h", "inactive_cases", "urgent_actionable"]);
    return allowed.has(key) ? key : "";
  };

  function rowStatus(row) {
    return String(row.dataset.statusBucket || row.dataset.hcStatusRow || row.dataset.status || "").trim().toUpperCase();
  }

  function isTerminal(row) {
    return ["COMPLETED", "CLOSED", "DONE", "REJECTED", "CANCELLED", "CANCELED"].includes(rowStatus(row));
  }

  function rowRisk(row) {
    return normalize(row.dataset.risk || row.dataset.riskLevel);
  }

  function cardFilter(card) {
    const key = normalize(card.dataset.filterKey);
    const value = card.dataset.filterValue || "";
    if (key === "status") return { tab: normalizeTab(value), filter: "" };
    if (key === "owner") return { tab: "", filter: normalizeFilter(value) };
    if (key === "stale") return { tab: "", filter: "stale_72h" };
    if (key === "inactive") return { tab: "", filter: "inactive_cases" };
    if (key === "actionable") return { tab: "", filter: "urgent_actionable" };
    if (key === "sla") return { tab: "", filter: "unassigned_48h" };
    return { tab: "", filter: normalizeFilter(value) };
  }

  function rowMatchesFilter(row, filter) {
    if (filter === "urgent_actionable") {
      return row.classList.contains("hc-row-actionable");
    }
    if (filter === "critical") {
      return rowRisk(row) === "critical" ||
        row.dataset.critical === "1" ||
        row.classList.contains("hc-case-row--critical") ||
        row.classList.contains("hc-request-row--critical");
    }
    if (filter === "attention") {
      return rowRisk(row) === "attention" || row.dataset.attention === "1";
    }
    if (filter === "assigned") {
      return normalize(row.dataset.owner) === "assigned" && !isTerminal(row);
    }
    if (filter === "no_owner") {
      return row.dataset.noOwner === "1" && !isTerminal(row);
    }
    if (filter === "stale_72h") {
      return row.dataset.stale === "1" || row.dataset.stale72h === "1";
    }
    if (filter === "unassigned_48h") {
      return row.dataset.unassigned48h === "1" ||
        String(row.dataset.sla || "").split(/\s+/).map(normalize).includes("owner_assignment_overdue");
    }
    if (filter === "inactive_cases") {
      return row.dataset.inactiveCase === "1";
    }
    return true;
  }

  function rowMatches(row) {
    if (state.tab && rowStatus(row) !== state.tab) return false;
    if (state.filter && !rowMatchesFilter(row, state.filter)) return false;
    return true;
  }

  function readUrl() {
    const params = new URLSearchParams(window.location.search);
    state.tab = normalizeTab(params.get("tab") || params.get("status"));
    state.filter = "";

    const setFilter = (value) => {
      const filter = normalizeFilter(value);
      if (filter) state.filter = filter;
    };

    params.getAll(FILTER_PARAM).forEach((value) => value.split(",").forEach(setFilter));
    params.getAll("filter").forEach((value) => value.split(",").forEach(setFilter));
    setFilter(params.get("risk_level"));
    if (params.get("no_owner") === "1") setFilter("no_owner");
    if (params.get("not_seen_72h") === "1") setFilter("stale_72h");
    if (params.get("queue") === "sla" && params.get("sla_kind") === "owner_assignment_overdue") {
      setFilter("unassigned_48h");
    }

    if (state.filter) state.tab = "";
  }

  function updateUrl() {
    const url = new URL(window.location.href);
    SERVER_PARAMS.forEach((param) => url.searchParams.delete(param));
    url.searchParams.delete("action");
    url.searchParams.delete("tab");
    url.searchParams.delete("status");

    if (state.filter) {
      url.searchParams.set(FILTER_PARAM, state.filter);
    } else if (state.tab) {
      url.searchParams.set("tab", state.tab);
    }

    window.history.pushState(
      { tab: state.tab, filter: state.filter },
      "",
      url.toString(),
    );
  }

  function setActive(control, active) {
    control.classList.toggle("is-active", active);
    control.setAttribute("aria-pressed", active ? "true" : "false");
    if (normalize(control.dataset.filterKey) === "status") {
      control.setAttribute("aria-current", active ? "true" : "false");
    }
  }

  function paint() {
    cards.forEach((card) => {
      const filter = cardFilter(card);
      const active = filter.tab
        ? state.tab === filter.tab && !state.filter
        : !!filter.filter && state.filter === filter.filter;
      setActive(card, active);
    });
  }

  function apply({ syncUrl = false } = {}) {
    let visibleCount = 0;

    rows.forEach((row) => {
      const visible = rowMatches(row);
      row.hidden = !visible;
      row.style.display = visible ? "" : "none";
      if (visible) row.style.removeProperty("display");
      else row.style.setProperty("display", "none", "important");
      row.classList.toggle("hc-filter-hidden", !visible);

      const cells = row.querySelectorAll("td");
      cells.forEach((cell) => {
        cell.style.display = visible ? "" : "none";
        if (visible) cell.style.removeProperty("display");
        else cell.style.setProperty("display", "none", "important");
      });

      row.setAttribute("aria-hidden", visible ? "false" : "true");
      if (visible) visibleCount += 1;
    });

    if (noMatch) noMatch.hidden = visibleCount !== 0;
    paint();
    if (syncUrl) updateUrl();
  }

  cards.forEach((card) => {
    card.addEventListener("click", (event) => {
      event.preventDefault();
      const filter = cardFilter(card);
      const sameTab = filter.tab && state.tab === filter.tab && !state.filter;
      const sameFilter = filter.filter && state.filter === filter.filter;

      state.tab = "";
      state.filter = "";
      if (!sameTab && filter.tab) state.tab = filter.tab;
      if (!sameFilter && filter.filter) state.filter = filter.filter;

      apply({ syncUrl: true });
    });
  });

  clearControls.forEach((control) => {
    control.addEventListener("click", (event) => {
      event.preventDefault();
      state.tab = "";
      state.filter = "";
      apply({ syncUrl: true });
    });
  });

  window.addEventListener("popstate", () => {
    readUrl();
    apply();
  });

  readUrl();
  apply();
})();
