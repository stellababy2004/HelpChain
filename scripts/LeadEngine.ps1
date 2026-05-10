# ==============================================
# LeadEngine.ps1
# Скрипт за извличане на активни leads и генериране на имейл + копиране в клипборда
# ==============================================

# 1) Активиране на виртуалната среда
& "C:\dev\HelpChain\.venv\Scripts\Activate.ps1"

# 2) Настройки за Neon Postgres
$OutputEncoding = [System.Text.Encoding]::UTF8
$PGHost = "ep-floral-fog-agq8kl5i-pooler.c-2.eu-central-1.aws.neon.tech"
$PGPort = 5432
$PGUser = "neondb_owner"
$PGPass = "npg_g6XPHW8tGQJZ"
$PGDB   = "neondb"

# 3) Функция за изпълнение на SQL query
function Exec-PSQL {
    param([string]$Query)
    $psqlPath = "C:\Program Files\PostgreSQL\18\bin\psql.exe"
    $env:PGPASSWORD = $PGPass
    $args = @(
        "-h", $PGHost
        "-U", $PGUser
        "-d", $PGDB
        "-p", $PGPort
        "-At"
        "-F", ","
        "-c", $Query
    )
    & "$psqlPath" @args
}

# 4) Вземане на активните leads
$testQuery = "SELECT id, city, email, status FROM professional_leads WHERE status != 'closed' LIMIT 5;"
$resultsRaw = Exec-PSQL $testQuery

# 5) Преобразуване към PowerShell обекти
$results = $resultsRaw | ForEach-Object {
    $fields = $_ -split ","
    [PSCustomObject]@{
        LeadId = $fields[0]
        City   = $fields[1]
        Email  = $fields[2]
        Status = $fields[3]
    }
}

# 6) Генериране на бележка + имейл текст за първия lead
$topLead = $results | Sort-Object -Property Status, LeadId -Descending | Select-Object -First 1

$contactNote = @"
📌 Lead за контакт:
City: $($topLead.City)
Email: $($topLead.Email)
Overall Score: TBD
Pilot Probability: TBD
Repeat Visits: TBD
Total Time on Site: TBD

✅ Бележка: Започни пилот с тази организация.

📧 Имейл текст:
Bonjour,

Je me permets de vous contacter au nom de HelpChain. Nous avons identifié votre structure ($($topLead.Email)) comme un candidat idéal pour notre pilote de coordination opérationnelle.

Nous serions ravis de planifier une courte session de démonstration pour vous montrer comment HelpChain peut aider votre équipe à gagner du temps et à optimiser vos processus.

Seriez-vous disponible pour un échange cette semaine ?

Cordialement,
Stella Stoyanova
Founder, HelpChain
---
"@

# 7) Копиране на текста в клипборда
$contactNote | Set-Clipboard

# 8) Извеждане в конзолата
Write-Host "✅ Имейлът за $($topLead.Email) е копиран в клипборда."
