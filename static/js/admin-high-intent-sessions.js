(function () {
  "use strict";

  function esc(value) {
    return String(value || "").replace(/[&<>"']/g, function (c) {
      return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c];
    });
  }

  function compactPath(paths) {
    var raw = paths || [];
    var compact = raw.length > 5 ? raw.slice(0, 2).concat(["..."]).concat(raw.slice(-3)) : raw;
    return compact.map(esc).join(" → ");
  }

  function actionFor(session) {
    if (session.intent === "very_high") return "Planifier un contact sous 48h";
    if (session.intent === "high") return "Qualifier le signal commercial";
    if (session.intent === "medium") return "Suivre les prochaines visites";
    return "Surveiller le parcours";
  }

  function momentumFor(session) {
    if (session.score >= 140) return "Signal fort";
    if (session.score >= 80) return "Signal actif";
    return "Signal en observation";
  }

  async function loadHighIntentSessions() {
    var root = document.getElementById("hc-high-intent-sessions");
    if (!root) return;

    try {
      var res = await fetch("/admin/api/high-intent-sessions", { cache: "no-store" });
      var data = await res.json();
      var sessions = data.sessions || [];

      if (!sessions.length) {
        root.innerHTML = '<div class="hc-empty-state">Aucun signal qualifie pour le moment.</div>';
        return;
      }

      root.innerHTML = sessions.map(function (s) {
        var badge = s.intent === "very_high" ? "Priorite elevee" : s.intent === "high" ? "Priorite active" : "A surveiller";
        var path = compactPath(s.path);
        var action = actionFor(s);
        var momentum = momentumFor(s);

        return '' +
          '<div class="hc-live-intent-row">' +
            '<div class="hc-live-intent-row__head">' +
              '<strong>' + esc(badge) + '</strong>' +
              '<span>Score ' + esc(s.score) + '</span>' +
            '</div>' +
            '<div class="hc-live-intent-row__path">' + path + '</div>' +
            '<div class="hc-live-intent-row__meta">' +
              esc(s.events) + ' evenements · Dernier signal: ' + esc(s.last_seen) +
            '</div>' +
            '<div class="hc-live-intent-row__action">' +
              '<span>' + esc(momentum) + '</span>' +
              '<strong>Action recommandee: ' + esc(action) + '</strong>' +
            '</div>' +
          '</div>';
      }).join("");

    } catch (e) {
      root.innerHTML = '<div class="hc-empty-state">Lecture des signaux indisponible.</div>';
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    loadHighIntentSessions();
    window.setInterval(loadHighIntentSessions, 30000);
  });
})();
