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
    }, 0);

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
          .bindPopup(professionalPopupHtml(item));

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
