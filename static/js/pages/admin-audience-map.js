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
  var QUALIFIED_PAGE_WEIGHTS = {
    "/demo": 40,
    "/contact": 35,
    "/offre": 30,
    "/deploiement": 20,
    "/securite": 15,
  };

  function parseAudiencePayload() {
    var el = document.getElementById("audienceMapPayload");
    if (!el) {
      return {};
    }
    try {
      return JSON.parse(el.textContent || "{}");
    } catch (error) {
      console.error("[AudienceMap] audience payload parse failed:", error);
      return {};
    }
  }

  var audiencePayload = parseAudiencePayload();
  var FOUNDER_QUEUE_ACCOUNT_ROWS = Array.isArray(audiencePayload.founder_queue_account_rows)
    ? audiencePayload.founder_queue_account_rows
    : [];
  var FOUNDER_QUEUE_LEAD_ROWS = Array.isArray(audiencePayload.founder_queue_lead_rows)
    ? audiencePayload.founder_queue_lead_rows
    : [];
  var QUALIFIED_SIGNAL_ROWS = Array.isArray(audiencePayload.qualified_signal_rows)
    ? audiencePayload.qualified_signal_rows
    : [];
  var BACKEND_MAP_LOCATIONS = Array.isArray(audiencePayload.map_locations)
    ? audiencePayload.map_locations
    : [];

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

  function normalizeText(value) {
    return String(value || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
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

  function findFocusSlug(territory, department) {
    var normalizedTerritory = normalizeText(territory);
    var normalizedDepartment = String(department || "").trim();
    var backendMatch = BACKEND_MAP_LOCATIONS.find(function (point) {
      return normalizeText(point.label) === normalizedTerritory ||
        (normalizedDepartment && String(point.department_code || "").trim() === normalizedDepartment);
    });
    if (backendMatch && backendMatch.slug) {
      return backendMatch.slug;
    }
    var locationMatch = LOCATIONS.find(function (point) {
      return normalizeText(point.city) === normalizedTerritory ||
        (normalizedDepartment && String(point.departmentNumber || "").trim() === normalizedDepartment);
    });
    return locationMatch ? locationMatch.slug : "paris";
  }

  function clampScore(value) {
    return Math.max(0, Math.min(100, Number(value) || 0));
  }

  function scorePriority(score) {
    if (score >= 90) {
      return "Tres chaud";
    }
    if (score >= 75) {
      return "Chaud";
    }
    if (score >= 55) {
      return "A qualifier";
    }
    return "Observation";
  }

  function scoreBadgeClass(score) {
    if (score >= 75) {
      return "is-high";
    }
    if (score >= 55) {
      return "is-warm";
    }
    return "is-watch";
  }

  function suggestedActionForScore(score) {
    if (score >= 90) {
      return "Appeler / contacter aujourd'hui";
    }
    if (score >= 75) {
      return "Envoyer un email cible aujourd'hui";
    }
    if (score >= 55) {
      return "Qualifier les interlocuteurs";
    }
    return "Garder en observation";
  }

  function opportunityValueFromScore(score) {
    if (score >= 90) {
      return 590;
    }
    if (score >= 75) {
      return 390;
    }
    if (score >= 55) {
      return 190;
    }
    return 0;
  }

  function founderLeadBadgeClass(priority) {
    if (priority === "Tres chaud" || priority === "Chaud") {
      return "is-high";
    }
    if (priority === "A qualifier") {
      return "is-warm";
    }
    return "is-watch";
  }

  function maskEmail(email) {
    var value = String(email || "").trim();
    var parts = value.split("@");
    if (parts.length !== 2) {
      return value;
    }
    var local = parts[0];
    var domain = parts[1];
    if (local.length <= 2) {
      return local.charAt(0) + "***@" + domain;
    }
    return local.slice(0, 2) + "***@" + domain;
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

  function buildQualifiedQueue() {
    var grouped = {};
    QUALIFIED_SIGNAL_ROWS.forEach(function (row) {
      var territory = String(row.territory || "").trim();
      var department = String(row.department || "").trim();
      var page = String(row.page || "").trim();
      if (!territory || !page) {
        return;
      }
      var key = territory + "||" + department;
      if (!grouped[key]) {
        grouped[key] = {
          territory: territory,
          department: department,
          pages: {},
          totalCount: 0,
          repeatSignals: 0,
          uniquePagesSeen: 0,
          lastSeen: "recent",
          focusSlug: String(row.focus_slug || "").trim() || findFocusSlug(territory, department),
        };
      }
      grouped[key].pages[page] = (grouped[key].pages[page] || 0) + (Number(row.count) || 0);
      grouped[key].totalCount += Number(row.count) || 0;
      grouped[key].repeatSignals += Number(row.repeat_sessions) || 0;
      grouped[key].uniquePagesSeen = Math.max(grouped[key].uniquePagesSeen, Number(row.unique_pages_seen) || 0);
      if (row.last_seen) {
        grouped[key].lastSeen = row.last_seen;
      }
    });

    return Object.keys(grouped)
      .map(function (key) {
        var item = grouped[key];
        var pages = Object.keys(item.pages);
        var score = 0;
        pages.forEach(function (page) {
          score += Number(QUALIFIED_PAGE_WEIGHTS[page] || 0);
        });
        if (item.repeatSignals > 0 || item.totalCount >= 2) {
          score += 10;
        }
        if (Math.max(item.uniquePagesSeen, pages.length) >= 3) {
          score += 8;
        }
        if (["75", "92", "93"].indexOf(item.department) !== -1) {
          score += 5;
        }
        score = clampScore(score);
        var territoryLabel = item.territory + (item.department ? " (" + item.department + ")" : "");
        var detectedSignal = pages.slice(0, 3).join(" + ");
        if (detectedSignal) {
          detectedSignal += " vues " + item.lastSeen;
        } else {
          detectedSignal = "Pas encore assez de signaux qualifies.";
        }
        return {
          territory: territoryLabel,
          detectedSignal: detectedSignal,
          score: score,
          scoreLabel: "Score " + score,
          priority: scorePriority(score),
          badgeClass: scoreBadgeClass(score),
          sourceLabel: "Signal qualifie",
          action: suggestedActionForScore(score),
          focusSlug: item.focusSlug || "paris",
          estimatedValue: opportunityValueFromScore(score),
        };
      })
      .sort(function (a, b) {
        return b.score - a.score;
      });
  }

  function buildQualifiedLeadQueue() {
    return FOUNDER_QUEUE_LEAD_ROWS.slice()
      .sort(function (a, b) {
        var scoreDiff = (Number(b.score) || 0) - (Number(a.score) || 0);
        if (scoreDiff !== 0) {
          return scoreDiff;
        }
        return String(a.organization || a.email || "").localeCompare(String(b.organization || b.email || ""));
      })
      .map(function (row) {
        var pagesViewed = Array.isArray(row.pages_viewed) ? row.pages_viewed : [];
        var territoryLabel = String(row.organization || row.email || "Lead qualifie");
        if (row.email && row.organization && row.organization !== row.email) {
          territoryLabel += " - " + row.email;
        }
        return {
          kind: "lead",
          organization: String(row.organization || "").trim(),
          organizationName: String(row.organization_name || "").trim(),
          organizationDomain: String(row.organization_domain || "").trim(),
          organizationType: String(row.organization_type || "").trim(),
          territoryHint: String(row.territory_hint || "").trim(),
          organizationConfidence: String(row.organization_confidence || "").trim(),
          salesNote: String(row.sales_note || "").trim(),
          email: String(row.email || "").trim(),
          emailMasked: maskEmail(row.email),
          pagesViewed: pagesViewed,
          territory: territoryLabel,
          detectedSignal: (pagesViewed.length ? pagesViewed.join(" + ") : "Pages non renseignees") + " - " + (row.territory || "France"),
          score: Number(row.score) || 0,
          scoreLabel: "Score " + (Number(row.score) || 0),
          priority: String(row.priority || "Observation"),
          badgeClass: founderLeadBadgeClass(String(row.priority || "")),
          sourceLabel: "Signal qualifie",
          action: suggestedActionForScore(Number(row.score) || 0),
          focusSlug: String(row.focus_slug || "").trim() || findFocusSlug(row.territory, row.department),
          estimatedValue: opportunityValueFromScore(Number(row.score) || 0),
        };
      });
  }

  function buildAccountQueue() {
    return FOUNDER_QUEUE_ACCOUNT_ROWS.slice()
      .sort(function (a, b) {
        var scoreDiff = (Number(b.best_score) || 0) - (Number(a.best_score) || 0);
        if (scoreDiff !== 0) {
          return scoreDiff;
        }
        return String(b.last_activity || "").localeCompare(String(a.last_activity || ""));
      })
      .map(function (row) {
        var pagesViewed = Array.isArray(row.pages_viewed) ? row.pages_viewed : [];
        var emails = Array.isArray(row.emails) ? row.emails : [];
        var bestScore = Number(row.best_score) || 0;
        var avgScore = Number(row.avg_score) || 0;
        var confidence = String(row.confidence || "low").trim() || "low";
        return {
          kind: "account",
          accountName: String(row.account_name || "").trim(),
          domain: String(row.domain || "").trim(),
          organizationType: String(row.organization_type || "").trim(),
          territoryHint: String(row.territory_hint || "").trim(),
          confidence: confidence,
          leadCount: Number(row.lead_count) || 0,
          emails: emails,
          pagesViewed: pagesViewed,
          bestScore: bestScore,
          avgScore: avgScore,
          score: bestScore,
          scoreLabel: "Score " + bestScore,
          priority: String(row.priority || scorePriority(bestScore)),
          badgeClass: founderLeadBadgeClass(String(row.priority || scorePriority(bestScore))),
          sourceLabel: String(row.source_label || "Signal qualifie"),
          action: String(row.recommended_action || suggestedActionForScore(bestScore)),
          lastActivity: String(row.last_activity || "recent"),
          focusSlug: String(row.focus_slug || "").trim() || findFocusSlug(row.territory_hint, ""),
          salesNote: String(row.sales_note || "").trim(),
          estimatedValue: opportunityValueFromScore(bestScore),
        };
      });
  }

  function buildEstimatedQueue() {
    return buildFounderQueue().map(function (item) {
      var fallbackScore = 0;
      if (item.badge === "Haute priorite") {
        fallbackScore = 82;
      } else if (item.badge === "Chaud") {
        fallbackScore = 68;
      } else {
        fallbackScore = 42;
      }
      return {
        kind: "estimated",
        territory: item.territory,
        detectedSignal: item.reason,
        score: fallbackScore,
        scoreLabel: "Score " + fallbackScore,
        priority: item.badge,
        badgeClass: item.badgeClass,
        sourceLabel: "Estimation interne",
        action: item.action,
        focusSlug: item.focusSlug,
        estimatedValue: 0,
      };
    });
  }

  function founderQueueRows() {
    var accountQueue = buildAccountQueue();
    if (accountQueue.length) {
      return {
        mode: "qualified",
        source: "account",
        rows: accountQueue,
      };
    }
    var leadQueue = buildQualifiedLeadQueue();
    if (leadQueue.length) {
      return {
        mode: "qualified",
        source: "lead",
        rows: leadQueue,
      };
    }
    var qualifiedQueue = buildQualifiedQueue();
    if (qualifiedQueue.length) {
      return {
        mode: "qualified",
        source: "qualified",
        rows: qualifiedQueue,
      };
    }
    return {
      mode: "estimated",
      source: "estimated",
      rows: buildEstimatedQueue(),
    };
  }

  function estimatedOpportunityMode() {
    var queue = founderQueueRows();
    if (queue.mode === "qualified") {
      return {
        title: "Opportunite qualifiee cette semaine",
        modeLabel: "Signal qualifie",
        label: "Signal qualifie + valeur estimee",
        context: "Projection interne basee sur signaux qualifies, non facturee.",
        value: queue.rows.reduce(function (sum, row) {
          return sum + (Number(row.estimatedValue) || 0);
        }, 0),
      };
    }
    return {
      title: "Opportunite estimee cette semaine",
      modeLabel: "Estimation interne",
      label: "Valeur estimee",
      context: "Projection interne, non facturee.",
      value: estimatedOpportunityThisWeek(),
    };
  }

  function renderFounderQueueEmptyState() {
    if (!founderQueueEl) {
      return;
    }
    founderQueueEl.innerHTML = [
      '<div class="hc-empty-state">',
      '<div class="hc-empty-state__title">Pas encore assez de signaux comptes.</div>',
      '<div class="hc-empty-state__text">Les recommandations s\'affineront avec les prochains leads qualifies.</div>',
      "</div>",
    ].join("");
  }

  function runSafeRender(label, renderFn, onError) {
    try {
      renderFn();
    } catch (error) {
      console.error("[AudienceMap] " + label + " failed:", error);
      if (typeof onError === "function") {
        onError();
      }
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
  var opportunityTitleEl = document.getElementById("audienceOpportunityTitle");
  var opportunityLabelEl = document.getElementById("audienceOpportunityLabel");
  var opportunityContextEl = document.getElementById("audienceOpportunityContext");
  var founderQueueModeEl = document.getElementById("audienceFounderQueueMode");

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
    radarEl.innerHTML = "";
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
        '<span class="audience-inline-tag">Estimation interne</span>',
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
    deptScoresEl.innerHTML = "";
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
    liveSignalsEl.innerHTML = "";
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
    recommendationsEl.innerHTML = "";
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
    var queue = founderQueueRows();
    founderQueueEl.innerHTML = "";
    if (founderQueueModeEl) {
      founderQueueModeEl.textContent = queue.mode === "qualified" ? "Signal qualifie" : "Estimation interne";
    }
    if (!queue.rows.length) {
      renderFounderQueueEmptyState();
      return;
    }
    queue.rows.forEach(function (item) {
      if (queue.source === "account" && item.kind === "account") {
        var accountCard = document.createElement("div");
        accountCard.className = "audience-founder-row";
        accountCard.setAttribute("role", "group");
        var accountLines = [];
        accountLines.push('<span class="audience-founder-row__reason">Compte detecte</span>');
        if (item.domain) {
          accountLines.push('<span class="audience-founder-row__reason">Domaine: ' + escapeHtml(item.domain) + "</span>");
        }
        if (item.organizationType) {
          accountLines.push('<span class="audience-founder-row__reason">Type probable: ' + escapeHtml(item.organizationType) + "</span>");
        }
        if (item.territoryHint) {
          accountLines.push('<span class="audience-founder-row__reason">Territoire: ' + escapeHtml(item.territoryHint) + "</span>");
        }
        accountLines.push('<span class="audience-founder-row__reason">Contacts detectes: ' + escapeHtml(item.leadCount) + "</span>");
        if (item.emails.length) {
          accountLines.push('<span class="audience-founder-row__reason">Emails: ' + escapeHtml(item.emails.join(", ")) + "</span>");
        }
        accountLines.push('<span class="audience-founder-row__reason">Pages vues: ' + escapeHtml(item.pagesViewed.join(", ") || "Pages non renseignees") + "</span>");
        accountLines.push('<span class="audience-founder-row__reason">Derniere activite: ' + escapeHtml(item.lastActivity) + "</span>");
        accountLines.push('<span class="audience-founder-row__reason"><span class="audience-inline-tag">ACCOUNT</span> <span class="audience-inline-tag">' + escapeHtml(item.sourceLabel) + '</span> <span class="audience-inline-tag">Confiance ' + escapeHtml(item.confidence) + "</span></span>");
        if (item.salesNote) {
          accountLines.push('<span class="audience-founder-row__reason">Note commerciale: ' + escapeHtml(item.salesNote) + "</span>");
        }
        accountCard.innerHTML = [
          '<span class="audience-founder-row__main">',
          '<strong>' + escapeHtml(item.accountName || item.domain || "Compte probable") + "</strong>",
          '<span class="audience-founder-row__reason">Organisation probable: ' + escapeHtml(item.accountName || item.domain || "-") + "</span>",
          '<span class="audience-founder-row__reason"><span class="audience-inline-tag">' + escapeHtml(item.scoreLabel) + '</span> <span class="audience-inline-tag">Moyenne ' + escapeHtml(item.avgScore) + "</span></span>",
          accountLines.join(""),
          '<span class="audience-founder-row__action">Action suggeree: ' + escapeHtml(item.action) + "</span>",
          '<span class="d-flex flex-wrap gap-2 mt-2">' +
            '<button type="button" class="btn btn-sm btn-outline-primary" data-founder-account-cta="leads">Voir leads</button>' +
            '<button type="button" class="btn btn-sm btn-outline-primary" data-founder-account-cta="email">Preparer email</button>' +
            '<button type="button" class="btn btn-sm btn-primary" data-founder-account-cta="call">Planifier appel</button>' +
          "</span>",
          "</span>",
          '<span class="audience-founder-row__badge ' + escapeHtml(item.badgeClass) + '">' + escapeHtml(item.priority) + "</span>",
        ].join("");
        Array.prototype.forEach.call(accountCard.querySelectorAll("[data-founder-account-cta]"), function (cta) {
          cta.addEventListener("click", function () {
            focusCity(item.focusSlug);
          });
        });
        founderQueueEl.appendChild(accountCard);
        return;
      }
      if (queue.source === "lead" && item.kind === "lead") {
        var card = document.createElement("div");
        card.className = "audience-founder-row";
        card.setAttribute("role", "group");
        var intelligenceLines = [];
        if (item.organizationName) {
          intelligenceLines.push('<span class="audience-founder-row__reason">Organisation détectée: ' + escapeHtml(item.organizationName) + "</span>");
        }
        if (item.organizationType) {
          intelligenceLines.push('<span class="audience-founder-row__reason">Type probable: ' + escapeHtml(item.organizationType) + "</span>");
        }
        if (item.territoryHint) {
          intelligenceLines.push('<span class="audience-founder-row__reason">Territoire: ' + escapeHtml(item.territoryHint) + "</span>");
        }
        if (item.organizationDomain) {
          intelligenceLines.push('<span class="audience-founder-row__reason">Domaine: ' + escapeHtml(item.organizationDomain) + "</span>");
        }
        if (item.organizationConfidence) {
          intelligenceLines.push('<span class="audience-founder-row__reason">Confiance: ' + escapeHtml(item.organizationConfidence) + "</span>");
        }
        if (item.salesNote) {
          intelligenceLines.push('<span class="audience-founder-row__reason">Note commerciale: ' + escapeHtml(item.salesNote) + "</span>");
        }
        card.innerHTML = [
          '<span class="audience-founder-row__main">',
          '<strong>' + escapeHtml(item.organizationName || item.organization || item.emailMasked || item.territory) + "</strong>",
          '<span class="audience-founder-row__reason">' + escapeHtml(item.emailMasked || item.email || "-") + "</span>",
          '<span class="audience-founder-row__reason"><span class="audience-inline-tag">' + escapeHtml(item.scoreLabel) + '</span> <span class="audience-inline-tag">' + escapeHtml(item.sourceLabel) + "</span></span>",
          '<span class="audience-founder-row__reason">Pages vues: ' + escapeHtml((item.pagesViewed || []).join(", ") || "Pages non renseignées") + "</span>",
          intelligenceLines.join(""),
          '<span class="audience-founder-row__action">' + escapeHtml(item.action) + "</span>",
          '<span class="d-flex flex-wrap gap-2 mt-2">' +
            '<button type="button" class="btn btn-sm btn-outline-primary" data-founder-cta="email">Envoyer email</button>' +
            '<button type="button" class="btn btn-sm btn-primary" data-founder-cta="call">Planifier appel</button>' +
          "</span>",
          "</span>",
          '<span class="audience-founder-row__badge ' + escapeHtml(item.badgeClass) + '">' + escapeHtml(item.priority) + "</span>",
        ].join("");
        Array.prototype.forEach.call(card.querySelectorAll("[data-founder-cta]"), function (cta) {
          cta.addEventListener("click", function () {
            focusCity(item.focusSlug);
          });
        });
        founderQueueEl.appendChild(card);
        return;
      }

      var button = document.createElement("button");
      button.type = "button";
      button.className = "audience-founder-row";
      button.innerHTML = [
        '<span class="audience-founder-row__main">',
        '<strong>' + escapeHtml(item.territory) + "</strong>",
        '<span class="audience-founder-row__reason"><span class="audience-inline-tag">' + escapeHtml(item.scoreLabel) + '</span> <span class="audience-inline-tag">' + escapeHtml(item.sourceLabel) + "</span></span>",
        '<span class="audience-founder-row__reason">' + escapeHtml(item.detectedSignal) + "</span>",
        '<span class="audience-founder-row__action">' + escapeHtml(item.action) + "</span>",
        "</span>",
        '<span class="audience-founder-row__badge ' + escapeHtml(item.badgeClass) + '">' + escapeHtml(item.priority) + "</span>",
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
    var mode = estimatedOpportunityMode();
    estimatedOpportunityEl.textContent = formatEuro(mode.value);
    if (opportunityTitleEl) {
      opportunityTitleEl.innerHTML =
        escapeHtml(mode.title) +
        ' <span class="audience-data-tag audience-data-tag--estimated" id="audienceOpportunityMode">' +
        escapeHtml(mode.modeLabel) +
        "</span>";
    }
    if (opportunityLabelEl) {
      opportunityLabelEl.textContent = mode.label;
    }
    if (opportunityContextEl) {
      opportunityContextEl.textContent = mode.context;
    }
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
      '<span><strong>' + expectedDemos + '</strong><em>Demos attendues <span class="audience-inline-tag">Donnee brute</span></em></span>',
      '<span><strong>' + likelyPilots + '</strong><em>Pilotes probables <span class="audience-inline-tag">Estimation interne</span></em></span>',
      '<span><strong>' + escapeHtml(formatEuro(590)) + " - " + escapeHtml(formatEuro(maxMrr)) + '</strong><em>Valeur estimee <span class="audience-inline-tag">Estimation interne</span></em></span>',
      '<span><strong>Moyenne</strong><em>Confiance <span class="audience-inline-tag">Estimation interne</span></em></span>',
      "</div>",
    ].join("");
  }

  function renderShortlist() {
    if (!shortlistEl) {
      return;
    }
    shortlistEl.innerHTML = "";
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
  runSafeRender("FounderSalesQueue", renderFounderSalesQueue, renderFounderQueueEmptyState);
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
