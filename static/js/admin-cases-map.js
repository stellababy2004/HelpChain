(function () {
  "use strict";

  const container = document.getElementById("cases-map");
  if (!container || typeof L === "undefined") return;

  const map = L.map(container).setView([48.8566, 2.3522], 12);

  L.tileLayer(
    "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
      
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors'
    }
  ).addTo(map);

  const colors = {
    high: "#dc3545",
    medium: "#f59e0b",
    low: "#198754"
  };

  fetch("/admin/api/cases/map", {
    credentials: "same-origin"
  })
    .then(function (response) {
      if (!response.ok) throw new Error("Map API unavailable");
      return response.json();
    })
    .then(function (data) {
      const bounds = [];

      (data.cases || []).forEach(function (item) {
        const lat = Number(item.lat);
        const lng = Number(item.lng);

        if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
        if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return;

        const color = colors[item.risk_level] || colors.low;

        const marker = L.circleMarker([lat, lng], {
          radius: 9,
          color: "#ffffff",
          weight: 2,
          fillColor: color,
          fillOpacity: 0.95
        }).addTo(map);

        const popup = document.createElement("div");

        const title = document.createElement("strong");
        title.textContent = "Case #" + String(item.id);
        popup.appendChild(title);

        [
          ["Status", item.status],
          ["Risk", item.risk_level]
        ].forEach(function (entry) {
          const line = document.createElement("div");
          line.textContent = entry[0] + ": " + String(entry[1] || "");
          popup.appendChild(line);
        });

        marker.bindPopup(popup);
        bounds.push([lat, lng]);
      });

      if (bounds.length > 0) {
        map.fitBounds(bounds, {
          padding: [35, 35],
          maxZoom: 14
        });
      }
    })
    .catch(function (error) {
      console.error("HelpChain cases map:", error);
    });
})();
