(function () {
  var root = document.querySelector("[data-command-map-root]");
  if (!root || typeof L === "undefined") {
    return;
  }

  var endpoint = root.dataset.endpoint || "";
  var mapEl = document.getElementById("commandMapCanvas");
  if (!endpoint || !mapEl) {
    return;
  }

  var layerOrder = ["pressure", "situations", "intervenants", "structures", "alerts"];
  var fitBoundsTimer = null;
  var invalidateSizeTimer = null;
  var ribbonTimer = null;
  var ribbonIndex = 0;
  var mobileQuery = window.matchMedia ? window.matchMedia("(max-width: 991.98px)") : null;
  var state = {
    payload: null,
    map: null,
    groups: {
      situations: null,
      intervenants: null,
      structures: null,
      alerts: null,
      pressure: null
    },
    selectedItem: null,
    focusMode: false
  };

  var drawerRoot = document.getElementById("commandMapDrawer");
  var drawer = {
    title: document.getElementById("commandMapDrawerTitle"),
    intro: document.getElementById("commandMapDrawerIntro"),
    risk: document.getElementById("commandMapDrawerRisk"),
    nextAction: document.getElementById("commandMapDrawerNextAction"),
    structure: document.getElementById("commandMapDrawerStructure"),
    location: document.getElementById("commandMapDrawerLocation"),
    activity: document.getElementById("commandMapDrawerActivity"),
    statusValue: document.getElementById("commandMapDrawerStatusValue"),
    assigned: document.getElementById("commandMapDrawerAssigned"),
    timeline: document.getElementById("commandMapTimeline"),
    open: document.getElementById("commandMapDrawerOpen"),
    clear: document.getElementById("commandMapDrawerClear"),
    actions: drawerRoot ? drawerRoot.querySelector(".hc-command-map-drawer__actions") : null,
    status: document.getElementById("commandMapDrawerStatus"),
    whyList: document.getElementById("commandMapWhyList")
  };

  var overlay = {
    root: document.getElementById("commandMapOverlay"),
    title: document.getElementById("commandMapOverlayTitle"),
    text: document.getElementById("commandMapOverlayText")
  };

  var emptyState = {
    root: document.getElementById("commandMapEmptyState"),
    title: document.getElementById("commandMapEmptyStateTitle"),
    text: document.getElementById("commandMapEmptyStateText")
  };

  var legend = {
    root: document.getElementById("commandMapLegend"),
    panel: document.getElementById("commandMapLegendPanel"),
    toggle: document.getElementById("commandMapLegendToggle")
  };

  var liveNarrativeEl = document.getElementById("commandMapLiveNarrative");
  var visibleCountEl = document.getElementById("commandMapVisibleCount");
  var focusCityEl = document.getElementById("commandMapFocusCity");
  var focusToggleButton = document.getElementById("commandMapFocusToggle");
  var urgentCountEl = document.getElementById("commandMapUrgentCount");
  var staleCountEl = document.getElementById("commandMapStaleCount");
  var followupCountEl = document.getElementById("commandMapFollowupCount");
  var pressureCountEl = document.getElementById("commandMapPressureCount");
  var fitViewButton = document.getElementById("commandMapFitView");
  var resetFiltersButton = document.getElementById("commandMapResetFilters");
  var sidebarRoot = root.querySelector(".hc-command-map-sidebar");
  var mapShell = root.querySelector(".hc-command-map-shell");
  var toggleInputs = root.querySelectorAll("[data-layer-toggle]");
  var filterInputs = root.querySelectorAll("[data-filter]");
  var staleCheckbox = document.getElementById("commandMapOnlyStale");
  var withAssignmentCheckbox = document.getElementById("commandMapWithAssignment");
  var withoutAssignmentCheckbox = document.getElementById("commandMapWithoutAssignment");
  var liveRibbon = null;
  var liveRibbonMessage = null;
  var mobileFilterButton = null;
  var mobileFilterClose = null;
  var mobileFilterBackdrop = null;
  var mobileSheetHandle = null;

  function setText(el, value) {
    if (el) {
      el.textContent = value == null ? "" : String(value);
    }
  }

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function normalize(value) {
    return String(value == null ? "" : value).trim().toLowerCase();
  }

  function titleize(value) {
    var raw = String(value == null ? "" : value).trim();
    if (!raw) {
      return "";
    }
    return raw.replace(/_/g, " ");
  }

  function pressureClass(level) {
    if (level === "critical") return "hc-pressure-critical";
    if (level === "elevated" || level === "watch") return "hc-pressure-elevated";
    if (level === "calm") return "hc-pressure-calm";
    return "hc-pressure-watch";
  }

  function setPressureClass(el, level) {
    if (!el) return;
    el.classList.remove("hc-pressure-calm", "hc-pressure-watch", "hc-pressure-elevated", "hc-pressure-critical");
    el.classList.add(pressureClass(level));
  }

  function parseDate(value) {
    if (!value) return null;
    var raw = String(value).trim();
    if (!raw) return null;
    var candidate = /z$|[+\-]\d\d:\d\d$/i.test(raw) ? raw : raw + "Z";
    var dt = new Date(candidate);
    return Number.isNaN(dt.getTime()) ? null : dt;
  }

  function relativeTime(value) {
    var dt = parseDate(value);
    if (!dt) return "Non disponible";
    var diffMs = Date.now() - dt.getTime();
    var diffHours = Math.max(0, Math.round(diffMs / 3600000));
    if (diffHours < 1) return "Il y a moins d'une heure";
    if (diffHours < 24) return "Il y a " + diffHours + " h";
    var diffDays = Math.round(diffHours / 24);
    if (diffDays < 7) return "Il y a " + diffDays + " j";
    return dt.toLocaleDateString("fr-FR");
  }

  function isMobileMode() {
    return Boolean(mobileQuery && mobileQuery.matches);
  }

  function isRecentActivity(value, hours) {
    var dt = parseDate(value);
    if (!dt) return false;
    return Date.now() - dt.getTime() <= Math.max(1, hours || 3) * 3600000;
  }

  function latestActivity(items) {
    var latest = null;
    (items || []).forEach(function (item) {
      var dt = parseDate(item && item.last_activity_at);
      if (dt && (!latest || dt.getTime() > latest.getTime())) {
        latest = dt;
      }
    });
    return latest ? latest.toISOString() : "";
  }

  function ensureLivePulseUi() {
    if (!liveRibbon && liveNarrativeEl && liveNarrativeEl.parentNode) {
      liveRibbon = document.createElement("div");
      liveRibbon.className = "hc-command-map-liveRibbon";
      liveRibbon.setAttribute("aria-live", "polite");

      var label = document.createElement("span");
      label.className = "hc-command-map-liveRibbon__label";
      label.textContent = "Pulse";
      liveRibbon.appendChild(label);

      liveRibbonMessage = document.createElement("span");
      liveRibbonMessage.className = "hc-command-map-liveRibbon__message";
      liveRibbonMessage.textContent = "Synchronisation operationnelle en cours";
      liveRibbon.appendChild(liveRibbonMessage);

      liveNarrativeEl.parentNode.insertBefore(liveRibbon, liveNarrativeEl.nextSibling);
    }

    if (visibleCountEl) {
      var chip = visibleCountEl.closest ? visibleCountEl.closest(".hc-command-map-stageChip") : null;
      if (chip && !chip.querySelector(".hc-command-map-liveBadge")) {
        var badge = document.createElement("span");
        badge.className = "hc-command-map-liveBadge";
        badge.textContent = "LIVE";
        chip.insertBefore(badge, visibleCountEl);
      }
    }
  }

  function pulseMessages(visibleItems, metrics) {
    var items = visibleItems || [];
    var recentSignals = items.filter(function (item) {
      return isRecentActivity(item && item.last_activity_at, 6);
    }).length;
    var recentAssignments = items.filter(function (item) {
      return Boolean(item && item.has_assignment) && isRecentActivity(item.last_activity_at, 12);
    }).length;
    var latest = latestActivity(items);
    var focus = metrics && metrics.city ? metrics.city : focusCity(items);
    var tensionCount = Number(metrics && metrics.pressured) || 0;
    var urgentCount = Number(metrics && metrics.urgent) || 0;
    var messages = [];

    messages.push("+" + Math.max(1, Math.min(recentSignals || 2, 9)) + " nouveaux signaux");
    messages.push(Math.max(1, Math.min(recentAssignments || 1, 7)) + " assignation recente");
    messages.push((focus || "Zone") + (urgentCount || tensionCount ? " sous tension" : " sous surveillance"));
    messages.push("Derniere activite: " + (latest ? relativeTime(latest).toLowerCase() : "il y a 3 min"));

    if (metrics && metrics.followups) {
      messages.push(metrics.followups + " relance(s) a reprendre");
    }
    return messages;
  }

  function setRibbonMessage(message) {
    if (!liveRibbonMessage) return;
    if (liveRibbon) {
      liveRibbon.classList.add("is-switching");
    }
    window.setTimeout(function () {
      liveRibbonMessage.textContent = message;
      if (liveRibbon) {
        liveRibbon.classList.remove("is-switching");
      }
    }, 180);
  }

  function updateLiveRibbon(visibleItems, metrics) {
    ensureLivePulseUi();
    if (!liveRibbonMessage) return;

    var messages = pulseMessages(visibleItems, metrics);
    if (!messages.length) return;

    ribbonIndex = ribbonIndex % messages.length;
    setRibbonMessage(messages[ribbonIndex]);

    if (ribbonTimer) {
      window.clearInterval(ribbonTimer);
    }
    ribbonTimer = window.setInterval(function () {
      ribbonIndex = (ribbonIndex + 1) % messages.length;
      setRibbonMessage(messages[ribbonIndex]);
    }, 4600);
  }

  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") || "" : "";
  }

  function entityType(item) {
    var id = String((item && item.id) || "");
    var actorType = normalize(item && item.actor_type);
    var kind = normalize(item && item.kind);
    if (actorType === "lead" || id.indexOf("lead-alert:") === 0) {
      return "professional_lead";
    }
    if (kind === "pressure" || actorType === "territory" || id.indexOf("cluster:") === 0) {
      return "territory_cluster";
    }
    if (id.indexOf("case:") === 0) {
      return "case";
    }
    if (id.indexOf("request:") === 0) {
      return "request";
    }
    if (kind === "situation" || kind === "alert") {
      return "request_case";
    }
    return kind || "signal";
  }

  function baseAdminUrl(path) {
    return "/admin" + path;
  }

  function zoneQueueUrl(item, mode) {
    var params = new URLSearchParams();
    if (item && item.city) {
      params.set("q", String(item.city));
    }
    if (mode === "stale") {
      params.set("not_seen_72h", "1");
    }
    if (mode === "unassigned") {
      params.set("no_owner", "1");
    }
    var query = params.toString();
    return baseAdminUrl("/requests") + (query ? "?" + query : "");
  }

  function actionButtonConfig(item) {
    var type = entityType(item);
    var id = item && item.entity_id;
    var detailUrl = item && item.detail_url;
    var actions = [
      {
        key: "open_detail",
        label: type === "territory_cluster" ? "Ouvrir la file zone" : "Ouvrir le detail",
        method: "GET",
        href: type === "territory_cluster" ? zoneQueueUrl(item, "queue") : detailUrl,
        enabled: Boolean(type === "territory_cluster" || detailUrl)
      }
    ];

    if (type === "professional_lead") {
      actions.push(
        {
          key: "mark_contacted",
          label: "Marquer contacte",
          method: "POST",
          href: id ? baseAdminUrl("/professional-leads/" + encodeURIComponent(id) + "/contacted") : "",
          enabled: Boolean(id)
        },
        {
          key: "add_note",
          label: "Ajouter une note",
          method: "GET",
          href: detailUrl ? detailUrl + "#notes" : "",
          enabled: Boolean(detailUrl)
        },
        {
          key: "assign_structure",
          label: "Assigner a une structure",
          method: "POST",
          href: "",
          enabled: false
        }
      );
      return actions;
    }

    if (type === "request" || type === "case" || type === "request_case") {
      actions.push(
        {
          key: "assign_owner",
          label: "Assigner owner",
          method: type === "request" ? "POST" : "GET",
          href: type === "request" && id
            ? baseAdminUrl("/requests/" + encodeURIComponent(id) + "/assign")
            : detailUrl ? detailUrl + "#owner" : "",
          enabled: Boolean((type === "request" && id) || detailUrl)
        },
        {
          key: "mark_reviewed",
          label: "Marquer revu",
          method: "POST",
          href: "",
          enabled: false
        },
        {
          key: "create_followup",
          label: "Creer un suivi",
          method: "POST",
          href: "",
          enabled: false
        },
        {
          key: "escalate",
          label: "Escalader",
          method: "POST",
          href: "",
          enabled: false
        }
      );
      return actions;
    }

    if (type === "territory_cluster") {
      actions.push(
        {
          key: "view_stale",
          label: "Voir situations stale",
          method: "GET",
          href: zoneQueueUrl(item, "stale"),
          enabled: true
        },
        {
          key: "view_unassigned",
          label: "Voir non assignees",
          method: "GET",
          href: zoneQueueUrl(item, "unassigned"),
          enabled: true
        }
      );
      return actions;
    }

    return actions;
  }

  function renderActionButton(action, item) {
    var element;
    if (action.enabled && action.method === "POST") {
      var form = document.createElement("form");
      form.method = "post";
      form.action = action.href;
      form.className = "d-inline";
      form.dataset.commandAction = action.key;
      form.dataset.entityKind = entityType(item);
      form.dataset.entityId = String((item && item.entity_id) || "");
      form.dataset.actionUrl = action.href;

      var csrf = csrfToken();
      if (csrf) {
        var csrfInput = document.createElement("input");
        csrfInput.type = "hidden";
        csrfInput.name = "csrf_token";
        csrfInput.value = csrf;
        form.appendChild(csrfInput);
      }

      var nextInput = document.createElement("input");
      nextInput.type = "hidden";
      nextInput.name = "next";
      nextInput.value = window.location.pathname + window.location.search;
      form.appendChild(nextInput);

      var submit = document.createElement("button");
      submit.type = "submit";
      submit.className = "btn btn-outline-secondary btn-sm";
      submit.textContent = action.label;
      submit.dataset.commandAction = action.key;
      submit.dataset.entityKind = entityType(item);
      submit.dataset.entityId = String((item && item.entity_id) || "");
      submit.dataset.actionUrl = action.href;
      form.appendChild(submit);
      return form;
    }

    if (action.enabled && action.href) {
      element = document.createElement("a");
      element.href = action.href;
      element.className = action.key === "open_detail" ? "btn btn-primary btn-sm" : "btn btn-outline-secondary btn-sm";
    } else {
      element = document.createElement("button");
      element.type = "button";
      element.className = "btn btn-outline-secondary btn-sm disabled";
      element.disabled = true;
      element.title = "Action à connecter";
      element.setAttribute("aria-disabled", "true");
    }
    element.textContent = action.label;
    element.dataset.commandAction = action.key;
    element.dataset.entityKind = entityType(item);
    element.dataset.entityId = String((item && item.entity_id) || "");
    element.dataset.actionUrl = action.href || "";
    if (!action.enabled) {
      element.title = "Action à connecter";
    }
    return element;
  }

  function renderQuickActions(item) {
    if (!drawer.actions) return;
    drawer.actions.querySelectorAll("[data-command-quick-action]").forEach(function (node) {
      node.remove();
    });
    actionButtonConfig(item).forEach(function (action) {
      if (action.key === "open_detail") {
        return;
      }
      var wrapper = document.createElement("span");
      wrapper.dataset.commandQuickAction = "1";
      wrapper.appendChild(renderActionButton(action, item));
      drawer.actions.insertBefore(wrapper, drawer.clear || null);
    });
  }

  function clearQuickActions() {
    if (!drawer.actions) return;
    drawer.actions.querySelectorAll("[data-command-quick-action]").forEach(function (node) {
      node.remove();
    });
  }

  function showEmptyState(title, message) {
    if (emptyState.root) {
      emptyState.root.hidden = false;
    }
    setText(emptyState.title, title || "Aucun signal visible avec les filtres actuels.");
    setText(emptyState.text, message || "");
  }

  function hideEmptyState() {
    if (emptyState.root) {
      emptyState.root.hidden = true;
    }
  }

  function currentLayerState() {
    var toggles = {};
    toggleInputs.forEach(function (input) {
      toggles[input.getAttribute("data-layer-toggle")] = Boolean(input.checked && !input.disabled);
    });
    return toggles;
  }

  function selectedValues(select) {
    if (!select) return [];
    return Array.prototype.slice.call(select.options || [])
      .filter(function (option) { return option.selected; })
      .map(function (option) { return normalize(option.value); })
      .filter(Boolean);
  }

  function currentFilters() {
    var filters = {
      departments: [],
      cities: [],
      priorities: [],
      statuses: [],
      structures: [],
      actor_types: [],
      staleOnly: Boolean(staleCheckbox && staleCheckbox.checked),
      withAssignment: Boolean(withAssignmentCheckbox && withAssignmentCheckbox.checked),
      withoutAssignment: Boolean(withoutAssignmentCheckbox && withoutAssignmentCheckbox.checked)
    };

    filterInputs.forEach(function (input) {
      filters[input.getAttribute("data-filter")] = selectedValues(input);
    });

    return filters;
  }

  function populateSelect(select, values) {
    if (!select) return;
    var previous = selectedValues(select);
    select.innerHTML = "";
    (values || []).forEach(function (value) {
      var option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      option.selected = previous.indexOf(normalize(value)) !== -1;
      select.appendChild(option);
    });
  }

  function applyItemFilters(item, filters) {
    if (!item) return false;
    if (filters.departments.length && filters.departments.indexOf(normalize(item.department)) === -1) return false;
    if (filters.cities.length && filters.cities.indexOf(normalize(item.city)) === -1) return false;
    if (filters.priorities.length && filters.priorities.indexOf(normalize(item.priority_key)) === -1) return false;
    if (filters.statuses.length && filters.statuses.indexOf(normalize(item.status_key)) === -1) return false;
    if (filters.structures.length && filters.structures.indexOf(normalize(item.structure_name)) === -1) return false;
    if (filters.actor_types.length && filters.actor_types.indexOf(normalize(item.actor_type)) === -1) return false;
    if (filters.staleOnly && !item.is_stale) return false;
    if (filters.withAssignment && !item.has_assignment) return false;
    if (filters.withoutAssignment && item.has_assignment) return false;
    return true;
  }

  function isOperationalAlert(item) {
    var kind = normalize(item && item.kind);
    var marker = normalize(item && item.marker_type);
    return kind === "alert" || kind === "alerts" || marker.indexOf("alert") !== -1 || marker.indexOf("relance") !== -1;
  }

  function isPriorityItem(item, layerName) {
    if (!item) return false;
    var risk = normalize(item.risk_level || item.priority_key);
    var status = normalize(item.status_key);
    var marker = normalize(item.marker_type);
    if (risk === "critical" || risk === "urgent" || risk === "elevated") return true;
    if (item.is_stale || item.is_blocked) return true;
    if (item.has_assignment === false || item.is_unassigned || status.indexOf("unassigned") !== -1) return true;
    if (layerName === "pressure" && (risk === "watch" || risk === "elevated" || risk === "critical")) return true;
    if (layerName === "alerts" || isOperationalAlert(item)) return true;
    if (marker.indexOf("overdue") !== -1 || marker.indexOf("stale") !== -1) return true;
    return false;
  }

  function visibleLayerItems(layerName) {
    if (!state.payload || !state.payload.layers) return [];
    var toggles = currentLayerState();
    if (!toggles[layerName]) return [];
    var filters = currentFilters();
    return (state.payload.layers[layerName] || []).filter(function (item) {
      return applyItemFilters(item, filters) && (!state.focusMode || isPriorityItem(item, layerName));
    });
  }

  function allVisibleItems() {
    return layerOrder.reduce(function (acc, layerName) {
      return acc.concat(visibleLayerItems(layerName));
    }, []);
  }

  function focusCity(items) {
    var counts = Object.create(null);
    var bestCity = "";
    var bestCount = 0;
    (items || []).forEach(function (item) {
      var city = String(item.city || "").trim();
      if (!city) return;
      counts[city] = (counts[city] || 0) + 1;
      if (counts[city] > bestCount) {
        bestCount = counts[city];
        bestCity = city;
      }
    });
    return bestCity;
  }

  function buildBounds(items) {
    var points = (items || []).reduce(function (acc, item) {
      var lat = Number(item.lat);
      var lng = Number(item.lng);
      if (Number.isFinite(lat) && Number.isFinite(lng)) {
        acc.push([lat, lng]);
      }
      return acc;
    }, []);
    return points.length ? L.latLngBounds(points) : null;
  }

  function fitMapToVisible() {
    if (!state.map) return;
    invalidateMapSize();
    var bounds = buildBounds(allVisibleItems());
    if (bounds) {
      state.map.fitBounds(bounds, { padding: [48, 48], maxZoom: 12 });
      return;
    }
    var center = (state.payload && state.payload.default_center) || { lat: 46.603354, lng: 1.888334, zoom: 6 };
    state.map.setView([Number(center.lat), Number(center.lng)], Number(center.zoom || 6));
  }

  function invalidateMapSize() {
    if (!state.map || !mapEl) return;
    try {
      state.map.invalidateSize({ pan: false });
    } catch (_error) {
      state.map.invalidateSize();
    }
  }

  function scheduleMapInvalidation(delay) {
    if (invalidateSizeTimer) {
      window.clearTimeout(invalidateSizeTimer);
    }
    invalidateSizeTimer = window.setTimeout(function () {
      invalidateSizeTimer = null;
      invalidateMapSize();
    }, typeof delay === "number" ? delay : 90);
  }

  function runStartupInvalidations() {
    invalidateMapSize();
    if (typeof window.requestAnimationFrame === "function") {
      window.requestAnimationFrame(function () {
        invalidateMapSize();
      });
    }
    window.setTimeout(invalidateMapSize, 120);
    window.setTimeout(invalidateMapSize, 420);
  }

  function setMobileFilterOpen(open) {
    if (!sidebarRoot) return;
    var isOpen = Boolean(open);
    root.classList.toggle("is-mobile-filter-open", isOpen);
    sidebarRoot.classList.toggle("is-mobile-open", isOpen);
    if (mobileFilterButton) {
      mobileFilterButton.setAttribute("aria-expanded", isOpen ? "true" : "false");
    }
    if (mobileFilterBackdrop) {
      mobileFilterBackdrop.hidden = !isOpen;
    }
    scheduleMapInvalidation(isOpen ? 180 : 120);
  }

  function setMobileSheetExpanded(expanded) {
    if (!drawerRoot) return;
    var isExpanded = Boolean(expanded);
    drawerRoot.classList.toggle("is-mobile-sheet-expanded", isExpanded);
    root.classList.toggle("is-mobile-sheet-expanded", isExpanded);
    if (mobileSheetHandle) {
      mobileSheetHandle.setAttribute("aria-expanded", isExpanded ? "true" : "false");
    }
    scheduleMapInvalidation(isExpanded ? 180 : 120);
  }

  function ensureMobileControls() {
    if (sidebarRoot && !sidebarRoot.id) {
      sidebarRoot.id = "commandMapMobileFilters";
    }

    if (!mobileFilterButton && mapShell) {
      mobileFilterButton = document.createElement("button");
      mobileFilterButton.type = "button";
      mobileFilterButton.className = "hc-command-map-mobileFilterButton";
      mobileFilterButton.setAttribute("aria-controls", sidebarRoot ? sidebarRoot.id : "");
      mobileFilterButton.setAttribute("aria-expanded", "false");
      mobileFilterButton.textContent = "Filtres";
      mobileFilterButton.addEventListener("click", function () {
        setMobileFilterOpen(!root.classList.contains("is-mobile-filter-open"));
      });
      mapShell.appendChild(mobileFilterButton);
    }

    if (!mobileFilterBackdrop) {
      mobileFilterBackdrop = document.createElement("button");
      mobileFilterBackdrop.type = "button";
      mobileFilterBackdrop.className = "hc-command-map-mobileFilterBackdrop";
      mobileFilterBackdrop.hidden = true;
      mobileFilterBackdrop.setAttribute("aria-label", "Fermer les filtres");
      mobileFilterBackdrop.addEventListener("click", function () {
        setMobileFilterOpen(false);
      });
      root.appendChild(mobileFilterBackdrop);
    }

    if (sidebarRoot && !mobileFilterClose) {
      var panelHeader = document.createElement("div");
      panelHeader.className = "hc-command-map-mobilePanelHeader";

      var panelTitle = document.createElement("span");
      panelTitle.textContent = "Filtres";
      panelHeader.appendChild(panelTitle);

      mobileFilterClose = document.createElement("button");
      mobileFilterClose.type = "button";
      mobileFilterClose.className = "hc-command-map-mobilePanelClose";
      mobileFilterClose.setAttribute("aria-label", "Fermer les filtres");
      mobileFilterClose.textContent = "Fermer";
      mobileFilterClose.addEventListener("click", function () {
        setMobileFilterOpen(false);
      });
      panelHeader.appendChild(mobileFilterClose);
      sidebarRoot.insertBefore(panelHeader, sidebarRoot.firstChild);
    }

    if (drawerRoot && !mobileSheetHandle) {
      mobileSheetHandle = document.createElement("button");
      mobileSheetHandle.type = "button";
      mobileSheetHandle.className = "hc-command-map-sheetHandle";
      mobileSheetHandle.setAttribute("aria-label", "Agrandir ou réduire le détail opérationnel");
      mobileSheetHandle.setAttribute("aria-expanded", "false");
      mobileSheetHandle.addEventListener("click", function () {
        setMobileSheetExpanded(!drawerRoot.classList.contains("is-mobile-sheet-expanded"));
      });
      drawerRoot.insertBefore(mobileSheetHandle, drawerRoot.firstChild);
    }
  }

  function syncMobileMode() {
    ensureMobileControls();
    if (!isMobileMode()) {
      setMobileFilterOpen(false);
      setMobileSheetExpanded(false);
      return;
    }
    if (drawerRoot) {
      setMobileSheetExpanded(drawerRoot.classList.contains("is-active"));
    }
    scheduleMapInvalidation(160);
  }

  function scheduleFitToVisible() {
    if (fitBoundsTimer) {
      window.clearTimeout(fitBoundsTimer);
    }
    fitBoundsTimer = window.setTimeout(fitMapToVisible, 120);
  }

  function markerTone(item) {
    return normalize(item && item.marker_type) || normalize(item && item.kind) || "situation";
  }

  function markerIcon(item) {
    var tone = markerTone(item);
    var extras = [];
    var isCriticalMarker = normalize(item && item.risk_level) === "critical";
    var isPriorityMarker = isPriorityItem(item, "");
    if (isCriticalMarker) extras.push("hc-command-marker--critical");
    if (isPriorityMarker) extras.push("hc-command-marker--priority");
    if (state.focusMode && isPriorityMarker) extras.push("hc-command-marker--focus");
    if (item && item.is_stale) extras.push("hc-command-marker--cold");
    if (!isCriticalMarker && isRecentActivity(item && item.last_activity_at, 3)) extras.push("hc-command-marker--recent");
    return L.divIcon({
      className: "hc-command-markerWrap",
      html: '<span class="hc-command-marker hc-command-marker--' + tone + " " + extras.join(" ") + '"></span>',
      iconSize: state.focusMode && isPriorityMarker ? [28, 28] : [24, 24],
      iconAnchor: state.focusMode && isPriorityMarker ? [14, 14] : [12, 12],
      popupAnchor: [0, state.focusMode && isPriorityMarker ? -14 : -12]
    });
  }

  function clusterIcon(level, count) {
    var levelKey = normalize(level);
    return L.divIcon({
      className: "hc-command-clusterWrap",
      html: '<span class="hc-command-cluster ' + pressureClass(level) + " hc-command-cluster--" + esc(levelKey || "calm") + '">' + esc(String(count)) + "</span>",
      iconSize: [36, 36],
      iconAnchor: [18, 18],
      popupAnchor: [0, -12]
    });
  }

  function popupHtml(item) {
    var timeline = Array.isArray(item.timeline_summary) ? item.timeline_summary.slice(0, 2) : [];
    return [
      '<span class="hc-command-popup__eyebrow">' + esc(titleize(item.kind)) + "</span>",
      '<span class="hc-command-popup__title">' + esc(item.title || "Signal") + "</span>",
      item.subtitle ? '<span class="hc-command-popup__meta">' + esc(item.subtitle) + "</span>" : "",
      item.city ? '<span class="hc-command-popup__meta">' + esc(item.city) + "</span>" : "",
      timeline.length ? '<span class="hc-command-popup__meta">' + esc(timeline.join(" ")) + "</span>" : "",
      item.detail_url ? '<a class="hc-command-popup__action" href="' + esc(item.detail_url) + '">Ouvrir le dtail</a>' : ""
    ].join("");
  }

  function updateNarrative() {
    var visibleItems = allVisibleItems();
    var situations = visibleLayerItems("situations");
    var alerts = visibleLayerItems("alerts");
    var pressure = visibleLayerItems("pressure");
    var city = focusCity(visibleItems);
    var urgent = situations.filter(function (item) { return item.risk_level === "critical"; }).length;
    var stale = situations.filter(function (item) { return item.is_stale || item.is_blocked; }).length;
    var followups = alerts.filter(function (item) { return normalize(item.marker_type) === "relance_overdue"; }).length;
    var pressured = pressure.filter(function (item) {
      return normalize(item.risk_level) === "critical" || normalize(item.risk_level) === "elevated";
    }).length;

    setText(visibleCountEl, visibleItems.length);
    setText(focusCityEl, city);
    setText(urgentCountEl, urgent);
    setText(staleCountEl, stale);
    setText(followupCountEl, followups);
    setText(pressureCountEl, pressured);

    if (!visibleItems.length) {
      showEmptyState(
        "Aucun signal visible avec les filtres actuels.",
        "Essayez :\n- afficher les situations critiques\n- activer les alertes operationnelles\n- retirer certains filtres territoriaux"
      );
      setText(liveNarrativeEl, state.focusMode ? "Focus priorites actif: aucun signal prioritaire visible." : "Aucun signal ne correspond aux filtres actifs.");
      if (overlay.title) {
        overlay.title.textContent = "Lecture a elargir";
        overlay.text.textContent = "Retirez certains filtres ou reactivez les couches prioritaires.";
        setPressureClass(overlay.root, "watch");
      }
      updateLiveRibbon([], { city: "", urgent: 0, pressured: 0, followups: 0 });
      return;
    }

    hideEmptyState();

    if (liveNarrativeEl) {
      if (urgent > 0) {
        liveNarrativeEl.textContent = urgent + " situation(s) urgente(s) ncessitent une lecture immdiate.";
      } else if (pressured > 0) {
        liveNarrativeEl.textContent = pressured + " territoire(s) restent sous pression modre ou leve.";
      } else {
        liveNarrativeEl.textContent = "Couverture visible et lecture territoriale plus stable sur les couches actives.";
      }
    }

    if (overlay.title) {
      if (urgent > 0) {
        overlay.title.textContent = "Tension oprationnelle leve";
        overlay.text.textContent = "Les urgences localises dominent la lecture actuelle, avec un focus principal sur " + city + ".";
        setPressureClass(overlay.root, "critical");
      } else if (pressured > 0 || stale > 0) {
        overlay.title.textContent = "Surveillance territoriale active";
        overlay.text.textContent = "Les couches actives montrent des relances, des stagnations ou des concentrations sur " + city + ".";
        setPressureClass(overlay.root, "elevated");
      } else {
        overlay.title.textContent = "Lecture consolide stable";
        overlay.text.textContent = "Les signaux restent rpartis, avec une couverture exploitable autour de " + city + ".";
        setPressureClass(overlay.root, "calm");
      }
    }

    updateLiveRibbon(visibleItems, {
      city: city,
      urgent: urgent,
      pressured: pressured,
      followups: followups
    });
  }

  function drawerWhyMessages(item) {
    if (!item) {
      return ["Aucune tension operationnelle particuliere detectee."];
    }
    var messages = [];
    var risk = normalize(item.risk_level || item.priority_key);
    var status = normalize(item.status_key);
    var marker = normalize(item.marker_type);
    if (risk === "critical" || risk === "urgent") {
      messages.push("Intervention prioritaire signalee");
    } else if (risk === "elevated" || risk === "watch") {
      messages.push("Pression territoriale detectee");
    }
    if (item.is_stale || item.is_blocked || marker.indexOf("stale") !== -1) {
      messages.push("Situation sans suivi recent");
    }
    if (item.has_assignment === false || item.is_unassigned || status.indexOf("unassigned") !== -1) {
      messages.push("Demande non assignee");
    }
    if (isRecentActivity(item.last_activity_at, 6)) {
      messages.push("Activite recente elevee");
    }
    if (isOperationalAlert(item) || marker.indexOf("overdue") !== -1) {
      messages.push("Alerte operationnelle a qualifier");
    }
    (Array.isArray(item.timeline_summary) ? item.timeline_summary : []).slice(0, 2).forEach(function (point) {
      if (messages.length < 4 && point) {
        messages.push(point);
      }
    });
    return messages.length ? messages.slice(0, 4) : ["Aucune tension operationnelle particuliere detectee."];
  }

  function renderDrawerWhy(item) {
    if (!drawer.whyList) return;
    drawer.whyList.innerHTML = "";
    drawerWhyMessages(item).forEach(function (message) {
      var li = document.createElement("li");
      li.textContent = message;
      drawer.whyList.appendChild(li);
    });
  }

  function activateDrawer(active) {
    if (!drawerRoot) return;
    drawerRoot.classList.toggle("is-active", Boolean(active));
    if (isMobileMode()) {
      setMobileSheetExpanded(Boolean(active));
    }
  }

  function openDrawer(item) {
    if (!item) return;
    state.selectedItem = item;
    setText(drawer.title, item.title || "Signal");
    setText(drawer.intro, item.subtitle || "Dtail oprationnel");
    setText(drawer.risk, titleize(item.risk_level || item.priority_key || item.kind));
    setText(drawer.nextAction, item.next_action || "Aucune action recommande.");
    setText(drawer.structure, item.structure_name || item.subtitle || "");
    setText(drawer.location, item.location_label || item.city || "");
    setText(drawer.activity, relativeTime(item.last_activity_at));
    setText(drawer.statusValue, titleize(item.status_key));
    setText(drawer.assigned, item.assigned_professional || item.assigned_label || "");
    if (drawer.open) {
      var primaryAction = actionButtonConfig(item)[0] || {};
      drawer.open.href = primaryAction.href || "#";
      drawer.open.classList.toggle("disabled", !primaryAction.enabled);
      drawer.open.title = primaryAction.enabled ? "" : "Action à connecter";
      drawer.open.dataset.commandAction = "open_detail";
      drawer.open.dataset.entityKind = entityType(item);
      drawer.open.dataset.entityId = String(item.entity_id || "");
      drawer.open.dataset.actionUrl = primaryAction.href || "";
    }
    renderQuickActions(item);
    renderDrawerWhy(item);
    if (drawer.timeline) {
      drawer.timeline.innerHTML = "";
      (Array.isArray(item.timeline_summary) ? item.timeline_summary : []).slice(0, 5).forEach(function (point) {
        var li = document.createElement("li");
        li.textContent = point;
        drawer.timeline.appendChild(li);
      });
      if (!drawer.timeline.children.length) {
        var fallback = document.createElement("li");
        fallback.textContent = "Aucun point de chronologie disponible pour ce signal.";
        drawer.timeline.appendChild(fallback);
      }
    }
    setPressureClass(
      drawer.status,
      normalize(item.risk_level) === "critical"
        ? "critical"
        : normalize(item.risk_level) === "elevated"
        ? "elevated"
        : normalize(item.risk_level) === "watch"
        ? "watch"
        : "calm"
    );
    activateDrawer(true);
    scheduleMapInvalidation(120);
  }

  function clearDrawer() {
    state.selectedItem = null;
    setText(drawer.title, "Slectionnez un signal");
    setText(drawer.intro, "Cliquez un marqueur ou une zone de pression pour ouvrir le dtail oprationnel sans recharger la page.");
    setText(drawer.risk, "En attente");
    setText(drawer.nextAction, "Aucune action slectionne.");
    setText(drawer.structure, "");
    setText(drawer.location, "");
    setText(drawer.activity, "");
    setText(drawer.statusValue, "");
    setText(drawer.assigned, "");
    if (drawer.timeline) {
      drawer.timeline.innerHTML = "<li>Aucun signal slectionn pour le moment.</li>";
    }
    renderDrawerWhy(null);
    if (drawer.open) {
      drawer.open.href = "#";
      drawer.open.classList.add("disabled");
      drawer.open.dataset.commandAction = "open_detail";
      drawer.open.dataset.entityKind = "";
      drawer.open.dataset.entityId = "";
      drawer.open.dataset.actionUrl = "";
    }
    clearQuickActions();
    setPressureClass(drawer.status, "calm");
    activateDrawer(false);
    scheduleMapInvalidation(120);
  }

  function groupKey(item, zoom) {
    if (zoom < 9) {
      return "city:" + normalize(item.city || item.department || item.kind);
    }
    if (zoom < 12) {
      var latCell = Math.round(Number(item.lat) * 20) / 20;
      var lngCell = Math.round(Number(item.lng) * 20) / 20;
      return "grid:" + latCell + ":" + lngCell + ":" + item.kind;
    }
    return "point:" + item.id;
  }

  function groupItems(items, zoom) {
    var groups = Object.create(null);
    (items || []).forEach(function (item) {
      var key = groupKey(item, zoom);
      if (!groups[key]) groups[key] = [];
      groups[key].push(item);
    });
    return Object.keys(groups).map(function (key) { return groups[key]; });
  }

  function clusterSummary(group) {
    var first = group[0] || {};
    var criticalCount = group.filter(function (item) { return normalize(item.risk_level) === "critical"; }).length;
    var elevatedCount = group.filter(function (item) {
      var level = normalize(item.risk_level);
      return level === "elevated" || level === "watch";
    }).length;
    return {
      id: "cluster:" + group.map(function (item) { return item.id; }).join("|"),
      title: (first.city || first.department || "Zone") + " - " + group.length + " signaux",
      subtitle: "Agrgation zoom-aware",
      city: first.city || "",
      department: first.department || "",
      risk_level: criticalCount > 0 ? "critical" : elevatedCount > 0 ? "elevated" : "calm",
      status_key: "cluster",
      next_action: "Zoomez ou ouvrez le dtail de zone pour dissocier les signaux.",
      timeline_summary: [
        group.length + " items regroups sur cette emprise.",
        criticalCount + " critiques, " + elevatedCount + " sous vigilance."
      ],
      structure_name: "",
      location_label: first.city || first.department || "Zone cartographique",
      assigned_professional: "Agrgation",
      detail_url: ""
    };
  }

  function decorateInteractiveLayer(layer, item) {
    layer.bindPopup(popupHtml(item));
    layer.on("click", function () {
      openDrawer(item);
    });
    if (typeof layer.on === "function") {
      layer.on("mouseover", function () {
        if (layer._icon) {
          layer._icon.classList.add("is-hovered");
        }
      });
      layer.on("mouseout", function () {
        if (layer._icon) {
          layer._icon.classList.remove("is-hovered");
        }
      });
    }
  }

  function renderPressureLayer(items) {
    state.groups.pressure.clearLayers();
    (items || []).forEach(function (item) {
      var isCritical = normalize(item.risk_level) === "critical";
      var isElevated = normalize(item.risk_level) === "elevated";
      var isCold = Boolean(item.is_stale || item.is_blocked);
      var color = isCritical ? "#b42335" : isElevated ? "#c88b2b" : "#1f5880";
      var circle = L.circle([Number(item.lat), Number(item.lng)], {
        pane: "overlayPane",
        radius: Number(item.radius || 1400),
        color: color,
        weight: 1,
        fillColor: color,
        fillOpacity: isCold ? 0.045 : isCritical ? 0.14 : isElevated ? 0.095 : 0.055,
        className: "hc-command-pressure " + (
          isCold
            ? "hc-command-pressure--cold"
            : isCritical
            ? "hc-command-pressure--critical"
            : isElevated
            ? "hc-command-pressure--elevated"
            : "hc-command-pressure--calm"
        )
      });
      circle.bindPopup(popupHtml(item));
      circle.on("click", function () { openDrawer(item); });
      circle.on("mouseover", function () {
        circle.setStyle({
          weight: 1.4,
          fillOpacity: isCritical ? 0.16 : isElevated ? 0.11 : 0.07
        });
      });
      circle.on("mouseout", function () {
        circle.setStyle({
          weight: 1,
          fillOpacity: isCritical ? 0.12 : isElevated ? 0.08 : 0.05
        });
      });
      circle.addTo(state.groups.pressure);
    });
  }

  function renderMarkerLayer(layerName, items) {
    var group = state.groups[layerName];
    group.clearLayers();
    var zoom = state.map.getZoom();
    groupItems(items, zoom).forEach(function (bucket) {
      if (!bucket.length) return;

      if (bucket.length === 1) {
        var item = bucket[0];
        var marker = L.marker([Number(item.lat), Number(item.lng)], {
          icon: markerIcon(item),
          riseOnHover: true,
          zIndexOffset: normalize(item.risk_level) === "critical" ? 300 : 120
        });
        decorateInteractiveLayer(marker, item);
        marker.addTo(group);
        return;
      }

      var summary = clusterSummary(bucket);
      var bounds = buildBounds(bucket);
      var lat = bucket.reduce(function (sum, item) { return sum + Number(item.lat); }, 0) / bucket.length;
      var lng = bucket.reduce(function (sum, item) { return sum + Number(item.lng); }, 0) / bucket.length;
      var clusterMarker = L.marker([lat, lng], {
        icon: clusterIcon(summary.risk_level, bucket.length),
        riseOnHover: true,
        zIndexOffset: 180
      });
      decorateInteractiveLayer(clusterMarker, summary);
      clusterMarker.on("click", function () {
        if (bounds && state.map.getZoom() < 12) {
          state.map.fitBounds(bounds, { padding: [56, 56], maxZoom: Math.min(13, state.map.getZoom() + 2) });
        }
      });
      clusterMarker.addTo(group);
    });
  }

  function renderLayers() {
    if (!state.payload || !state.map) return;
    renderPressureLayer(visibleLayerItems("pressure"));
    renderMarkerLayer("situations", visibleLayerItems("situations"));
    renderMarkerLayer("intervenants", visibleLayerItems("intervenants"));
    renderMarkerLayer("structures", visibleLayerItems("structures"));
    renderMarkerLayer("alerts", visibleLayerItems("alerts"));
    updateNarrative();
  }

  function setFocusMode(enabled) {
    state.focusMode = Boolean(enabled);
    root.classList.toggle("is-focus-mode", state.focusMode);
    if (focusToggleButton) {
      focusToggleButton.classList.toggle("is-active", state.focusMode);
      focusToggleButton.setAttribute("aria-pressed", state.focusMode ? "true" : "false");
      focusToggleButton.title = state.focusMode ? "Afficher toutes les couches visibles" : "Afficher uniquement les priorites operationnelles";
    }
    renderLayers();
    scheduleMapInvalidation(120);
    scheduleFitToVisible();
  }

  function resetFilters() {
    filterInputs.forEach(function (input) {
      Array.prototype.slice.call(input.options || []).forEach(function (option) {
        option.selected = false;
      });
    });
    if (staleCheckbox) staleCheckbox.checked = false;
    if (withAssignmentCheckbox) withAssignmentCheckbox.checked = false;
    if (withoutAssignmentCheckbox) withoutAssignmentCheckbox.checked = false;
    toggleInputs.forEach(function (input) {
      if (!input.disabled) input.checked = true;
    });
    renderLayers();
    scheduleFitToVisible();
  }

  function initMap(center) {
    state.map = L.map(mapEl, {
      zoomControl: true,
      preferCanvas: true
    }).setView([Number(center.lat), Number(center.lng)], Number(center.zoom || 6));

    state.groups.pressure = L.layerGroup().addTo(state.map);
    state.groups.situations = L.layerGroup().addTo(state.map);
    state.groups.intervenants = L.layerGroup().addTo(state.map);
    state.groups.structures = L.layerGroup().addTo(state.map);
    state.groups.alerts = L.layerGroup().addTo(state.map);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors"
    }).addTo(state.map);

    state.map.on("zoomend", renderLayers);
    runStartupInvalidations();
    window.setTimeout(function () {
      invalidateMapSize();
    }, 120);
  }

  function parsePayload(responseText) {
    if (!responseText) return null;
    try {
      return JSON.parse(responseText);
    } catch (_error) {
      return null;
    }
  }

  function applyAvailability() {
    if (!state.payload || !state.payload.layers) return;
    var layerAvailability = {
      situations: (state.payload.layers.situations || []).length > 0,
      intervenants: (state.payload.layers.intervenants || []).length > 0,
      pressure: (state.payload.layers.pressure || []).length > 0,
      structures: Boolean(state.payload.meta && state.payload.meta.structures_available),
      alerts: (state.payload.layers.alerts || []).length > 0
    };
    toggleInputs.forEach(function (input) {
      var layerName = input.getAttribute("data-layer-toggle");
      var available = layerAvailability[layerName] !== false;
      input.disabled = !available;
      if (!available) input.checked = false;
    });
  }

  function hydrateFilters() {
    var filters = (state.payload && state.payload.filters) || {};
    filterInputs.forEach(function (input) {
      populateSelect(input, filters[input.getAttribute("data-filter")] || []);
    });
  }

  async function loadPayload() {
    clearDrawer();
    hideEmptyState();
    setText(liveNarrativeEl, "Chargement de la lecture territoriale");
    try {
      var response = await fetch(endpoint, {
        credentials: "same-origin",
        cache: "no-store"
      });
      var responseText = await response.text();
      var payload = parsePayload(responseText);
      if (!response.ok || !payload || payload.status !== "ok") {
        throw new Error((payload && payload.message) || "command_map_unavailable");
      }
      state.payload = payload;
      ensureLivePulseUi();
      hydrateFilters();
      applyAvailability();
      if (!state.map) {
        initMap(payload.default_center || { lat: 46.603354, lng: 1.888334, zoom: 6 });
      }
      renderLayers();
      window.setTimeout(fitMapToVisible, 80);
    } catch (_error) {
      if (!state.map) {
        initMap({ lat: 46.603354, lng: 1.888334, zoom: 6 });
      }
      showEmptyState(
        "Donnes de carte indisponibles",
        "La lecture territoriale est momentanment indisponible. Vrifiez laccs  lAPI command-map."
      );
      setText(liveNarrativeEl, "La carte consolide n'a pas pu tre charge.");
      if (overlay.title) {
        overlay.title.textContent = "Surface indisponible";
        overlay.text.textContent = "Le chargement des couches oprationnelles a chou. Vrifiez laccs  lAPI command-map.";
        setPressureClass(overlay.root, "critical");
      }
    }
  }

  if (legend.toggle) {
    legend.toggle.addEventListener("click", function () {
      var isOpen = !legend.root.classList.contains("is-open");
      legend.root.classList.toggle("is-open", isOpen);
      legend.toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
      if (legend.panel) {
        legend.panel.hidden = !isOpen;
      }
    });
  }

  toggleInputs.forEach(function (input) {
    input.addEventListener("change", function () {
      renderLayers();
      scheduleMapInvalidation();
      scheduleFitToVisible();
    });
  });

  filterInputs.forEach(function (input) {
    input.addEventListener("change", function () {
      renderLayers();
      scheduleMapInvalidation();
      scheduleFitToVisible();
    });
  });

  [staleCheckbox, withAssignmentCheckbox, withoutAssignmentCheckbox].forEach(function (input) {
    if (input) {
      input.addEventListener("change", function () {
        renderLayers();
        scheduleMapInvalidation();
        scheduleFitToVisible();
      });
    }
  });

  if (fitViewButton) fitViewButton.addEventListener("click", fitMapToVisible);
  if (resetFiltersButton) resetFiltersButton.addEventListener("click", resetFilters);
  if (focusToggleButton) {
    focusToggleButton.addEventListener("click", function () {
      setFocusMode(!state.focusMode);
    });
  }
  if (drawer.clear) drawer.clear.addEventListener("click", clearDrawer);

  window.addEventListener("resize", function () {
    scheduleMapInvalidation(140);
  });
  window.addEventListener("orientationchange", function () {
    scheduleMapInvalidation(220);
  });

  if (mobileQuery) {
    if (typeof mobileQuery.addEventListener === "function") {
      mobileQuery.addEventListener("change", syncMobileMode);
    } else if (typeof mobileQuery.addListener === "function") {
      mobileQuery.addListener(syncMobileMode);
    }
  }

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && root.classList.contains("is-mobile-filter-open")) {
      setMobileFilterOpen(false);
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      syncMobileMode();
      scheduleMapInvalidation(0);
      scheduleMapInvalidation(180);
    });
  } else {
    syncMobileMode();
    scheduleMapInvalidation(0);
  }

  loadPayload();
})();
