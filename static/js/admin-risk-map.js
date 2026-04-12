(function () {
  var root = document.querySelector("[data-risk-map-root]");
  if (!root) {
    return;
  }

  var endpoint = root.dataset.endpoint || "";
  var professionalsEndpoint = root.dataset.professionalsEndpoint || "";
  var defaultLat = Number(root.dataset.defaultLat || 48.8397);
  var defaultLng = Number(root.dataset.defaultLng || 2.2399);
  var defaultZoom = Number(root.dataset.defaultZoom || 13);
  var defaultCity = root.dataset.defaultCity || "Boulogne-Billancourt";
  var activeCaseCount = Number(root.dataset.activeCaseCount || 0);
  var criticalQueueCount = Number(root.dataset.criticalQueueCount || 0);
  var emptyCtaHref = root.dataset.emptyCta || "/admin/requests";
  var mapEl = document.getElementById("riskMapCanvas");
  var stateBar = document.getElementById("riskMapStateBar");
  var zoneSelect = document.getElementById("riskMapZoneSelect");
  var emptyState = document.getElementById("riskMapEmptyState");
  var emptyCta = document.getElementById("riskMapEmptyCta");
  var mapHintEl = document.getElementById("riskMapMapHint");
  var criticalCountEl = document.getElementById("riskMapCriticalCount");
  var zonesCountEl = document.getElementById("riskMapZonesCount");
  var professionalsCountEl = document.getElementById("riskMapProfessionalsCount");
  var staleCountEl = document.getElementById("riskMapStaleCount");
  var criticalHintEl = document.getElementById("riskMapCriticalHint");
  var zonesHintEl = document.getElementById("riskMapZonesHint");
  var professionalsHintEl = document.getElementById("riskMapProfessionalsHint");
  var staleHintEl = document.getElementById("riskMapStaleHint");
  var coverageLineEl = document.getElementById("riskMapCoverageLine");
  var zoneLabelEl = document.getElementById("riskMapZoneLabel");
  var actionMetaEl = document.getElementById("riskMapActionMeta");
  var openCasesEl = document.getElementById("riskMapOpenCases");
  var openRequestsEl = document.getElementById("riskMapOpenRequests");
  var openStaleEl = document.getElementById("riskMapOpenStale");
  var queueNoteEl = document.getElementById("riskMapQueueNote");
  var emptyCapacityEl = document.getElementById("riskMapEmptyCapacity");

  var map = null;
  var markersLayer = null;
  var professionalsLayer = null;
  var refreshTimer = null;
  var lastProfessionalsCount = 0;
  var currentRiskItems = [];

  if (emptyCta) {
    emptyCta.href = emptyCtaHref;
  }

  function currentCity() {
    if (zoneSelect && zoneSelect.options.length) {
      return zoneSelect.options[zoneSelect.selectedIndex].text || defaultCity;
    }
    return defaultCity;
  }

  function buildCasesUrl(city, extras) {
    var params = new URLSearchParams(extras || {});
    params.set("city", city || defaultCity);
    return "/ops/cases?" + params.toString();
  }

  function buildRequestsUrl(city, extras) {
    var params = new URLSearchParams(extras || {});
    params.set("city", city || defaultCity);
    return "/admin/requests?" + params.toString();
  }

  function storeCityContext(city) {
    var selectedCity = city || currentCity();
    var currentUrl = new URL(window.location.href);
    currentUrl.searchParams.set("city", selectedCity);
    window.history.replaceState({}, "", currentUrl.toString());
    setText(zoneLabelEl, selectedCity);
    setText(actionMetaEl, selectedCity);
  }

  function syncActionUrls(city) {
    var selectedCity = city || currentCity();
    if (openCasesEl) {
      openCasesEl.href = buildCasesUrl(selectedCity);
    }
    if (openRequestsEl) {
      openRequestsEl.href = buildRequestsUrl(selectedCity, { status: "open" });
    }
    if (openStaleEl) {
      openStaleEl.href = buildCasesUrl(selectedCity, { stale: "1" });
    }
    if (emptyCta) {
      emptyCta.href = buildRequestsUrl(selectedCity);
    }
  }

  function riskColor(level, score) {
    if (level === "high" || Number(score) >= 80) return "#c62828";
    if (level === "medium" || Number(score) >= 50) return "#ef6c00";
    return "#2e7d32";
  }

  function riskRadius(score) {
    var numericScore = Number(score || 0);
    if (numericScore >= 80) return 10;
    if (numericScore >= 50) return 8;
    return 6;
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function setText(el, value) {
    if (el) {
      el.textContent = String(value);
    }
  }

  function parseUtcDate(value) {
    if (!value) {
      return null;
    }
    var raw = String(value).trim();
    if (!raw) {
      return null;
    }
    var normalized = /z$|[+\-]\d\d:\d\d$/i.test(raw) ? raw : raw + "Z";
    var dt = new Date(normalized);
    return Number.isNaN(dt.getTime()) ? null : dt;
  }

  function pluralize(count, singular, plural) {
    return count + " " + (count > 1 ? plural : singular);
  }

  function updateQueueNote(hasGeolocatedCritical) {
    if (!queueNoteEl) {
      return;
    }
    if (criticalQueueCount > 0 && !hasGeolocatedCritical) {
      queueNoteEl.textContent =
        pluralize(criticalQueueCount, "situation critique", "situations critiques") +
        " existent dans la file operateur, sans localisation exploitable sur la carte.";
      return;
    }
    if (activeCaseCount > 0) {
      queueNoteEl.textContent =
        pluralize(activeCaseCount, "cas actif", "cas actifs") +
        " restent pilotables sur la zone, meme lorsque la carte ne dispose pas encore de toutes les localisations.";
      return;
    }
    queueNoteEl.textContent =
      "La file operateur reste disponible sur la zone, meme lorsque la carte ne dispose pas encore de situations localisees.";
  }

  function updateEmptyCapacity(visibleMarkers) {
    if (!emptyCapacityEl) {
      return;
    }
    if (visibleMarkers > 0) {
      emptyCapacityEl.textContent =
        pluralize(visibleMarkers, "intervenant visible", "intervenants visibles") +
        " sur " + currentCity() + ".";
      return;
    }
    if (criticalQueueCount > 0) {
      emptyCapacityEl.textContent =
        pluralize(criticalQueueCount, "situation critique", "situations critiques") +
        " restent a traiter dans la file operateur.";
      return;
    }
    emptyCapacityEl.textContent = "Capacite terrain en cours de lecture.";
  }

  function setState(_, text) {
    if (stateBar) {
      stateBar.textContent = text;
    }
  }

  function setEmptyVisible(isVisible) {
    if (emptyState) {
      emptyState.classList.toggle("is-visible", Boolean(isVisible));
    }
  }

  function setMapHint(text, isVisible) {
    if (!mapHintEl) {
      return;
    }
    mapHintEl.textContent = text || "";
    mapHintEl.classList.toggle("is-visible", Boolean(isVisible));
  }

  function ensureMap() {
    if (!mapEl) {
      return false;
    }
    if (typeof L === "undefined") {
      setState("error", "La bibliothèque cartographique n'a pas pu être chargée.");
      return false;
    }
    if (map) {
      return true;
    }

    map = L.map(mapEl).setView([48.8397, 2.2399], 13);
    markersLayer = L.layerGroup().addTo(map);
    professionalsLayer = L.layerGroup().addTo(map);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    window.setTimeout(function () {
      map.invalidateSize();
    }, 0);

    return true;
  }

  function popupActionsHtml(city) {
    var selectedCity = encodeURIComponent(city || defaultCity);
    return [
      '<div class="hc-risk-map-popup__actions">',
      '<a class="hc-risk-map-popup__action" href="/ops/cases?city=' + selectedCity + '">Voir les cas liés</a>',
      '<a class="hc-risk-map-popup__action" href="/admin/requests?city=' + selectedCity + '">Voir les demandes</a>',
      "</div>",
    ].join("");
  }

  function popupHtml(item) {
    var riskLabel = "Standard";
    if (item && (item.risk_level === "high" || Number(item.risk_score) >= 80)) {
      riskLabel = "Critique";
    } else if (item && (item.risk_level === "medium" || Number(item.risk_score) >= 50)) {
      riskLabel = "Attention";
    }
    var city = item && item.city ? item.city : currentCity();

    return [
      '<div class="hc-risk-map-popup__eyebrow">Situation</div>',
      "<strong>" + escapeHtml(item.title || "Situation") + "</strong>",
      item.city ? "Ville : " + escapeHtml(item.city) : "",
      "Niveau : " + escapeHtml(riskLabel),
      "Score : " + escapeHtml(item.risk_score || 0),
      item.category ? "Catégorie : " + escapeHtml(item.category) : "",
      item.status ? "Statut : " + escapeHtml(item.status) : "",
      item.updated_at ? "Dernière mise à jour : " + escapeHtml(item.updated_at) : "",
      popupActionsHtml(city),
    ]
      .filter(Boolean)
      .join("<br>");
  }

  function professionalPopupHtml(item) {
    var city = item && item.city ? item.city : currentCity();
    return [
      '<div class="hc-risk-map-popup__eyebrow">Intervenant</div>',
      "<strong>" + escapeHtml(item.full_name || "Intervenant") + "</strong>",
      item.profession ? "Profession : " + escapeHtml(item.profession) : "",
      item.address ? "Adresse : " + escapeHtml(item.address) : "",
      city ? "Ville : " + escapeHtml(city) : "",
      popupActionsHtml(city),
    ].filter(Boolean).join("<br>");
  }

  function zoneKey(item) {
    if (item && item.city) {
      return String(item.city).trim().toLowerCase();
    }
    var lat = Number(item && item.latitude);
    var lng = Number(item && item.longitude);
    if (Number.isFinite(lat) && Number.isFinite(lng)) {
      return lat.toFixed(2) + "|" + lng.toFixed(2);
    }
    return "";
  }

  function updateRiskKpis(items) {
    var rows = Array.isArray(items) ? items : [];
    currentRiskItems = rows.slice();
    var criticalCount = 0;
    var staleCount = 0;
    var zones = new Set();
    var now = new Date();

    rows.forEach(function (item) {
      var score = Number(item && item.risk_score || 0);
      var level = String(item && item.risk_level || "").toLowerCase();
      if (level === "high" || score >= 80) {
        criticalCount += 1;
      }
      var key = zoneKey(item);
      if (key) {
        zones.add(key);
      }

      var referenceDate =
        parseUtcDate(item && item.updated_at) ||
        parseUtcDate(item && item.created_at);
      if (referenceDate && (now.getTime() - referenceDate.getTime()) >= (72 * 60 * 60 * 1000)) {
        staleCount += 1;
      }
    });

    setText(criticalCountEl, criticalCount);
    setText(zonesCountEl, zones.size);
    setText(staleCountEl, staleCount);
    if (criticalCount === 0) {
      setText(criticalHintEl, "Aucune situation critique localisee sur la carte.");
    }
    setText(
      criticalHintEl,
      criticalCount > 0
        ? criticalCount + (criticalCount > 1 ? " situations critiques géolocalisées." : " situation critique géolocalisée.")
        : "Aucune situation critique géolocalisée."
    );
    setText(
      zonesHintEl,
      zones.size > 0
        ? zones.size + (zones.size > 1 ? " zones actives détectées." : " zone active détectée.")
        : "Aucune zone active détectée."
    );
    setText(
      staleHintEl,
      staleCount > 0
        ? staleCount + (staleCount > 1 ? " situations à relancer." : " situation à relancer.")
        : "Aucune situation en dépassement."
    );

    if (coverageLineEl) {
      if (rows.length > 0) {
        coverageLineEl.textContent =
          rows.length +
          (rows.length > 1 ? " situations géolocalisées" : " situation géolocalisée") +
          " · " +
          lastProfessionalsCount +
          (lastProfessionalsCount > 1 ? " intervenants visibles" : " intervenant visible") +
          " · " +
          staleCount +
          (staleCount > 1 ? " situations à relancer" : " situation à relancer");
      } else {
        coverageLineEl.textContent =
          lastProfessionalsCount +
          (lastProfessionalsCount > 1 ? " intervenants visibles sur la zone" : " intervenant visible sur la zone") +
          " · Aucune situation géolocalisée active pour le moment";
      }
    }
    if (coverageLineEl && rows.length === 0) {
      var segments = [
        pluralize(lastProfessionalsCount, "intervenant visible sur la zone", "intervenants visibles sur la zone"),
      ];
      if (criticalQueueCount > 0) {
        segments.push(
          pluralize(
            criticalQueueCount,
            "situation critique dans la file, non localisee",
            "situations critiques dans la file, non localisees"
          )
        );
      } else if (activeCaseCount > 0) {
        segments.push(
          pluralize(activeCaseCount, "cas actif disponible dans la file", "cas actifs disponibles dans la file")
        );
      }
      coverageLineEl.textContent = segments.join(" · ");
    }
    updateQueueNote(criticalCount > 0);
  }

  async function loadProfessionalsKpi() {
    if (!professionalsEndpoint) {
      setText(professionalsCountEl, 0);
      setMapHint("", false);
      updateEmptyCapacity(0);
      return;
    }
    try {
      var res = await fetch(professionalsEndpoint, {
        credentials: "same-origin",
        cache: "no-store",
      });
      var data = await res.json();
      if (!res.ok || !data || data.status !== "ok") {
        throw new Error("professionals_unavailable");
      }
      var professionals = Array.isArray(data.professionals) ? data.professionals : [];
      if (professionalsLayer) {
        professionalsLayer.clearLayers();
      }
      var visibleMarkers = 0;
      var availableCount = professionals.filter(function (item) {
        var availability = String(item && item.availability || "").toLowerCase();
        return availability !== "indisponible";
      }).length;
      professionals.forEach(function (item) {
        var lat = Number(item && item.latitude);
        var lng = Number(item && item.longitude);
        if (!Number.isFinite(lat) || !Number.isFinite(lng) || !professionalsLayer) {
          return;
        }
        visibleMarkers += 1;
        L.circleMarker([lat, lng], {
          radius: 12,
          color: "rgba(59, 130, 246, 0.28)",
          weight: 1,
          fillColor: "rgba(96, 165, 250, 0.18)",
          fillOpacity: 0.32,
          opacity: 0.55,
        }).addTo(professionalsLayer);
        var marker = L.circleMarker([lat, lng], {
          radius: 7,
          color: "#1d4ed8",
          weight: 2.5,
          fillColor: "#93c5fd",
          fillOpacity: 0.95,
          opacity: 1,
        });
        marker.bindPopup(professionalPopupHtml(item));
        marker.on("click", function () {
          storeCityContext(item && item.city ? item.city : currentCity());
          syncActionUrls(item && item.city ? item.city : currentCity());
        });
        marker.addTo(professionalsLayer);
      });
      lastProfessionalsCount = availableCount;
      setText(professionalsCountEl, availableCount);
      setText(
        professionalsHintEl,
        availableCount > 0
          ? "Capacité opérationnelle disponible."
          : "Aucun intervenant disponible."
      );
      setMapHint(
        visibleMarkers > 0
          ? visibleMarkers + (visibleMarkers > 1 ? " intervenants disponibles sur la zone" : " intervenant disponible sur la zone")
          : "Intervenants disponibles sur la zone",
        true
      );
      if (visibleMarkers > 0) {
        setMapHint(
          pluralize(visibleMarkers, "intervenant disponible sur la zone", "intervenants disponibles sur la zone") +
            (criticalQueueCount > 0
              ? " · " + pluralize(criticalQueueCount, "situation critique non localisee", "situations critiques non localisees")
              : ""),
          true
        );
      }
      updateEmptyCapacity(visibleMarkers);
      updateRiskKpis(currentRiskItems);
    } catch (_) {
      lastProfessionalsCount = 0;
      setText(professionalsCountEl, "—");
      setText(professionalsHintEl, "Capacité opérationnelle non disponible.");
      if (professionalsLayer) {
        professionalsLayer.clearLayers();
      }
      setMapHint("", false);
      updateEmptyCapacity(0);
      updateRiskKpis(currentRiskItems);
    }
  }

  function renderItems(items) {
    var rows = Array.isArray(items) ? items : [];
    var bounds = [];

    markersLayer.clearLayers();
    updateRiskKpis(rows);

    rows.forEach(function (item) {
      var lat = Number(item && item.latitude);
      var lng = Number(item && item.longitude);
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
        return;
      }

      var score = Number(item && item.risk_score || 0);
      var color = riskColor(item && item.risk_level, score);
      var marker = L.circleMarker([lat, lng], {
        radius: riskRadius(score),
        color: color,
        weight: 2,
        fillColor: color,
        fillOpacity: 0.35,
      });
      marker.bindPopup(popupHtml(item));
      marker.on("click", function () {
        storeCityContext(item && item.city ? item.city : currentCity());
        syncActionUrls(item && item.city ? item.city : currentCity());
      });
      marker.addTo(markersLayer);
      bounds.push([lat, lng]);
    });

    if (bounds.length === 0) {
      map.setView([48.8397, 2.2399], 13);
      setEmptyVisible(true);
      return;
    }

    setEmptyVisible(false);
    map.fitBounds(bounds, { padding: [28, 28], maxZoom: 14 });
    setState(
      "success",
      String(bounds.length) +
        (bounds.length > 1
          ? " situations géolocalisées affichées sur Boulogne-Billancourt."
          : " situation géolocalisée affichée sur Boulogne-Billancourt.")
    );
  }

  async function loadRiskMap() {
    if (!ensureMap() || !endpoint) {
      return;
    }
    map.setView([48.8397, 2.2399], 13);
    setEmptyVisible(false);
    setState("loading", "Chargement de la cartographie territoriale de Boulogne-Billancourt...");

    try {
      var res = await fetch(endpoint, {
        credentials: "same-origin",
        cache: "no-store",
      });
      var data = await res.json();
      if (!res.ok || !data || data.status !== "ok") {
        throw new Error((data && data.message) || "risk_map_data_unavailable");
      }
      renderItems(data.items || []);
    } catch (_) {
      if (markersLayer) {
        markersLayer.clearLayers();
      }
      if (map) {
        map.setView([defaultLat, defaultLng], defaultZoom);
      }
      updateRiskKpis([]);
      setEmptyVisible(true);
    }
  }

  function startRefresh() {
    if (refreshTimer) {
      window.clearInterval(refreshTimer);
    }
    refreshTimer = window.setInterval(loadRiskMap, 30000);
  }

  function bindEvents() {
    if (zoneSelect) {
      zoneSelect.addEventListener("change", function () {
        var selectedCity = currentCity();
        setText(zoneLabelEl, selectedCity);
        setText(actionMetaEl, selectedCity);
        syncActionUrls(selectedCity);
        storeCityContext(selectedCity);
        updateEmptyCapacity(lastProfessionalsCount);
        if (map) {
          map.setView([defaultLat, defaultLng], defaultZoom);
        }
        loadRiskMap();
      });
    }

    window.addEventListener("resize", function () {
      if (map) {
        map.invalidateSize();
      }
    });
  }

  async function boot() {
    syncActionUrls(currentCity());
    storeCityContext(currentCity());
    updateQueueNote(false);
    await Promise.all([loadRiskMap(), loadProfessionalsKpi()]);
    startRefresh();
    bindEvents();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
