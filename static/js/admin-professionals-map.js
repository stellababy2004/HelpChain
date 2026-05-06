(function () {
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

  function ensureCommandPanelStatus() {
    var panel = document.querySelector(".hc-map-command-panel--coverage");
    if (!panel) return null;
    var existing = panel.querySelector(".hc-map-command-panel__status");
    if (existing) return existing;
    var wrapper = document.createElement("div");
    wrapper.className = "hc-map-command-panel__status hc-pressure-calm";
    wrapper.innerHTML =
      '<div class="hc-map-command-panel__status-label">Etat territorial</div>' +
      '<div class="hc-map-command-panel__status-value">Capacite disponible</div>' +
      '<div class="hc-map-command-panel__status-note">Lecture initiale de la couverture en cours.</div>';
    panel.appendChild(wrapper);
    return wrapper;
  }

  function updateNarrative(cityCount, listCount, topCity, topCityCount, dominantProfession, dominantProfessionCount) {
    var statusEl = ensureCommandPanelStatus();
    var panel = document.querySelector(".hc-map-command-panel--coverage");
    var contextBar = document.querySelector(".hc-risk-map-contextbar");
    var queueNote = document.querySelector(".hc-risk-map-queue-note");
    var kpis = document.querySelectorAll(".hc-risk-map-kpi");
    var level = "calm";
    var value = "Capacite disponible";
    var note = listCount > 0
      ? listCount + (listCount > 1 ? " intervenants visibles sur la carte." : " intervenant visible sur la carte.")
      : "Aucune capacite cartographiee disponible pour le moment.";

    if (listCount === 0) {
      level = "watch";
      value = "Couverture limitee";
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
      value = "Capacite specialisee";
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
      '<a class="hc-risk-map-popup__action" href="/ops/cases?city=' + selectedCity + '">Voir les cas lies</a>',
      '<a class="hc-risk-map-popup__action" href="/admin/requests?city=' + selectedCity + '">Voir les demandes</a>',
      "</div>",
    ].join("");
  }

  function professionalPopupHtml(item) {
    var name = esc((item && item.full_name) || "Intervenant");
    var profession = esc((item && item.profession) || "professional");
    var city = esc((item && item.city) || "N/A");
    var availability = esc((item && item.availability) || "unknown");
    var workload = Number(item && item.workload);
    var safeWorkload = Number.isFinite(workload) ? workload : 0;
    var address = esc((item && item.address) || "");
    var coordsLabel = item && item.has_exact_coordinates ? "coordonnees exactes" : "coordonnees ville";
    var actionCity = (item && item.city) || "Boulogne-Billancourt";

    return [
      '<div class="hc-risk-map-popup__eyebrow">Intervenant</div>',
      "<strong>" + name + "</strong>",
      profession,
      city,
      address || "",
      "Disponibilite : " + availability,
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

  function updateKpis(rows) {
    var list = Array.isArray(rows) ? rows : [];
    var cityCounts = Object.create(null);
    var professionCounts = Object.create(null);
    var topCity = "N/A";
    var topCityCount = -1;
    var dominantProfession = "N/A";
    var dominantProfessionCount = -1;

    list.forEach(function (item) {
      var city = (item && item.city) || "N/A";
      var profession = (item && item.profession) || "N/A";
      cityCounts[city] = (cityCounts[city] || 0) + 1;
      professionCounts[profession] = (professionCounts[profession] || 0) + 1;
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
      Math.max(0, dominantProfessionCount)
    );
  }

  async function initProfessionalsMap() {
    var mapEl = document.getElementById("professionalsMap");
    if (!mapEl || typeof L === "undefined") return;

    var fallbackCenter = [48.8566, 2.3522];
    var map = L.map("professionalsMap").setView(fallbackCenter, 11);
    var layer = L.layerGroup().addTo(map);
    var bounds = [];

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    setTimeout(function () {
      map.invalidateSize();
    }, 120);

    try {
      var res = await fetch("/admin/api/professionals", {
        credentials: "same-origin",
        cache: "no-store",
      });
      if (!res.ok) return;

      var payload = await res.json();
      if (!payload || payload.status !== "ok" || !Array.isArray(payload.professionals)) {
        return;
      }

      var data = payload.professionals;
      updateKpis(data);
      layer.clearLayers();
      bounds.length = 0;

      data.forEach(function (item) {
        var lat = Number(item && item.latitude);
        var lng = Number(item && item.longitude);
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;

        L.marker([lat, lng])
          .setIcon(buildRingIcon("professional"))
          .addTo(layer)
          .bindPopup(professionalPopupHtml(item))
          .on("mouseover", function (event) { setMarkerState(event.target, "is-hover", true); })
          .on("mouseout", function (event) { setMarkerState(event.target, "is-hover", false); })
          .on("popupopen", function (event) { setMarkerState(event.target, "is-active", true); })
          .on("popupclose", function (event) { setMarkerState(event.target, "is-active", false); });

        bounds.push([lat, lng]);
      });

      if (bounds.length > 0) {
        map.fitBounds(bounds, { padding: [24, 24], maxZoom: 12 });
      }
    } catch (_) {
      // Keep page stable even if endpoint fails.
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initProfessionalsMap);
  } else {
    initProfessionalsMap();
  }
})();
