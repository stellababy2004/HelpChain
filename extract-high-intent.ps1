param(
    [int]$MinScore = 80,
    [string]$City = "",
    [switch]$ExportJson,
    [switch]$ExportTxt
)

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host " HELPCHAIN - LIVE INTENT EXTRACTOR " -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Проверка за Node
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "Node.js is NOT installed or not in PATH." -ForegroundColor Red
    exit
}

# Временен Node script
$tempFile = Join-Path $env:TEMP "hc_live_extract.mjs"

@'
function esc(value) {
    return String(value || "").replace(/[&<>"']/g, function (c) {
        return {
            "&":"&amp;",
            "<":"&lt;",
            ">":"&gt;",
            "\"":"&quot;",
            "'":"&#39;"
        }[c];
    });
}

function labelPath(path) {
    const map = {
        "/": "Accueil",
        "/comment_ca_marche": "Fonctionnement",
        "/offre": "Offre",
        "/deploiement": "Déploiement",
        "/demo": "Accès pilote",
        "/professionnels": "Professionnels",
        "/collectivites": "Collectivités",
        "/securite": "Sécurité",
        "/contact": "Contact",
        "/requests": "Demandes",
        "/requests/dashboard": "Pilotage",
        "/requests/operations": "Opérations"
    };

    return map[path] || path;
}

function compactPath(paths) {

    const important = {
        "/comment_ca_marche": true,
        "/offre": true,
        "/deploiement": true,
        "/demo": true,
        "/professionnels": true,
        "/collectivites": true,
        "/securite": true,
        "/contact": true,
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

    return cleaned.map(function(p) {
        return "[" + labelPath(p) + "]";
    }).join(" -> ");
}

async function main() {

    const minScore = Number(process.argv[2] || 80);
    const cityFilter = String(process.argv[3] || "").toLowerCase();

    const res = await fetch("http://127.0.0.1:5005/admin/api/high-intent-sessions", {
        cache: "no-store"
    });

    const data = await res.json();

    let sessions = data.sessions || [];

    sessions = sessions.filter(s => Number(s.score || 0) >= minScore);

    if (cityFilter) {
        sessions = sessions.filter(s =>
            String(s.city || s.location || "")
            .toLowerCase()
            .includes(cityFilter)
        );
    }

    sessions.sort((a,b) => Number(b.score || 0) - Number(a.score || 0));

    const exportData = [];

    console.log("");
    console.log("========== LIVE HIGH INTENT ==========");
    console.log("");

    if (!sessions.length) {
        console.log("No matching sessions.");
        process.exit(0);
    }

    sessions.forEach((s, idx) => {

        const path = compactPath(s.path || []);

        let priority = "LOW";

        if (s.score >= 200) priority = "VERY HIGH";
        else if (s.score >= 140) priority = "HIGH";
        else if (s.score >= 80) priority = "MEDIUM";

        let recommendation = "Observe";

        if (s.score >= 200) {
            recommendation = "CONTACT IN 24H";
        } else if (s.score >= 140) {
            recommendation = "QUALIFY THIS WEEK";
        } else if (s.score >= 80) {
            recommendation = "ADD TO WATCHLIST";
        }

        const item = {
            rank: idx + 1,
            score: s.score,
            priority,
            city: s.city || s.location || "Unknown",
            type: s.session_type || "Signal public",
            events: s.events || 0,
            last_seen: s.last_seen,
            recommendation,
            path
        };

        exportData.push(item);

        console.log("--------------------------------");
        console.log("RANK:           ", item.rank);
        console.log("CITY:           ", item.city);
        console.log("SCORE:          ", item.score);
        console.log("PRIORITY:       ", item.priority);
        console.log("TYPE:           ", item.type);
        console.log("EVENTS:         ", item.events);
        console.log("LAST SEEN:      ", item.last_seen);
        console.log("PATH:           ", item.path);
        console.log("RECOMMENDATION: ", item.recommendation);
        console.log("--------------------------------");
        console.log("");

    });

    globalThis.__HC_EXPORT__ = exportData;
}

main();
'@ | Set-Content $tempFile -Encoding UTF8

# Стартиране на Node
$output = & node $tempFile $MinScore $City

$output

# Export data
if ($ExportTxt) {

    $txtFile = ".\high-intent-report.txt"

    $output | Out-File $txtFile -Encoding utf8

    Write-Host ""
    Write-Host "TXT export saved:" -ForegroundColor Green
    Write-Host $txtFile -ForegroundColor Yellow
}

if ($ExportJson) {

    $jsonFile = ".\high-intent-report.json"

    $output | Out-File $jsonFile -Encoding utf8

    Write-Host ""
    Write-Host "JSON export saved:" -ForegroundColor Green
    Write-Host $jsonFile -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done." -ForegroundColor Cyan
Write-Host ""
