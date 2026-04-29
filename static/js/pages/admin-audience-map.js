(function () {
  var root = document.querySelector("[data-audience-map-root]");
  if (!root) {
    return;
  }

  if (typeof L === "undefined") {
    console.error("[AudienceMap] Leaflet is not loaded. Check script order / CSP.");
    return;
  }

  var mapEl = document.getElementById("audienceMap");
  if (!mapEl) {
    return;
  }

  var LOCATIONS = [
    { slug: "paris", city: "Paris", departmentNumber: "75", departmentName: "Paris", lat: 48.8566, lng: 2.3522, needs: 12, structures: 8, priority: "Haute", recommendation: "Prioriser les comptes publics deja engages et proposer un cadrage pilote." },
    { slug: "saint-denis", city: "Saint-Denis", departmentNumber: "93", departmentName: "Seine-Saint-Denis", lat: 48.9362, lng: 2.3574, needs: 9, structures: 6, priority: "Haute", recommendation: "Approcher les acteurs sociaux et associations de coordination locale." },
    { slug: "montreuil", city: "Montreuil", departmentNumber: "93", departmentName: "Seine-Saint-Denis", lat: 48.8638, lng: 2.4485, needs: 8, structures: 5, priority: "Haute", recommendation: "Prioriser les associations locales et dispositifs d'accompagnement." },
    { slug: "nanterre", city: "Nanterre", departmentNumber: "92", departmentName: "Hauts-de-Seine", lat: 48.8924, lng: 2.206, needs: 7, structures: 5, priority: "Haute", recommendation: "Cibler les structures departementales et services sociaux." },
    { slug: "creteil", city: "Creteil", departmentNumber: "94", departmentName: "Val-de-Marne", lat: 48.7904, lng: 2.4556, needs: 6, structures: 4, priority: "Moyenne", recommendation: "Identifier les interlocuteurs municipaux et associatifs." },
    { slug: "boulogne-billancourt", city: "Boulogne-Billancourt", departmentNumber: "92", departmentName: "Hauts-de-Seine", lat: 48.8397, lng: 2.2399, needs: 5, structures: 4, priority: "Moyenne", recommendation: "Tester une approche aupres des structures privees et associatives." },
    { slug: "argenteuil", city: "Argenteuil", departmentNumber: "95", departmentName: "Val-d'Oise", lat: 48.9472, lng: 2.2467, needs: 5, structures: 3, priority: "Moyenne", recommendation: "Qualifier les besoins avant lancement d'un pilote." },
    { slug: "versailles", city: "Versailles", departmentNumber: "78", departmentName: "Yvelines", lat: 48.8049, lng: 2.1204, needs: 4, structures: 3, priority: "Observation", recommendation: "Surveiller le potentiel institutionnel avant prospection active." },
    { slug: "cergy", city: "Cergy", departmentNumber: "95", departmentName: "Val-d'Oise", lat: 49.0364, lng: 2.0761, needs: 4, structures: 3, priority: "Observation", recommendation: "Garder en veille pour extension Val-d'Oise." },
    { slug: "evry-courcouronnes", city: "Evry-Courcouronnes", departmentNumber: "91", departmentName: "Essonne", lat: 48.623, lng: 2.429, needs: 4, structures: 3, priority: "Observation", recommendation: "Veille territoriale pour extension Essonne." },
    { slug: "aulnay-sous-bois", city: "Aulnay-sous-Bois", departmentNumber: "93", departmentName: "Seine-Saint-Denis", lat: 48.9382, lng: 2.4943, needs: 6, structures: 4, priority: "Moyenne", recommendation: "Structurer un ciblage des dispositifs de coordination locale et municipale." },
    { slug: "ivry-sur-seine", city: "Ivry-sur-Seine", departmentNumber: "94", departmentName: "Val-de-Marne", lat: 48.813, lng: 2.3889, needs: 5, structures: 4, priority: "Moyenne", recommendation: "Qualifier les acteurs associatifs et les relais de proximite avant prise de contact." },
    { slug: "colombes", city: "Colombes", departmentNumber: "92", departmentName: "Hauts-de-Seine", lat: 48.9226, lng: 2.2522, needs: 5, structures: 4, priority: "Moyenne", recommendation: "Positionner HelpChain sur les besoins de coordination inter-services et reporting." },
    { slug: "courbevoie", city: "Courbevoie", departmentNumber: "92", departmentName: "Hauts-de-Seine", lat: 48.8973, lng: 2.256, needs: 4, structures: 3, priority: "Observation", recommendation: "Maintenir une veille active avant acceleration commerciale." },
  ];

  var REVENUE_RADAR = [
    { territory: "Paris (75)", departmentNumber: "75", priority: "Haute", repeatLabel: "2 repeat visits", pages: ["/offre", "/demo", "/deploiement"], score: 82, potential: 590, focusSlug: "paris" },
    { territory: "Hauts-de-Seine (92)", departmentNumber: "92", priority: "Moyenne", repeatLabel: "Viewed /professionnels", pages: ["/professionnels"], score: 64, potential: 390, focusSlug: "nanterre" },
    { territory: "Seine-Saint-Denis (93)", departmentNumber: "93", priority: "Haute", repeatLabel: "Viewed /contact twice", pages: ["/contact", "/contact"], score: 78, potential: 590, focusSlug: "saint-denis" },
    { territory: "Yvelines (78)", departmentNumber: "78", priority: "Observation", repeatLabel: "Signal leger", pages: ["/offre"], score: 41, potential: 190, focusSlug: "versailles" },
  ];

  var DEPARTMENT_SCORES = [
    { number: "75", name: "Paris", score: 82, focusSlug: "paris" },
    { number: "92", name: "Hauts-de-Seine", score: 76, focusSlug: "nanterre" },
    { number: "93", name: "Seine-Saint-Denis", score: 74, focusSlug: "saint-denis" },
    { number: "94", name: "Val-de-Marne", score: 63, focusSlug: "creteil" },
    { number: "95", name: "Val-d'Oise", score: 55, focusSlug: "argenteuil" },
    { number: "78", name: "Yvelines", score: 41, focusSlug: "versailles" },
    { number: "91", name: "Essonne", score: 39, focusSlug: "evry-courcouronnes" },
  ];

  var LIVE_SIGNALS = [
    { territory: "Paris", detail: "Session viewed /offre then /demo", when: "2 min ago", focusSlug: "paris" },
    { territory: "Nanterre", detail: "Session returned 3rd time this week", when: "11 min ago", focusSlug: "nanterre" },
    { territory: "Saint-Denis", detail: "Session viewed /contact", when: "18 min ago", focusSlug: "saint-denis" },
  ];

  var PIPELINE_SHORTLIST = [
    "CCAS Paris",
    "Associations 92",
    "Reseau insertion 93",
    "Structures multi-sites 94",
    "Ville pilote 95",
  ];

  var HEAT_ZONES = [
    { lat: 48.8566, lng: 2.3522, radius: 18000, color: "#1d4ed8", fillOpacity: 0.14, opacity: 0.2 },
    { lat: 48.8924, lng: 2.206, radius: 15000, color: "#2563eb", fillOpacity: 0.12, opacity: 0.18 },
    { lat: 48.9362, lng: 2.3574, radius: 15500, color: "#2563eb", fillOpacity: 0.12, opacity: 0.18 },
    { lat: 48.7904, lng: 2.4556, radius: 12500, color: "#3b82f6", fillOpacity: 0.09, opacity: 0.14 },
    { lat: 48.9472, lng: 2.2467, radius: 12000, color: "#60a5fa", fillOpacity: 0.08, opacity: 0.13 },
    { lat: 48.8049, lng: 2.1204, radius: 11000, color: "#93c5fd", fillOpacity: 0.035, opacity: 0.1 },
    { lat: 48.623, lng: 2.429, radius: 10500, color: "#93c5fd", fillOpacity: 0.05, opacity: 0.09 },
  ];

  var PRIORITY_META = {
    Haute: { cssClass: "audience-marker--high", popupEyebrow: "Territoire prioritaire", action: "Planifier une prise de contact cette semaine.", intensity: "High", zoom: 12, zIndexOffset: 500 },
    Moyenne: { cssClass: "audience-marker--medium", popupEyebrow: "Territoire a qualifier", action: "Qualifier les interlocuteurs avant prospection.", intensity: "Medium", zoom: 11.4, zIndexOffset: 350 },
    Observation: { cssClass: "audience-marker--watch", popupEyebrow: "Territoire en observation", action: "Conserver en veille commerciale.", intensity: "Watch", zoom: 11, zIndexOffset: 220 },
  };

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function setText(id, value) {
    var el = document.getElementById(id);
    if (el) {
      el.textContent = String(value || "");
    }
  }

  function getPriorityMeta(priority) {
    return PRIORITY_META[priority] || PRIORITY_META.Observation;
  }

  function formatDepartment(point) {
    return point.departmentNumber + " " + point.departmentName;
  }

  function formatEuro(value) {
    try {
      return new Intl.NumberFormat("fr-FR", {
        style: "currency",
        currency: "EUR",
        maximumFractionDigits: 0,
      }).format(Number(value) || 0);
    } catch (error) {
      return "\u20ac" + String(value || 0);
    }
  }

  function euroPerMonth(value) {
    return formatEuro(value) + "/mo";
  }

  function buildPopupHtml(point) {
    var meta = getPriorityMeta(point.priority);
    return [
      '<div class="hc-audience-popup">',
      '<div class="hc-audience-popup__eyebrow">' + escapeHtml(meta.popupEyebrow) + "</div>",
      '<div class="hc-audience-popup__titleWrap">',
      "<strong>" + escapeHtml(point.city) + "</strong>",
      '<span class="hc-audience-popup__dept">Departement ' + escapeHtml(formatDepartment(point)) + "</span>",
      "</div>",
      '<div class="hc-audience-popup__stats">',
      "<span><strong>Demandes detectees</strong><em>" + escapeHtml(point.needs) + "</em></span>",
      "<span><strong>Structures cibles</strong><em>" + escapeHtml(point.structures) + "</em></span>",
      "<span><strong>Priorite</strong><em>" + escapeHtml(point.priority) + "</em></span>",
      "</div>",
      '<div class="hc-audience-popup__recommendation"><strong>Recommandation</strong><p>' + escapeHtml(point.recommendation) + "</p></div>",
      "</div>",
    ].join("");
  }

  function buildMarkerIcon(point) {
    var meta = getPriorityMeta(point.priority);
    return L.divIcon({
      className: "audience-markerWrap",
      html:
        '<span class="audience-marker ' +
        meta.cssClass +
        '" data-priority="' +
        escapeHtml(point.priority) +
        '">' +
        '<span class="audience-marker__core"></span>' +
        '<span class="audience-marker__pulse"></span>' +
        "</span>",
      iconSize: [36, 36],
      iconAnchor: [18, 18],
      popupAnchor: [0, -14],
    });
  }

  function buildActionSuggestion(priority) {
    return getPriorityMeta(priority).action;
  }

  function getEstimatedDemand(row) {
    var city = cityRegistry[row.focusSlug];
    return city ? city.needs : 0;
  }

  function buildFounderAction(row) {
    var estimatedDemand = getEstimatedDemand(row);
    if (row.priority === "Haute" && estimatedDemand >= 8) {
      return "Outreach now";
    }
    if (row.priority === "Moyenne") {
      return "Email cible aujourd'hui";
    }
    if (row.priority === "Observation") {
      return "Garder en observation";
    }
    return "Preparer campagne locale";
  }

  function buildFounderReason(row) {
    var estimatedDemand = getEstimatedDemand(row);
    if (row.priority === "Haute" && estimatedDemand >= 8) {
      return "Signaux recurrents et demande estimee elevee.";
    }
    if (row.priority === "Moyenne") {
      return "Interet qualifie avec marge pour une relance structuree.";
    }
    if (row.priority === "Observation") {
      return "Momentum utile, mais encore trop leger pour accelerer.";
    }
    return "Signaux a consolider avant passage en priorite haute.";
  }

  function buildFounderBadge(row) {
    var estimatedDemand = getEstimatedDemand(row);
    if (row.priority === "Haute" && estimatedDemand >= 8) {
      return "Haute priorite";
    }
    if (row.priority === "Moyenne" || row.priority === "Haute") {
      return "Chaud";
    }
    return "Faible";
  }

  function founderBadgeClass(label) {
    if (label === "Haute priorite") {
      return "is-high";
    }
    if (label === "Chaud") {
      return "is-warm";
    }
    return "is-watch";
  }

  function founderSortWeight(row) {
    var territory = row.territory || "";
    if (territory.indexOf("Paris") === 0) {
      return 0;
    }
    if (territory.indexOf("Hauts-de-Seine") === 0) {
      return 1;
    }
    if (territory.indexOf("Seine-Saint-Denis") === 0) {
      return 2;
    }
    return 3;
  }

  function buildFounderQueue() {
    return REVENUE_RADAR.slice()
      .sort(function (a, b) {
        var orderDiff = founderSortWeight(a) - founderSortWeight(b);
        if (orderDiff !== 0) {
          return orderDiff;
        }
        return b.score - a.score;
      })
      .map(function (row) {
        var badge = buildFounderBadge(row);
        return {
          territory: row.territory,
          reason: buildFounderReason(row),
          action: buildFounderAction(row),
          badge: badge,
          badgeClass: founderBadgeClass(badge),
          focusSlug: row.focusSlug,
        };
      });
  }

  function estimatedOpportunityThisWeek() {
    return REVENUE_RADAR.reduce(function (sum, row) {
      return sum + (Number(row.potential) || 0);
    }, 0);
  }

  function runSafeRender(label, renderFn) {
    try {
      renderFn();
    } catch (error) {
      console.error("[AudienceMap] " + label + " failed:", error);
    }
  }

  function createControl(position, className, innerHtml) {
    var control = L.control({ position: position });
    control.onAdd = function () {
      var el = L.DomUtil.create("div", className);
      el.innerHTML = innerHtml;
      L.DomEvent.disableClickPropagation(el);
      return el;
    };
    control.addTo(map);
    return control;
  }

  function pulseSidebar() {
    var card = document.getElementById("audienceMapDetailCard");
    if (!card) {
      return;
    }
    card.classList.remove("is-refreshing");
    window.requestAnimationFrame(function () {
      card.classList.add("is-refreshing");
      window.setTimeout(function () {
        card.classList.remove("is-refreshing");
      }, 280);
    });
  }

  function recommendationLogic() {
    return [
      {
        title: "Prioriser Paris cette semaine.",
        reason: "Fort volume + pages commerciales vues.",
        focusSlug: "paris",
      },
      {
        title: "Relancer Hauts-de-Seine via email cible.",
        reason: "Signal modere mais solvabilite elevee.",
        focusSlug: "nanterre",
      },
      {
        title: "Tester campagne locale Seine-Saint-Denis.",
        reason: "Interet croissant.",
        focusSlug: "saint-denis",
      },
      {
        title: "Suspendre Yvelines pour l'instant.",
        reason: "Momentum trop faible pour concentrer du temps commercial.",
        focusSlug: "versailles",
      },
    ];
  }

  var defaultLat = Number(root.dataset.defaultLat || 48.8566);
  var defaultLng = Number(root.dataset.defaultLng || 2.3522);
  var defaultZoom = Number(root.dataset.defaultZoom || 10);
  var totalNeeds = LOCATIONS.reduce(function (sum, point) { return sum + point.needs; }, 0);
  var totalStructures = LOCATIONS.reduce(function (sum, point) { return sum + point.structures; }, 0);

  var map = L.map(mapEl, {
    zoomControl: true,
    attributionControl: true,
  }).setView([defaultLat, defaultLng], defaultZoom);

  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    maxZoom: 19,
    subdomains: "abcd",
    attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
  }).addTo(map);

  var heatLayer = L.layerGroup().addTo(map);
  var overlayLayer = L.layerGroup().addTo(map);
  var markerLayer = L.layerGroup().addTo(map);

  HEAT_ZONES.forEach(function (zone) {
    L.circle([zone.lat, zone.lng], {
      radius: zone.radius,
      stroke: false,
      color: zone.color,
      fillColor: zone.color,
      fillOpacity: Math.min(zone.fillOpacity, 0.045),
      opacity: zone.opacity,
    }).addTo(heatLayer);
  });

  var expansionRing = L.circle([48.8566, 2.3522], {
    radius: 32000,
    color: "#2563eb",
    weight: 2,
    opacity: 0.25,
    fillColor: "#2563eb",
    fillOpacity: 0.035,
    dashArray: "8 6",
  }).addTo(overlayLayer);

  var coreRing = L.circle([48.8566, 2.3522], {
    radius: 15000,
    color: "#2563eb",
    weight: 1.5,
    opacity: 0.22,
    fillColor: "#2563eb",
    fillOpacity: 0.04,
  }).addTo(overlayLayer);

  L.marker([48.8566, 2.3522], {
    interactive: false,
    keyboard: false,
    icon: L.divIcon({
      className: "audience-zone-labelWrap",
      html: '<span class="audience-zone-label">Zone cible IDF</span>',
      iconSize: [120, 24],
      iconAnchor: [60, 12],
    }),
  }).addTo(overlayLayer);

  createControl(
    "topleft",
    "audience-map-summary",
    [
      "<div class=\"audience-map-summary__eyebrow\">Ile-de-France</div>",
      "<div class=\"audience-map-summary__title\">Territoires detectes: " + LOCATIONS.length + "</div>",
      "<div class=\"audience-map-summary__stats\">",
      "<span><strong>" + totalNeeds + "</strong><em>Demandes estimees</em></span>",
      "<span><strong>" + totalStructures + "</strong><em>Structures cibles</em></span>",
      "</div>",
    ].join("")
  );

  createControl(
    "bottomleft",
    "audience-map-legend",
    [
      '<div class="audience-map-legend__title">Priorite</div>',
      '<div class="audience-map-legend__item"><span class="audience-map-legend__dot audience-map-legend__dot--high"></span>Haute</div>',
      '<div class="audience-map-legend__item"><span class="audience-map-legend__dot audience-map-legend__dot--medium"></span>Moyenne</div>',
      '<div class="audience-map-legend__item"><span class="audience-map-legend__dot audience-map-legend__dot--watch"></span>Observation</div>',
      '<div class="audience-map-legend__section">Zones</div>',
      '<div class="audience-map-legend__item"><span class="audience-map-legend__zone audience-map-legend__zone--core"></span>coeur</div>',
      '<div class="audience-map-legend__item"><span class="audience-map-legend__zone audience-map-legend__zone--expansion"></span>extension</div>',
      "</div>",
    ].join("")
  );

  var markerRegistry = {};
  var cityRegistry = {};
  var activeSlug = null;
  var cityListEl = document.getElementById("audienceMapCityList");
  var radarEl = document.getElementById("audienceRevenueRadar");
  var radarEmptyEl = document.getElementById("audienceRevenueRadarEmpty");
  var deptScoresEl = document.getElementById("audienceDepartmentScores");
  var liveSignalsEl = document.getElementById("audienceLiveSignals");
  var recommendationsEl = document.getElementById("audienceRecommendations");
  var forecastEl = document.getElementById("audienceForecastPanel");
  var shortlistEl = document.getElementById("audienceProspectionShortlist");
  var founderQueueEl = document.getElementById("audienceFounderQueue");
  var estimatedOpportunityEl = document.getElementById("audienceEstimatedOpportunityValue");

  function setMarkerState(marker, state, enabled) {
    var icon = marker && marker.getElement();
    if (!icon) {
      return;
    }
    icon.classList.toggle(state, enabled);
  }

  function setActiveMarker(slug) {
    if (activeSlug && markerRegistry[activeSlug]) {
      markerRegistry[activeSlug].setZIndexOffset(0);
      setMarkerState(markerRegistry[activeSlug], "is-active", false);
    }
    activeSlug = slug;
    if (markerRegistry[slug]) {
      markerRegistry[slug].setZIndexOffset(getPriorityMeta(cityRegistry[slug].priority).zIndexOffset);
      setMarkerState(markerRegistry[slug], "is-active", true);
    }
  }

  function highlightButtons(container, attribute, value) {
    if (!container) {
      return;
    }
    Array.prototype.forEach.call(container.querySelectorAll("[" + attribute + "]"), function (node) {
      node.classList.toggle("is-active", node.getAttribute(attribute) === value);
    });
  }

  function updateSidebar(point) {
    setText("audienceMapDetailCity", point.city);
    setText("audienceMapDetailDemand", point.needs);
    setText("audienceMapDetailStructures", point.structures);
    setText("audienceMapDetailDepartment", formatDepartment(point));
    setText("audienceMapDetailPriority", point.priority);
    setText("audienceMapDetailIntensity", getPriorityMeta(point.priority).intensity);
    setText("audienceMapDetailRecommendation", point.recommendation);
    setText("audienceMapDetailAction", buildActionSuggestion(point.priority));
    highlightButtons(cityListEl, "data-city-slug", point.slug);
    pulseSidebar();
  }

  function focusCity(slug) {
    var marker = markerRegistry[slug];
    var point = cityRegistry[slug];
    if (!marker || !point) {
      return;
    }
    map.flyTo([point.lat, point.lng], getPriorityMeta(point.priority).zoom, {
      duration: 0.6,
    });
    marker.openPopup();
    updateSidebar(point);
    setActiveMarker(slug);
  }

  function scoreClass(score) {
    if (score >= 70) {
      return "is-hot";
    }
    if (score >= 40) {
      return "is-warm";
    }
    return "is-cold";
  }

  function renderRevenueRadar() {
    if (!radarEl) {
      return;
    }
    if (!REVENUE_RADAR.length) {
      if (radarEmptyEl) {
        radarEmptyEl.classList.remove("d-none");
      }
      return;
    }
    REVENUE_RADAR.forEach(function (row, index) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "audience-radar-row";
      button.setAttribute("data-radar-focus", row.focusSlug);
      button.innerHTML = [
        '<span class="audience-radar-row__rank">' + (index + 1) + ".</span>",
        '<span class="audience-radar-row__main">',
        '<strong>' + escapeHtml(row.territory) + "</strong>",
        '<span class="audience-radar-row__meta">Intent: ' + escapeHtml(row.priority) + " - " + escapeHtml(row.repeatLabel) + "</span>",
        '<span class="audience-radar-row__pages">Pages vues: ' + escapeHtml(row.pages.join(" ")) + "</span>",
        "</span>",
        '<span class="audience-radar-row__score">',
        '<span class="audience-inline-tag">ESTIMATED</span>',
        '<span class="audience-radar-row__badge">' + escapeHtml(row.priority) + "</span>",
        '<strong>Score: ' + escapeHtml(row.score) + "</strong>",
        '<em>Potentiel: ' + escapeHtml(euroPerMonth(row.potential)) + "</em>",
        "</span>",
      ].join("");
      button.addEventListener("click", function () {
        focusCity(row.focusSlug);
      });
      radarEl.appendChild(button);
    });
  }

  function renderDepartmentScores() {
    if (!deptScoresEl) {
      return;
    }
    DEPARTMENT_SCORES.forEach(function (dept) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "audience-opportunity-card " + scoreClass(dept.score);
      button.innerHTML = [
        '<span class="audience-opportunity-card__label">' + escapeHtml(dept.number + " " + dept.name) + "</span>",
        '<strong class="audience-opportunity-card__score">' + escapeHtml(dept.score) + "</strong>",
      ].join("");
      button.addEventListener("click", function () {
        focusCity(dept.focusSlug);
      });
      deptScoresEl.appendChild(button);
    });
  }

  function renderLiveSignals() {
    if (!liveSignalsEl) {
      return;
    }
    LIVE_SIGNALS.forEach(function (signal) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "audience-signal-item";
      button.innerHTML =
        '<span class="audience-signal-item__dot" aria-hidden="true"></span>' +
        '<span class="audience-signal-item__content"><strong>' + escapeHtml(signal.territory) + "</strong><span>" + escapeHtml(signal.detail) + '</span><em>' + escapeHtml(signal.when) + "</em></span>";
      button.addEventListener("click", function () {
        focusCity(signal.focusSlug);
      });
      liveSignalsEl.appendChild(button);
    });
  }

  function renderRecommendations() {
    if (!recommendationsEl) {
      return;
    }
    recommendationLogic().forEach(function (item, index) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "audience-action-item";
      button.innerHTML =
        '<span class="audience-action-item__index">' + (index + 1) + "</span>" +
        '<span class="audience-action-item__content"><strong>' + escapeHtml(item.title) + "</strong><span>" + escapeHtml(item.reason) + "</span></span>";
      button.addEventListener("click", function () {
        focusCity(item.focusSlug);
      });
      recommendationsEl.appendChild(button);
    });
  }

  function renderFounderSalesQueue() {
    if (!founderQueueEl) {
      return;
    }
    buildFounderQueue().forEach(function (item) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "audience-founder-row";
      button.innerHTML = [
        '<span class="audience-founder-row__main">',
        '<strong>' + escapeHtml(item.territory) + "</strong>",
        '<span class="audience-founder-row__reason">' + escapeHtml(item.reason) + "</span>",
        '<span class="audience-founder-row__action">' + escapeHtml(item.action) + "</span>",
        "</span>",
        '<span class="audience-founder-row__badge ' + escapeHtml(item.badgeClass) + '">' + escapeHtml(item.badge) + "</span>",
      ].join("");
      button.addEventListener("click", function () {
        focusCity(item.focusSlug);
      });
      founderQueueEl.appendChild(button);
    });
  }

  function renderEstimatedOpportunity() {
    if (!estimatedOpportunityEl) {
      return;
    }
    estimatedOpportunityEl.textContent = formatEuro(estimatedOpportunityThisWeek());
  }

  function renderForecast() {
    if (!forecastEl) {
      return;
    }
    var hotCount = DEPARTMENT_SCORES.filter(function (dept) { return dept.score >= 70; }).length;
    var expectedDemos = hotCount;
    var likelyPilots = hotCount >= 2 ? 1 : 0;
    var maxMrr = hotCount * 590;
    forecastEl.innerHTML = [
      '<div class="audience-forecast-card__grid">',
      '<span><strong>' + expectedDemos + '</strong><em>Expected demos <span class="audience-inline-tag">RAW DATA</span></em></span>',
      '<span><strong>' + likelyPilots + '</strong><em>Likely pilots <span class="audience-inline-tag">ESTIMATED</span></em></span>',
      '<span><strong>' + escapeHtml(formatEuro(590)) + " - " + escapeHtml(formatEuro(maxMrr)) + '</strong><em>Potential MRR <span class="audience-inline-tag">ESTIMATED</span></em></span>',
      '<span><strong>Moyenne</strong><em>Confidence <span class="audience-inline-tag">ESTIMATED</span></em></span>',
      "</div>",
    ].join("");
  }

  function renderShortlist() {
    if (!shortlistEl) {
      return;
    }
    PIPELINE_SHORTLIST.forEach(function (item, index) {
      var row = document.createElement("div");
      row.className = "audience-shortlist-item";
      row.innerHTML = '<span class="audience-shortlist-item__index">' + (index + 1) + '</span><span class="audience-shortlist-item__label">' + escapeHtml(item) + "</span>";
      shortlistEl.appendChild(row);
    });
  }

  LOCATIONS.forEach(function (point) {
    cityRegistry[point.slug] = point;
    var marker = L.marker([point.lat, point.lng], {
      icon: buildMarkerIcon(point),
      title: point.city + " - " + point.needs + " demandes",
      riseOnHover: true,
      keyboard: true,
    });
    marker.bindPopup(buildPopupHtml(point), { closeButton: false, offset: [0, -4] });
    marker.on("mouseover", function () { setMarkerState(marker, "is-hover", true); });
    marker.on("mouseout", function () { setMarkerState(marker, "is-hover", false); });
    marker.on("click", function () { focusCity(point.slug); });
    marker.on("popupopen", function () {
      updateSidebar(point);
      setActiveMarker(point.slug);
    });
    marker.addTo(markerLayer);
    markerRegistry[point.slug] = marker;
  });

  if (cityListEl) {
    LOCATIONS.slice()
      .sort(function (a, b) { return b.needs - a.needs; })
      .slice(0, 5)
      .forEach(function (point, index) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "audience-city-item";
        button.setAttribute("data-city-slug", point.slug);
        button.setAttribute("title", point.city + " - " + point.needs + " demandes");
        button.innerHTML =
          '<span class="audience-city-item__rank">' + (index + 1) + '.</span>' +
          '<span class="audience-city-item__label">' + escapeHtml(point.city) + '</span>' +
          '<span class="audience-city-item__meta">' + escapeHtml(point.needs) + ' demandes</span>' +
          '<span class="audience-city-item__arrow" aria-hidden="true">›</span>';
        button.addEventListener("click", function () {
          focusCity(point.slug);
        });
        cityListEl.appendChild(button);
      });
  }

  runSafeRender("Estimated Opportunity", renderEstimatedOpportunity);
  runSafeRender("Revenue Radar", renderRevenueRadar);
  runSafeRender("Department Scores", renderDepartmentScores);
  runSafeRender("Live Signals", renderLiveSignals);
  runSafeRender("Recommendations", renderRecommendations);
  runSafeRender("Founder Sales Queue", renderFounderSalesQueue);
  runSafeRender("Forecast", renderForecast);
  runSafeRender("Shortlist", renderShortlist);

  var markerGroup = L.featureGroup(
    LOCATIONS.map(function (point) { return markerRegistry[point.slug]; })
  );
  map.fitBounds(markerGroup.getBounds().pad(0.16));
  if (map.getZoom() > defaultZoom) {
    map.setZoom(defaultZoom);
  }

  heatLayer.eachLayer(function (layer) { layer.bringToBack(); });
  expansionRing.bringToBack();
  coreRing.bringToBack();
  window.setTimeout(function () {
    map.invalidateSize();
    focusCity("paris");
  }, 0);
})();
