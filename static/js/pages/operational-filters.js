(() => {
  const allowedPaths = ["/admin/requests", "/ops/workspace", "/ops/cases"];
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  if (!allowedPaths.includes(path)) return;

  const cards = Array.from(document.querySelectorAll("[data-hc-filter-card]"));
  const rows = Array.from(document.querySelectorAll("[data-hc-filter-row]"));
  if (!cards.length || !rows.length) return;

  const clearControls = Array.from(document.querySelectorAll("[data-hc-filter-clear]"));
  const tableFilters = window.hcAdminRequestsTableFilters;
  const noMatch = document.getElementById("hcOpsWorkspaceClientEmpty") || document.querySelector("[data-hc-filter-empty]");
  const activeFilter = document.querySelector("[data-hc-active-filter]");
  const visibleCountLabel = document.querySelector("[data-hc-visible-count]");
  const kpiCounts = Array.from(document.querySelectorAll("[data-ops-kpi-count]"));
  const FILTER_PARAMS = ["status", "risk", "risk_level", "owner", "no_owner", "stale_72h", "not_seen_72h", "sla", "queue", "sla_kind", "filter"];

  const state = { key: "", value: "" };
  const normalize = (value) => String(value || "").trim().toLowerCase().replace(/-/g, "_");

  const FILTER_LABELS = {
    "risk:critical": "Vue filtrée : situations critiques",
    "owner:none": "Vue filtrée : demandes non assignées",
    "stale:1": "Vue filtrée : sans activité 72h",
    "notification:failed": "Vue filtrée : notifications en échec",
    "updated:today": "Vue filtrée : mises à jour aujourd’hui",
  };

  const EMPTY_LABELS = {
    "risk:critical": "Aucune situation critique détectée",
    "owner:none": "Toutes les demandes sont attribuées",
    "stale:1": "Aucune demande sans activité détectée",
    "notification:failed": "Aucune notification en échec",
    "updated:today": "Aucune demande mise à jour aujourd’hui",
  };

  function rowStatus(row) {
    return normalize(row.dataset.statusBucket || row.dataset.hcStatusRow || row.dataset.status);
  }

  function isTerminal(row) {
    return ["completed", "closed", "done", "rejected", "cancelled", "canceled"].includes(rowStatus(row));
  }

  function rowMatches(row, key, value) {
    const filterKey = normalize(key);
    const filterValue = normalize(value);
    if (!filterKey || !filterValue) return true;

    if (filterKey === "status") return rowStatus(row) === filterValue;
    if (filterKey === "risk") {
      if (filterValue === "critical") {
        return normalize(row.dataset.risk) === "critical" || normalize(row.dataset.priority) === "critical" || normalize(row.dataset.priority) === "urgent";
      }
      if (filterValue === "attention") {
        return ["attention", "high", "eleve", "élevé", "warning"].includes(normalize(row.dataset.risk));
      }
      return normalize(row.dataset.risk) === filterValue;
    }
    if (filterKey === "owner") {
      if (filterValue === "none" || filterValue === "no_owner") {
        return ["none", "missing", "free", "0", ""].includes(normalize(row.dataset.owner)) && !isTerminal(row);
      }
      if (filterValue === "assigned") {
        return !["none", "missing", "free", "0", ""].includes(normalize(row.dataset.owner)) && !isTerminal(row);
      }
      return normalize(row.dataset.owner) === filterValue;
    }
    if (filterKey === "stale") return row.dataset.stale === "1" || normalize(row.dataset.stale) === filterValue;
    if (filterKey === "sla") return normalize(row.dataset.sla) === filterValue || normalize(row.dataset.sla).split(/\s+/).includes(filterValue);
    if (filterKey === "notification") return row.dataset.notificationFailed === "1";
    if (filterKey === "updated") return row.dataset.updatedToday === "1";
    return row.dataset[filterKey] === filterValue;
  }

  function activeFromUrl() {
    const params = new URLSearchParams(window.location.search);
    if (path === "/admin/requests") {
      const status = params.get("tab") || params.get("status");
      if (status) return { key: "status", value: statusToBucket(status) };
      if (params.get("risk_level")) return { key: "risk", value: params.get("risk_level") };
      if (params.get("no_owner") === "1") return { key: "owner", value: "none" };
      if (params.get("not_seen_72h") === "1") return { key: "stale", value: "1" };
      if (params.get("queue") === "sla" && params.get("sla_kind")) return { key: "sla", value: params.get("sla_kind") };
    }
    if (path === "/ops/cases") {
      if (params.get("risk")) return { key: "risk", value: params.get("risk") };
      if (params.get("owner") === "none") return { key: "owner", value: "none" };
      if (params.get("stale_72h") === "1") return { key: "stale", value: "1" };
    }
    const raw = params.get("filter");
    if (!raw) return { key: "", value: "" };

    const normalizedRaw = normalize(raw);

    const match = cards.find((card) => {
      const key = normalize(card.dataset.filterKey);
      const value = normalize(card.dataset.filterValue);
      return normalize(key + ":" + value) === normalizedRaw;
    });

    if (match) return cardState(match);

    if (normalizedRaw.includes(":")) {
      const parts = normalizedRaw.split(":");
      return {
        key: parts[0] || "",
        value: parts[1] || "",
      };
    }

    return { key: "filter", value: raw };
  }

  function statusToBucket(value) {
    const status = normalize(value).toUpperCase();
    const map = {
      PENDING: "NEW",
      OPEN: "NEW",
      NEW: "NEW",
      APPROVED: "IN_PROGRESS",
      IN_PROGRESS: "IN_PROGRESS",
      DONE: "COMPLETED",
      COMPLETED: "COMPLETED",
      REJECTED: "CLOSED",
      CANCELLED: "CLOSED",
      CANCELED: "CLOSED",
      CLOSED: "CLOSED",
    };
    return map[status] || status;
  }

  function cardState(card) {
    return {
      key: card.dataset.filterKey || "",
      value: card.dataset.filterValue || "",
    };
  }

  function setUrl() {
    const url = new URL(window.location.href);
    FILTER_PARAMS.forEach((param) => url.searchParams.delete(param));
    url.searchParams.delete("tab");

    if (state.key && state.value) {
      if (path === "/admin/requests") {
        if (state.key === "status") url.searchParams.set("tab", state.value);
        else if (state.key === "risk") url.searchParams.set("risk_level", state.value);
        else if (state.key === "owner" && state.value === "none") url.searchParams.set("no_owner", "1");
        else if (state.key === "stale") url.searchParams.set("not_seen_72h", "1");
        else if (state.key === "sla") {
          url.searchParams.set("queue", "sla");
          url.searchParams.set("sla_kind", state.value);
        } else if (state.key === "notification") url.searchParams.set("notification", state.value);
        else if (state.key === "updated") url.searchParams.set("updated", state.value);
        else url.searchParams.set("filter", state.key + ":" + state.value);
      } else if (path === "/ops/cases") {
        if (state.key === "risk") url.searchParams.set("risk", state.value);
        else if (state.key === "owner") url.searchParams.set("owner", state.value);
        else if (state.key === "stale") url.searchParams.set("stale_72h", "1");
        else if (state.key === "notification") url.searchParams.set("notification", state.value);
        else if (state.key === "updated") url.searchParams.set("updated", state.value);
        else url.searchParams.set("filter", state.key + ":" + state.value);
      } else {
        url.searchParams.set("filter", state.key + ":" + state.value);
      }
    }

    window.history.pushState({ key: state.key, value: state.value }, "", url.toString());
  }

  function paint() {
    cards.forEach((card) => {
      const current = cardState(card);
      const active = normalize(current.key) === normalize(state.key) && normalize(current.value) === normalize(state.value);
      card.classList.toggle("is-active", active);
      card.setAttribute("aria-pressed", active ? "true" : "false");
      if (card.dataset.hcFilterCard === "status") {
        card.setAttribute("aria-current", active ? "true" : "false");
      }
    });
  }

  function setVisible(row, visible) {
    if (tableFilters) return;
    row.hidden = !visible;
      row.style.setProperty("display", visible ? "table-row" : "none", "important");
    row.style.setProperty("display", visible ? "table-row" : "none", "important");
  }

  function updateKpiCounts() {
    kpiCounts.forEach((item) => {
      const raw = item.dataset.opsKpiCount || "";
      const parts = raw.split(":");
      const key = parts[0] || "";
      const value = parts.slice(1).join(":") || "";
      const sourceRows = Array.from(document.querySelectorAll("[data-hc-filter-row]"));
      const count = sourceRows.filter((row) => rowMatches(row, key, value)).length;
      item.textContent = String(count);
      item.classList.toggle("is-alert", count > 0);
    });
  }

  function updateActiveFilterLabel() {
    if (!activeFilter) return;

    const key = normalize(state.key);
    const value = normalize(state.value);
    const lookup = key + ":" + value;

    const label = FILTER_LABELS[lookup] || "";

    activeFilter.hidden = !label;
    activeFilter.textContent = label;
  }

  function apply({ syncUrl = false } = {}) {
    const predicate = (row) => rowMatches(row, state.key, state.value);
    let visibleCount = 0;

    if (tableFilters) {
      tableFilters.setPredicate("operationalCards", predicate);
    }

    visibleCount = 0;

    rows.forEach((row) => {
      const visible = predicate(row);
      setVisible(row, visible);
      row.hidden = !visible;
      row.style.setProperty("display", visible ? "table-row" : "none", "important");
      row.classList.toggle("hc-filter-hidden", !visible);
      row.setAttribute("aria-hidden", visible ? "false" : "true");

      if (visible) visibleCount += 1;
    });

    if (noMatch) {
      const key = normalize(state.key);
      const value = normalize(state.value);
      const lookup = key + ":" + value;
      const emptyTitle = noMatch.querySelector(".hc-empty-state__title");

      if (emptyTitle && EMPTY_LABELS[lookup]) {
        emptyTitle.textContent = EMPTY_LABELS[lookup];
      }

      noMatch.hidden = visibleCount > 0;
      noMatch.style.setProperty("display", visibleCount > 0 ? "none" : "table-row", "important");
    }
    updateKpiCounts();
    paint();
    updateActiveFilterLabel();

    if (visibleCountLabel) {
      const actualVisibleCount = Array.from(document.querySelectorAll("[data-hc-filter-row]"))
        .filter((row) => row.offsetParent !== null).length;

      visibleCountLabel.hidden = actualVisibleCount <= 0;

      visibleCountLabel.textContent =
        actualVisibleCount <= 1
          ? actualVisibleCount + " situation affichée"
          : actualVisibleCount + " situations affichées";
    }

    if (syncUrl) setUrl();
  }

  cards.forEach((card) => {
    card.addEventListener("click", (event) => {
      event.preventDefault();
      const next = cardState(card);
      const same = normalize(next.key) === normalize(state.key) && normalize(next.value) === normalize(state.value);
      state.key = same ? "" : next.key;
      state.value = same ? "" : next.value;
      apply({ syncUrl: true });
    });
  });

  clearControls.forEach((control) => {
    control.addEventListener("click", (event) => {
      event.preventDefault();
      state.key = "";
      state.value = "";
      apply({ syncUrl: true });
    });
  });

  window.addEventListener("popstate", () => {
    const next = activeFromUrl();
    state.key = next.key;
    state.value = next.value;
    apply();
  });

  const initial = activeFromUrl();
  state.key = initial.key;
  state.value = initial.value;
  apply();
})();
