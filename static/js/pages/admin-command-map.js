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
    selectedItem: null
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
    status: document.getElementById("commandMapDrawerStatus")
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
  var urgentCountEl = document.getElementById("commandMapUrgentCount");
  var staleCountEl = document.getElementById("commandMapStaleCount");
  var followupCountEl = document.getElementById("commandMapFollowupCount");
  var pressureCountEl = document.getElementById("commandMapPressureCount");
  var fitViewButton = document.getElementById("commandMapFitView");
  var resetFiltersButton = document.getElementById("commandMapResetFilters");
  var toggleInputs = root.querySelectorAll("[data-layer-toggle]");
  var filterInputs = root.querySelectorAll("[data-filter]");
  var staleCheckbox = document.getElementById("commandMapOnlyStale");
  var withAssignmentCheckbox = document.getElementById("commandMapWithAssignment");
  var withoutAssignmentCheckbox = document.getElementById("commandMapWithoutAssignment");

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

  function showEmptyState(title, message) {
    if (emptyState.root) {
      emptyState.root.hidden = false;
    }
    setText(emptyState.title, title || "Donnes de carte indisponibles");
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

  function visibleLayerItems(layerName) {
    if (!state.payload || !state.payload.layers) return [];
    var toggles = currentLayerState();
    if (!toggles[layerName]) return [];
    var filters = currentFilters();
    return (state.payload.layers[layerName] || []).filter(function (item) {
      return applyItemFilters(item, filters);
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
    var bounds = buildBounds(allVisibleItems());
    if (bounds) {
      state.map.fitBounds(bounds, { padding: [48, 48], maxZoom: 12 });
      return;
    }
    var center = (state.payload && state.payload.default_center) || { lat: 46.603354, lng: 1.888334, zoom: 6 };
    state.map.setView([Number(center.lat), Number(center.lng)], Number(center.zoom || 6));
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
    return L.divIcon({
      className: "hc-command-markerWrap",
      html: '<span class="hc-command-marker hc-command-marker--' + tone + '"></span>',
      iconSize: [24, 24],
      iconAnchor: [12, 12],
      popupAnchor: [0, -12]
    });
  }

  function clusterIcon(level, count) {
    return L.divIcon({
      className: "hc-command-clusterWrap",
      html: '<span class="hc-command-cluster ' + pressureClass(level) + '">' + esc(String(count)) + "</span>",
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
        "Aucun signal oprationnel visible",
        "Aucun signal oprationnel visible avec les filtres actuels."
      );
      setText(liveNarrativeEl, "Aucun signal ne correspond aux filtres actifs.");
      if (overlay.title) {
        overlay.title.textContent = "Aucune couche visible";
        overlay.text.textContent = "Ractivez une couche ou largissez les filtres pour restaurer la lecture oprationnelle.";
        setPressureClass(overlay.root, "watch");
      }
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
  }

  function activateDrawer(active) {
    if (!drawerRoot) return;
    drawerRoot.classList.toggle("is-active", Boolean(active));
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
      drawer.open.href = item.detail_url || "#";
      drawer.open.classList.toggle("disabled", !item.detail_url);
    }
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
    if (drawer.open) {
      drawer.open.href = "#";
      drawer.open.classList.add("disabled");
    }
    setPressureClass(drawer.status, "calm");
    activateDrawer(false);
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
      var color = isCritical ? "#b42335" : isElevated ? "#c88b2b" : "#1f5880";
      var circle = L.circle([Number(item.lat), Number(item.lng)], {
        pane: "overlayPane",
        radius: Number(item.radius || 1400),
        color: color,
        weight: 1,
        fillColor: color,
        fillOpacity: isCritical ? 0.12 : isElevated ? 0.08 : 0.05
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
    window.setTimeout(function () {
      state.map.invalidateSize();
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
      hydrateFilters();
      applyAvailability();
      if (!state.map) {
        initMap(payload.default_center || { lat: 46.603354, lng: 1.888334, zoom: 6 });
      }
      renderLayers();
      fitMapToVisible();
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
      scheduleFitToVisible();
    });
  });

  filterInputs.forEach(function (input) {
    input.addEventListener("change", function () {
      renderLayers();
      scheduleFitToVisible();
    });
  });

  [staleCheckbox, withAssignmentCheckbox, withoutAssignmentCheckbox].forEach(function (input) {
    if (input) {
      input.addEventListener("change", function () {
        renderLayers();
        scheduleFitToVisible();
      });
    }
  });

  if (fitViewButton) fitViewButton.addEventListener("click", fitMapToVisible);
  if (resetFiltersButton) resetFiltersButton.addEventListener("click", resetFilters);
  if (drawer.clear) drawer.clear.addEventListener("click", clearDrawer);

  loadPayload();
})();
