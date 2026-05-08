// compactPath-test.js
(function() {
  "use strict";

  function esc(value) {
    return String(value || "").replace(/[&<>"']/g, function(c) {
      return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c];
    });
  }

  function labelPath(path) {
    var map = {
      "/": "Accueil",
      "/comment_ca_marche": "Fonctionnement",
      "/offre": "Offre",
      "/deploiement": "Déploiement",
      "/demo": "Accès pilote",
      "/professionnels": "Professionnels",
      "/collectivites": "Collectivites",
      "/securite": "Securite",
      "/contact": "Contact",
      "/requests": "Demandes",
      "/requests/dashboard": "Pilotage",
      "/requests/operations": "Operations"
    };
    return map[path] || path;
  }

  function compactPath(paths) {
    var important = {
      "/comment_ca_marche": true,
      "/offre": true,
      "/deploiement": true,
      "/demo": true,
      "/professionnels": true,
      "/collectivites": true,
      "/securite": true,
      "/contact": true,
      "/cas_usage": true,
      "/requests": true,
      "/requests/dashboard": true,
      "/requests/operations": true
    };

    var raw = paths || [];
    var cleaned = [];
    var seen = {};

    raw.forEach(function(p) {
      if (!important[p]) return;
      if (!seen[p]) {
        cleaned.push(p);
        seen[p] = true;
      }
    });

    if (!cleaned.length) {
      cleaned = raw.filter(p => p && p !== "/").slice(-4);
    }

    // връща визуални chips
    return cleaned.map(function(p) {
      return '<span class="hc-live-path-chip">' + esc(labelPath(p)) + '</span>';
    }).join("");
  }

  // правим функцията достъпна глобално
  window.compactPath = compactPath;
  console.log("compactPath е готова за тестове!");
})();
