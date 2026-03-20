(function () {
  var root = document.querySelector("[data-risk-map-root]");
  if (!root) {
    return;
  }

  var endpoint = root.dataset.endpoint || "";
  var defaultLat = Number(root.dataset.defaultLat || 46.603354);
  var defaultLng = Number(root.dataset.defaultLng || 1.888334);
  var defaultZoom = Number(root.dataset.defaultZoom || 6);
  var mapEl = document.getElementById("riskMapCanvas");
  var stateBar = document.getElementById("riskMapStateBar");

  var map = null;
  var markersLayer = null;
  var refreshTimer = null;

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

  function setState(kind, text) {
    if (!stateBar) {
      return;
    }
    stateBar.classList.remove(
      "alert-secondary",
      "alert-success",
      "alert-warning",
      "alert-danger"
    );
    if (kind === "success") {
      stateBar.classList.add("alert-success");
    } else if (kind === "empty") {
      stateBar.classList.add("alert-warning");
    } else if (kind === "error") {
      stateBar.classList.add("alert-danger");
    } else {
      stateBar.classList.add("alert-secondary");
    }
    stateBar.textContent = text;
  }

  function ensureMap() {
    if (!mapEl) {
      return false;
    }
    if (typeof L === "undefined") {
      setState("error", "Map library could not be loaded.");
      return false;
    }
    if (map) {
      return true;
    }

    map = L.map(mapEl).setView([defaultLat, defaultLng], defaultZoom);
    markersLayer = L.layerGroup().addTo(map);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    window.setTimeout(function () {
      map.invalidateSize();
    }, 0);

    return true;
  }

  function popupHtml(item) {
    return [
      "<strong>" + escapeHtml(item.title || "Case") + "</strong>",
      item.city ? "City: " + escapeHtml(item.city) : "",
      "Risk score: " + escapeHtml(item.risk_score || 0),
      "Risk level: " + escapeHtml(item.risk_level || "low"),
      item.category ? "Category: " + escapeHtml(item.category) : "",
      item.status ? "Status: " + escapeHtml(item.status) : "",
      item.updated_at ? "Updated: " + escapeHtml(item.updated_at) : "",
    ]
      .filter(Boolean)
      .join("<br>");
  }

  function renderItems(items) {
    var rows = Array.isArray(items) ? items : [];
    var bounds = [];
    var maxRisk = -1;
    var maxRiskLabel = "";

    markersLayer.clearLayers();

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
      marker.addTo(markersLayer);
      bounds.push([lat, lng]);

      if (score > maxRisk) {
        maxRisk = score;
        maxRiskLabel = item && (item.title || item.city || ("Case #" + item.id));
      }
    });

    if (bounds.length === 0) {
      map.setView([defaultLat, defaultLng], defaultZoom);
      setState(
        "empty",
        "No geolocated risk data is available for the current admin scope."
      );
      return;
    }

    map.fitBounds(bounds, { padding: [24, 24], maxZoom: 12 });
    setState(
      "success",
      String(bounds.length) +
        (bounds.length > 1 ? " risk points loaded." : " risk point loaded.") +
        (maxRisk >= 0 ? " Highest score: " + String(maxRisk) + " (" + String(maxRiskLabel) + ")." : "")
    );
  }

  async function loadRiskMap() {
    if (!ensureMap() || !endpoint) {
      return;
    }
    setState("loading", "Loading territorial risk data...");

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
      setState("error", "Territorial risk data could not be loaded.");
    }
  }

  function startRefresh() {
    if (refreshTimer) {
      window.clearInterval(refreshTimer);
    }
    refreshTimer = window.setInterval(loadRiskMap, 30000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      loadRiskMap();
      startRefresh();
    });
  } else {
    loadRiskMap();
    startRefresh();
  }

  window.addEventListener("resize", function () {
    if (map) {
      map.invalidateSize();
    }
  });
})();
