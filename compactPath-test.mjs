// compactPath-test.mjs

// помощни функции
function esc(value) {
  return String(value || "").replace(/[&<>"']/g, c =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c])
  );
}

function labelPath(path) {
  const map = {
    "/": "Accueil",
    "/offre": "Offre",
    "/demo": "Accès pilote",
    "/requests": "Demandes",
    "/requests/dashboard": "Pilotage",
    "/requests/operations": "Operations",
    "/comment_ca_marche": "Fonctionnement",
    "/professionnels": "Professionnels",
    "/collectivites": "Collectivites",
    "/securite": "Securite",
    "/contact": "Contact",
    "/cas_usage": "Cas d'usage"
  };
  return map[path] || path;
}

// функцията compactPath
function compactPath(paths) {
  const important = {
    "/offre": true,
    "/demo": true,
    "/requests": true,
    "/requests/dashboard": true,
    "/requests/operations": true
  };

  const raw = paths || [];
  const cleaned = [];
  const seen = {};

  raw.forEach(function(p) {
    if (!important[p]) return;
    if (!seen[p]) {
      cleaned.push(p);
      seen[p] = true;
    }
  });

  if (!cleaned.length) cleaned.push(...raw.filter(p => p && p !== "/").slice(-4));

  return cleaned.map(p => '<span class="hc-live-path-chip">' + esc(labelPath(p)) + '</span>').join('');
}

// тест на функцията
const testPaths = ["/offre", "/demo", "/requests", "/requests/operations"];
console.log(compactPath(testPaths));
