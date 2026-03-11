(function () {
  function colorForRisk(score) {
    if (score > 70) return "#c62828";
    if (score > 40) return "#ef6c00";
    return "#2e7d32";
  }

  function updateStatusBar(data) {
    var bar = document.getElementById("riskMapStatusBar");
    bar.classList.remove(
      "alert-secondary",
      "alert-success",
      "alert-warning",
      "alert-danger"
    );
    var mainEl = document.getElementById("riskMapStatusMain");
    var secondaryEl = document.getElementById("riskMapStatusSecondary");
    if (!bar || !mainEl || !secondaryEl) return;

    bar.classList.remove("alert-danger", "alert-warning", "alert-success", "alert-secondary");

    var rows = Array.isArray(data) ? data : [];
    if (rows.length === 0) {
      bar.classList.add("alert-secondary");
      mainEl.textContent = "Aucune donnée territoriale disponible";
      secondaryEl.textContent = "";
      return;
    }

    var totalCases = 0;
    var maxRisk = -Infinity;
    var maxRiskCity = "N/A";

    rows.forEach(function (item) {
      var cases = Number(item && item.cases);
      if (Number.isFinite(cases) && cases > 0) totalCases += cases;

      var risk = Number(item && item.avg_risk);
      if (Number.isFinite(risk) && risk > maxRisk) {
        maxRisk = risk;
        maxRiskCity = (item && item.city) || "N/A";
      }
    });

    if (maxRisk > 70) {
      bar.classList.add("alert-danger");
      mainEl.textContent = "Zone critique détectée : " + maxRiskCity;
    } else if (maxRisk > 40) {
      bar.classList.add("alert-warning");
      mainEl.textContent = "Zone sensible détectée : " + maxRiskCity;
    } else {
      bar.classList.add("alert-success");
      mainEl.textContent = "Situation territoriale stable";
    }

    secondaryEl.textContent =
      String(totalCases) +
      (totalCases > 1 ? " cas actifs à suivre" : " cas actif à suivre");
  }

  function updateKpis(data) {
    var citiesEl = document.getElementById("riskMapCitiesCount");
    var casesEl = document.getElementById("riskMapCasesCount");
    var avgRiskEl = document.getElementById("riskMapAvgRisk");
    var topCityEl = document.getElementById("riskMapTopCity");

    if (!citiesEl || !casesEl || !avgRiskEl || !topCityEl) return;

    var rows = Array.isArray(data) ? data : [];
    var citiesCount = rows.length;
    var totalCases = 0;
    var riskSum = 0;
    var riskCount = 0;
    var maxRisk = -Infinity;
    var maxRiskCity = "N/A";

    rows.forEach(function (item) {
      var cases = Number(item && item.cases);
      if (Number.isFinite(cases) && cases > 0) totalCases += cases;

      var risk = Number(item && item.avg_risk);
      if (Number.isFinite(risk)) {
        riskSum += risk;
        riskCount += 1;
        if (risk > maxRisk) {
          maxRisk = risk;
          maxRiskCity = (item && item.city) || "N/A";
        }
      }
    });

    var avgRisk = riskCount > 0 ? (riskSum / riskCount) : 0;
    citiesEl.textContent = String(citiesCount);
    casesEl.textContent = String(totalCases);
    avgRiskEl.textContent = avgRisk.toFixed(1);
    topCityEl.textContent = maxRiskCity;
  }

  async function initRiskMap() {
    var mapEl = document.getElementById("map");
    if (!mapEl || typeof L === "undefined") return;

    var fallbackCenter = [48.84, 2.24];
    var map = L.map("map").setView(fallbackCenter, 12);
    var layer = L.layerGroup().addTo(map);
    var bounds = [];

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    // Helps Leaflet compute dimensions correctly in card-based layouts.
    setTimeout(function () {
      map.invalidateSize();
    }, 0);

    try {
      var res = await fetch("/admin/api/risk-map", { credentials: "same-origin" });
      if (!res.ok) return;
      var data = await res.json();
      updateKpis(data);
      updateStatusBar(data);
      layer.clearLayers();
      bounds.length = 0;

      data.forEach(function (item) {
        var lat = Number(item.lat);
        var lng = Number(item.lng);
        // Defensive guard: skip malformed points.
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;

        var pt = [lat, lng];
        var score = Number(item.avg_risk || 0);
        var color = colorForRisk(score);
        var radius = 300 + Math.min(Number(item.cases || 0), 100) * 8;

        L.circle(pt, { radius: radius, color: color, weight: 2, fillOpacity: 0.2 })
          .addTo(layer)
          .bindPopup(
            "<strong>" +
              (item.city || "Inconnu") +
              "</strong><br>" +
              "Risque moyen: " +
              score.toFixed(1) +
              "<br>" +
              "Cas: " +
              (item.cases || 0) +
              "<br>" +
              "Niveau: " +
              (item.risk_level || "low")
          );

        bounds.push(pt);
      });

      if (bounds.length > 0) {
        map.fitBounds(bounds, { padding: [24, 24], maxZoom: 13 });
      }
    } catch (_) {
      // Keep page stable even if endpoint/network fails.
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initRiskMap);
  } else {
    initRiskMap();
  }
})();
