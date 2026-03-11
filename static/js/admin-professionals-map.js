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

  function updateKpis(rows) {
    var cities = Array.isArray(rows) ? rows.length : 0;
    var totalPros = 0;
    var topCity = "N/A";
    var topCityCount = -1;
    var professionScores = Object.create(null);

    (rows || []).forEach(function (item) {
      var count = Number(item && item.count);
      var safeCount = Number.isFinite(count) ? count : 0;
      totalPros += safeCount;

      if (safeCount > topCityCount) {
        topCityCount = safeCount;
        topCity = (item && item.city) || "N/A";
      }

      var topProf = Array.isArray(item && item.top_professions) ? item.top_professions[0] : "";
      if (topProf) {
        professionScores[topProf] = (professionScores[topProf] || 0) + safeCount;
      }
    });

    var dominantProfession = "N/A";
    var dominantScore = -1;
    Object.keys(professionScores).forEach(function (name) {
      if (professionScores[name] > dominantScore) {
        dominantScore = professionScores[name];
        dominantProfession = name;
      }
    });

    setText("proMapCitiesCount", String(cities));
    setText("proMapProfessionalsCount", String(totalPros));
    setText("proMapTopCity", topCityCount > 0 ? (topCity + " (" + topCityCount + ")") : "N/A");
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
      var res = await fetch("/admin/api/professionals-map", { credentials: "same-origin" });
      if (!res.ok) return;
      var rows = await res.json();
      var data = Array.isArray(rows) ? rows : [];

      updateKpis(data);
      layer.clearLayers();
      bounds.length = 0;

      data.forEach(function (item) {
        var lat = Number(item && item.lat);
        var lng = Number(item && item.lng);
        var count = Number(item && item.count);
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;

        var safeCount = Number.isFinite(count) ? count : 0;
        var radius = 220 + Math.min(safeCount, 120) * 14;
        var professions = Array.isArray(item && item.top_professions) ? item.top_professions : [];
        var topProfessions = professions.length ? professions.map(esc).join(", ") : "N/A";
        var city = esc((item && item.city) || "N/A");

        L.circle([lat, lng], {
          radius: radius,
          color: "#1d4ed8",
          weight: 2,
          fillColor: "#60a5fa",
          fillOpacity: 0.26,
        })
          .addTo(layer)
          .bindPopup(
            "<strong>" + city + "</strong><br>" +
              "Professionnels: " + String(safeCount) + "<br>" +
              "Top métiers: " + topProfessions
          );

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
