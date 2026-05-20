(function () {
  var root = document.querySelector(".hc-map-page--professionals");
  var apiUrl = (root && root.getAttribute("data-professionals-api")) || "/admin/api/professionals";
  var listUrl = (root && root.getAttribute("data-professionals-list-url")) || "/admin/intervenants";
  var structureName = (root && root.getAttribute("data-professionals-structure-name")) || "";
  var liveManager = root && window.HCMapsLive && window.HCMapsLive.create
    ? window.HCMapsLive.create(root, {
        loadingText: "Analyse de couverture...",
        refreshText: "Synchronisation des intervenants...",
        stableText: "Couverture live"
      })
    : null;

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function setText(id, value) {
    var el = document.getElementById(id);
    if (!el) return;
    el.textContent = value;
  }

  function pressureClass(level) {
    if (level === "critical") return "hc-pressure-critical";
    if (level === "elevated") return "hc-pressure-elevated";
    if (level === "watch") return "hc-pressure-watch";
    return "hc-pressure-calm";
  }

  function setPressureClass(el, level) {
    if (!el) return;
    el.classList.remove("hc-pressure-calm", "hc-pressure-watch", "hc-pressure-elevated", "hc-pressure-critical");
    el.classList.add(pressureClass(level));
  }

  function setMarkerState(marker, state, enabled) {
    var icon = marker && marker.getElement && marker.getElement();
    if (!icon) return;
    icon.classList.toggle(state, Boolean(enabled));
  }

  function isAvailableProfessional(item) {
    var availability = String(item && item.availability || "").trim().toLowerCase();
    return ["unavailable", "indisponible", "capped", "full", "sature"].indexOf(availability) === -1;
  }

  function coordinateKey(lat, lng) {
    return Number(lat).toFixed(6) + ":" + Number(lng).toFixed(6);
  }

  function ensureCommandPanelStatus() {
    var panel = document.querySelector(".hc-map-command-panel--coverage");
    if (!panel) return null;
    var existing = panel.querySelector(".hc-map-command-panel__status");
    if (existing) return existing;
    var wrapper = document.createElement("div");
    wrapper.className = "hc-map-command-panel__status hc-pressure-calm";
    wrapper.innerHTML =
      '<div class="hc-map-command-panel__status-label">Etat territorial</div>' +
      '<div class="hc-map-command-panel__status-value">Couverture visible</div>' +
      '<div class="hc-map-command-panel__status-note">Lecture initiale de la couverture en cours.</div>';
    panel.appendChild(wrapper);
    return wrapper;
  }

  function updateNarrative(cityCount, listCount, topCity, topCityCount, dominantProfession, dominantProfessionCount, groupedCount, groupedCity) {
    var statusEl = ensureCommandPanelStatus();
    var panel = document.querySelector(".hc-map-command-panel--coverage");
    var contextBar = document.querySelector(".hc-risk-map-contextbar");
    var queueNote = document.querySelector(".hc-risk-map-queue-note");
    var kpis = document.querySelectorAll(".hc-risk-map-kpi");
    var level = "calm";
    var value = "Couverture visible";
    var note = listCount > 0
      ? listCount + (listCount > 1 ? " intervenants visibles sur la carte." : " intervenant visible sur la carte.")
      : "Aucun intervenant cartographie disponible pour le moment.";

    if (listCount === 0) {
      level = "watch";
      value = "Couverture limitee";
    } else if (groupedCount >= 2) {
      level = groupedCount >= 5 ? "elevated" : "watch";
      value = "Couverture concentree";
      note = groupedCount + (groupedCount > 1 ? " intervenants concentres sur " : " intervenant concentre sur ") + groupedCity + ". Cliquez le marqueur groupe pour voir la liste detaillee.";
    } else if (cityCount <= 1) {
      level = "watch";
      value = "Couverture concentree";
      note = "La couverture visible reste concentree sur une zone principale.";
    } else if (topCityCount >= Math.max(4, Math.ceil(listCount * 0.55))) {
      level = "elevated";
      value = "Attention operationnelle";
      note = "La ressource terrain se concentre majoritairement sur " + topCity + ".";
    } else if (dominantProfessionCount >= Math.max(3, Math.ceil(listCount * 0.5))) {
      level = "watch";
      value = "Couverture specialisee";
      note = "La couverture est surtout portee par le metier " + dominantProfession + ".";
    }

    setPressureClass(panel, level);
    setPressureClass(statusEl, level);
    setPressureClass(contextBar, level);
    setPressureClass(queueNote, level === "elevated" ? "watch" : level);
    if (statusEl) {
      var valueEl = statusEl.querySelector(".hc-map-command-panel__status-value");
      var noteEl = statusEl.querySelector(".hc-map-command-panel__status-note");
      if (valueEl) valueEl.textContent = value;
      if (noteEl) noteEl.textContent = note;
    }
    if (kpis.length) {
      setPressureClass(kpis[0], cityCount > 1 ? "calm" : "watch");
      setPressureClass(kpis[1], listCount > 0 ? "calm" : "watch");
      setPressureClass(kpis[2], topCityCount >= Math.max(4, Math.ceil(listCount * 0.55)) ? "elevated" : "calm");
      setPressureClass(kpis[3], dominantProfessionCount >= Math.max(3, Math.ceil(listCount * 0.5)) ? "watch" : "calm");
    }
  }

  function popupActionsHtml(city) {
    var selectedCity = encodeURIComponent(city || "Boulogne-Billancourt");
    return [
      '<div class="hc-risk-map-popup__actions">',
      '<a class="hc-risk-map-popup__action" href="' + esc(listUrl) + '">Voir les intervenants</a>',
      '<a class="hc-risk-map-popup__action" href="/ops/cases?city=' + selectedCity + '">Voir les cas lies</a>',
      '<a class="hc-risk-map-popup__action" href="/admin/requests?city=' + selectedCity + '">Voir les demandes</a>',
      "</div>",
    ].join("");
  }

  function professionalPopupHtml(item) {
    var name = esc((item && item.full_name) || "Intervenant");
    var profession = esc((item && item.profession) || "professional");
    var city = esc((item && item.city) || "N/A");
    var availability = esc((item && item.availability_label) || (item && item.availability) || "unknown");
    var workload = Number(item && item.workload);
    var safeWorkload = Number.isFinite(workload) ? workload : 0;
    var address = esc((item && item.address) || "");
    var coordsLabel = item && item.has_exact_coordinates ? "coordonnees exactes" : "coordonnees ville";
    var actionCity = (item && item.city) || "Boulogne-Billancourt";
    var activeLabel = item && item.is_active === false ? "Inactif" : "Actif";

    return [
      '<div class="hc-risk-map-popup__eyebrow">Intervenant</div>',
      "<strong>" + name + "</strong>",
      profession,
      city,
      address || "",
      "Disponibilite : " + availability,
      "Statut : " + activeLabel,
      "Charge : " + String(safeWorkload),
      "Source carte : " + coordsLabel,
      popupActionsHtml(actionCity),
    ]
      .filter(Boolean)
      .join("<br>");
  }

  function buildRingIcon(variant) {
    var tone = variant || "professional";
    return L.divIcon({
      className: "hc-map-ringMarkerWrap",
      html:
        '<span class="hc-map-ringMarker hc-map-ringMarker--' +
        tone +
        '"><span class="hc-map-ringMarker__core"></span></span>',
      iconSize: [22, 22],
      iconAnchor: [11, 11],
      popupAnchor: [0, -10],
    });
  }

  function buildCountIcon(count, variant) {
    var tone = variant || "professional";
    return L.divIcon({
      className: "hc-map-countMarkerWrap",
      html:
        '<span class="hc-map-countMarker hc-map-countMarker--' +
        tone +
        '"><span class="hc-map-countMarker__count">' +
        esc(count) +
        "</span></span>",
      iconSize: [34, 34],
      iconAnchor: [17, 17],
      popupAnchor: [0, -14],
    });
  }

  function spiderfyLabel(count, city) {
    return count + (count > 1 ? " intervenants deployes autour de " : " intervenant deploye autour de ") + city + ".";
  }

  function groupedPopupHtml(items) {
    var rows = Array.isArray(items) ? items.slice() : [];
    if (!rows.length) return "";
    var first = rows[0] || {};
    var city = (first && first.city) || "Zone visible";
    var title = rows.length + (rows.length > 1 ? " intervenants concentres sur " : " intervenant concentre sur ") + city;
    var exactCount = rows.filter(function (item) { return Boolean(item && item.has_exact_coordinates); }).length;
    var note = exactCount === rows.length
      ? "Chaque intervenant dispose de coordonnees individuelles."
      : exactCount > 0
        ? exactCount + " intervenants utilisent des coordonnees exactes, le reste partage des coordonnees ville."
        : "Tous ces intervenants partagent les memes coordonnees ville de repli.";
    var listHtml = rows.map(function (item) {
      var availability = esc((item && item.availability_label) || (item && item.availability) || "unknown");
      var profession = esc((item && item.profession) || "Intervenant");
      var status = item && item.is_active === false ? "Inactif" : "Actif";
      return [
        '<li class="hc-risk-map-popup__item">',
        '<strong>' + esc((item && item.full_name) || "Intervenant") + '</strong>',
        '<span>' + profession + " · " + availability + " · " + status + "</span>",
        "</li>",
      ].join("");
    }).join("");

    return [
      '<div class="hc-risk-map-popup__eyebrow">Couverture groupee</div>',
      "<strong>" + esc(title) + "</strong>",
      structureName ? esc(structureName) : "",
      esc(note),
      '<ul class="hc-risk-map-popup__list">' + listHtml + "</ul>",
      popupActionsHtml(city),
    ].filter(Boolean).join("<br>");
  }

  function groupProfessionalsByCoordinate(rows) {
    var buckets = Object.create(null);
    (Array.isArray(rows) ? rows : []).forEach(function (item) {
      var lat = Number(item && item.latitude);
      var lng = Number(item && item.longitude);
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
      var key = coordinateKey(lat, lng);
      if (!buckets[key]) {
        buckets[key] = {
          lat: lat,
          lng: lng,
          city: (item && item.city) || "Zone visible",
          items: [],
        };
      }
      buckets[key].items.push(item);
    });
    return Object.keys(buckets).map(function (key) { return buckets[key]; });
  }

  function updateKpis(rows) {
    var list = Array.isArray(rows) ? rows : [];
    var cityCounts = Object.create(null);
    var professionCounts = Object.create(null);
    var coordinateBuckets = Object.create(null);
    var topCity = "N/A";
    var topCityCount = -1;
    var dominantProfession = "N/A";
    var dominantProfessionCount = -1;
    var topGroupedCity = "N/A";
    var topGroupedCount = 0;

    list.forEach(function (item) {
      var city = (item && item.city) || "N/A";
      var profession = (item && item.profession) || "N/A";
      cityCounts[city] = (cityCounts[city] || 0) + 1;
      professionCounts[profession] = (professionCounts[profession] || 0) + 1;
      var lat = Number(item && item.latitude);
      var lng = Number(item && item.longitude);
      if (Number.isFinite(lat) && Number.isFinite(lng)) {
        var key = coordinateKey(lat, lng);
        if (!coordinateBuckets[key]) {
          coordinateBuckets[key] = { count: 0, city: city };
        }
        coordinateBuckets[key].count += 1;
      }
    });

    Object.keys(cityCounts).forEach(function (city) {
      if (cityCounts[city] > topCityCount) {
        topCityCount = cityCounts[city];
        topCity = city;
      }
    });

    Object.keys(professionCounts).forEach(function (profession) {
      if (professionCounts[profession] > dominantProfessionCount) {
        dominantProfessionCount = professionCounts[profession];
        dominantProfession = profession;
      }
    });

    Object.keys(coordinateBuckets).forEach(function (key) {
      if (coordinateBuckets[key].count > topGroupedCount) {
        topGroupedCount = coordinateBuckets[key].count;
        topGroupedCity = coordinateBuckets[key].city;
      }
    });

    setText("proMapCitiesCount", String(Object.keys(cityCounts).length));
    setText("proMapProfessionalsCount", String(list.length));
    setText(
      "proMapTopCity",
      topCityCount > 0 ? topCity + " (" + topCityCount + ")" : "N/A"
    );
    setText("proMapTopProfession", dominantProfession);
    updateNarrative(
      Object.keys(cityCounts).length,
      list.length,
      topCity,
      Math.max(0, topCityCount),
      dominantProfession,
      Math.max(0, dominantProfessionCount),
      topGroupedCount,
      topGroupedCity
    );
  }

  async function initProfessionalsMap() {
    var mapEl = document.getElementById("professionalsMap");
    if (!mapEl || typeof L === "undefined") return;
    if (liveManager) liveManager.loading("Analyse de couverture...");

    var fallbackCenter = [48.8566, 2.3522];
    var map = L.map("professionalsMap", { attributionControl: false, zoomControl: true }).setView(fallbackCenter, 11);
    var layer = L.layerGroup().addTo(map);
    var spiderLayer = L.layerGroup().addTo(map);
    var bounds = [];
    var activeSpiderKey = null;

    function clearSpiderfy() {
      activeSpiderKey = null;
      spiderLayer.clearLayers();
      layer.eachLayer(function (marker) {
        setMarkerState(marker, "is-selected", false);
      });
    }

    function spiderfyPositions(centerLatLng, count) {
      var centerPoint = map.latLngToLayerPoint(centerLatLng);
      var radius = Math.max(34, Math.min(84, 24 + count * 5));
      var angleStep = (Math.PI * 2) / Math.max(count, 1);
      var startAngle = -Math.PI / 2;
      var positions = [];
      for (var index = 0; index < count; index += 1) {
        var angle = startAngle + (angleStep * index);
        var point = L.point(
          centerPoint.x + Math.cos(angle) * radius,
          centerPoint.y + Math.sin(angle) * radius
        );
        positions.push(map.layerPointToLatLng(point));
      }
      return positions;
    }

    function spiderfyBucket(bucket, marker) {
      var items = bucket && bucket.items || [];
      if (items.length <= 1) return;
      var bucketKey = coordinateKey(bucket.lat, bucket.lng);
      if (activeSpiderKey === bucketKey) {
        clearSpiderfy();
        return;
      }

      clearSpiderfy();
      activeSpiderKey = bucketKey;
      setMarkerState(marker, "is-selected", true);

      var center = L.latLng(bucket.lat, bucket.lng);
      var positions = spiderfyPositions(center, items.length);
      positions.forEach(function (latLng, index) {
        var item = items[index];
        L.polyline([center, latLng], {
          color: "rgba(59, 130, 246, 0.45)",
          weight: 2,
          opacity: 0.9,
          interactive: false,
        }).addTo(spiderLayer);

        L.marker(latLng, {
          icon: buildRingIcon(isAvailableProfessional(item) ? "professional" : "attention"),
          keyboard: true,
        })
          .addTo(spiderLayer)
          .bindPopup(professionalPopupHtml(item))
          .on("mouseover", function (event) { setMarkerState(event.target, "is-hover", true); })
          .on("mouseout", function (event) { setMarkerState(event.target, "is-hover", false); })
          .on("popupopen", function (event) { setMarkerState(event.target, "is-active", true); })
          .on("popupclose", function (event) { setMarkerState(event.target, "is-active", false); });
      });

      var statusEl = ensureCommandPanelStatus();
      if (statusEl) {
        var noteEl = statusEl.querySelector(".hc-map-command-panel__status-note");
        if (noteEl) {
          noteEl.textContent = spiderfyLabel(items.length, bucket.city || "la zone");
        }
      }
    }

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "",
    }).addTo(map);

    setTimeout(function () {
      map.invalidateSize();
    }, 120);

    map.on("click zoomstart", clearSpiderfy);

    try {
      var res = await fetch(apiUrl, {
        credentials: "same-origin",
        cache: "no-store",
      });
      if (!res.ok) {
        if (liveManager) liveManager.stable("Couverture indisponible", 220);
        return;
      }

      var payload = await res.json();
      if (!payload || payload.status !== "ok" || !Array.isArray(payload.professionals)) {
        if (liveManager) liveManager.stable("Couverture indisponible", 220);
        return;
      }

      var data = Array.isArray(payload.professionals) ? payload.professionals : [];
      updateKpis(data);
      layer.clearLayers();
      clearSpiderfy();
      bounds.length = 0;

      groupProfessionalsByCoordinate(data).forEach(function (bucket) {
        var items = bucket.items || [];
        if (!items.length) return;
        var marker = L.marker([bucket.lat, bucket.lng])
          .setIcon(
            items.length > 1
              ? buildCountIcon(items.length, items.some(isAvailableProfessional) ? "professional" : "attention")
              : buildRingIcon(items.some(isAvailableProfessional) ? "professional" : "attention")
          )
          .addTo(layer)
          .on("click", function (event) {
            if (items.length > 1) {
              L.DomEvent.stopPropagation(event);
              spiderfyBucket(bucket, marker);
            }
          })
          .on("mouseover", function (event) { setMarkerState(event.target, "is-hover", true); })
          .on("mouseout", function (event) { setMarkerState(event.target, "is-hover", false); })
          .on("popupopen", function (event) { setMarkerState(event.target, "is-active", true); })
          .on("popupclose", function (event) { setMarkerState(event.target, "is-active", false); });

        if (items.length > 1) {
          marker.bindTooltip(
            items.length + (items.length > 1 ? " intervenants sur " : " intervenant sur ") + (bucket.city || "la zone"),
            {
              direction: "top",
              offset: [0, -16],
              opacity: 0.96,
            }
          );
        } else {
          marker.bindPopup(professionalPopupHtml(items[0]));
        }

        bounds.push([bucket.lat, bucket.lng]);
      });

      if (bounds.length > 0) {
        map.fitBounds(bounds, { padding: [24, 24], maxZoom: 12 });
      }
      if (liveManager) liveManager.stable("Couverture live", 240);
    } catch (_) {
      // Keep page stable even if endpoint fails.
      if (liveManager) liveManager.stable("Couverture indisponible", 220);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initProfessionalsMap);
  } else {
    initProfessionalsMap();
  }
})();
