[CmdletBinding()]
param(
    [switch]$RunMigration,
    [switch]$VerifyOnly
)

$ErrorActionPreference = "Stop"

$pgBin = "C:\Program Files\PostgreSQL\18\bin"
$psql = Join-Path $pgBin "psql.exe"
$python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
$expectedHost = "127.0.0.1"
$expectedPort = "5432"
$expectedDatabase = "helpchain_migration_test"
$expectedUser = "hc_migration_test"
$migrationRevision = "20261030_0001"
$expectedMembershipTablePresent = 1

if (-not (Test-Path -LiteralPath $psql)) {
    throw "psql.exe not found at the expected local PostgreSQL path."
}
if (-not (Test-Path -LiteralPath $python)) {
    throw "Local Python environment not found at the expected path."
}

$existingDatabaseUrl = $env:DATABASE_URL
$existingAlchemyUrl = $env:SQLALCHEMY_DATABASE_URI
$existingAllowBootstrap = $env:ALEMBIC_ALLOW_METADATA_CREATE_ALL
$existingMigrationMode = $env:HC_MIGRATION_MODE

try {
    if ($existingDatabaseUrl -or $existingAlchemyUrl) {
        throw "Refusing to run while DATABASE_URL or SQLALCHEMY_DATABASE_URI is already set."
    }

    $securePassword = Read-Host "Password for $expectedUser on $expectedHost`:$expectedPort" -AsSecureString
    # Convert only in memory. NetworkCredential avoids manual BSTR handling
    # and preserves the exact characters entered at the secure prompt.
    $plainPassword = (New-Object System.Net.NetworkCredential('', $securePassword)).Password

    $env:PGHOST = $expectedHost
    $env:PGPORT = $expectedPort
    $env:PGDATABASE = $expectedDatabase
    $env:PGUSER = $expectedUser
    $env:PGPASSWORD = $plainPassword
    $env:ALEMBIC_ALLOW_METADATA_CREATE_ALL = "0"
    # Flask must be importable for `flask db`, but application startup checks
    # must not query application tables before Alembic creates them.
    $env:HC_MIGRATION_MODE = "1"

    $psqlCommonArgs = @(
        "--no-psqlrc", "--tuples-only", "--no-align", "--quiet",
        "--host", $expectedHost, "--port", $expectedPort,
        "--username", $expectedUser, "--dbname", $expectedDatabase
    )

    $identity = & $psql @psqlCommonArgs `
        --command "SELECT current_user || '|' || current_database() || '|' || COALESCE(host(inet_server_addr()), '') || '|' || inet_server_port()::text;"
    if ($LASTEXITCODE -ne 0) {
        throw "Local PostgreSQL authentication or connection failed."
    }

    # Native command output is an array of lines in PowerShell.  Do not select
    # the last line blindly: warnings/blank lines would make the check depend
    # on psql's output shape.  Accept exactly one non-empty result line.
    $identityLines = @(
        $identity |
            ForEach-Object { ([string]$_).Trim() } |
            Where-Object { $_.Length -gt 0 }
    )
    if ($identityLines.Count -ne 1) {
        throw "Connection identity query returned an unexpected result."
    }
    $identity = $identityLines[0]
    $expectedIdentity = "$expectedUser|$expectedDatabase|$expectedHost|$expectedPort"
    if ($identity -ne $expectedIdentity) {
        throw "Connection identity mismatch; refusing to continue."
    }

    # Only create the application URL after psql has authenticated against the
    # verified local target. The URL is never printed.
    $encodedPassword = [Uri]::EscapeDataString($plainPassword)
    $env:DATABASE_URL = "postgresql+psycopg://$expectedUser`:$encodedPassword@$expectedHost`:$expectedPort/$expectedDatabase"

    if (-not $VerifyOnly) {
        $remoteCount = & $psql @psqlCommonArgs `
        --command "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema');"
        $remoteCountLines = @($remoteCount | ForEach-Object { ([string]$_).Trim() } | Where-Object { $_ })
        if ($LASTEXITCODE -ne 0 -or $remoteCountLines.Count -ne 1 -or [int]$remoteCountLines[0] -ne 0) {
            throw "Target database is not empty or could not be inspected."
        }
    }

    $head = & $python -m flask --app run:app db heads --directory migrations
    if ($LASTEXITCODE -ne 0 -or ($head -notmatch [regex]::Escape($migrationRevision))) {
        throw "Expected Alembic head $migrationRevision was not found."
    }

    if (-not $RunMigration -or $VerifyOnly) {
        if ($VerifyOnly) {
            Write-Output "VERIFY: identity verified, existing target will be checked; metadata bootstrap disabled."
        }
        else {
            Write-Output "READY: identity verified, target is empty, metadata bootstrap disabled."
            Write-Output "No migration was executed. Re-run with -RunMigration only after manual approval."
            return
        }
    }

    if ($RunMigration -and -not $VerifyOnly) {
        & $python -m flask --app run:app db upgrade --directory migrations
        if ($LASTEXITCODE -ne 0) {
            throw "Alembic migration failed."
        }
    }

    $columnRows = & $psql @psqlCommonArgs --command "SELECT column_name || '|' || data_type || '|' || is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name='volunteer_structure_memberships' ORDER BY ordinal_position;"
    if ($LASTEXITCODE -ne 0) { throw "PostgreSQL column verification query failed." }
    $columnLines = @($columnRows | ForEach-Object { ([string]$_).Trim() } | Where-Object { $_.Length -gt 0 })
    $expectedColumns = [ordered]@{ id='integer|NO'; volunteer_id='integer|NO'; structure_id='integer|NO'; status='character varying|NO'; requested_by_user_id='integer|YES'; approved_by_admin_id='integer|YES'; approved_at='timestamp without time zone|YES'; suspended_by_admin_id='integer|YES'; suspended_at='timestamp without time zone|YES'; revoked_by_admin_id='integer|YES'; revoked_at='timestamp without time zone|YES'; decision_reason='text|YES'; created_at='timestamp without time zone|NO'; updated_at='timestamp without time zone|NO' }
    $actualColumns = @{}
    foreach ($line in $columnLines) { $parts = $line -split '\|', 3; if ($parts.Count -eq 3) { $actualColumns[$parts[0]] = "$($parts[1])|$($parts[2])" } }
    foreach ($name in $expectedColumns.Keys) {
        if (-not $actualColumns.ContainsKey($name)) { throw "Schema verification failed: missing column '$name'." }
        if ($actualColumns[$name] -cne $expectedColumns[$name]) { throw "Schema verification failed: column '$name' actual='$($actualColumns[$name])', expected='$($expectedColumns[$name])'." }
    }
    $schema = & $psql @psqlCommonArgs --command "SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname='volunteer_structure_memberships' AND c.relkind IN ('r','p'); SELECT count(*) FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='public' AND t.relname='volunteer_structure_memberships' AND c.conname IN ('uq_volunteer_structure_membership','ck_volunteer_structure_membership_status'); SELECT count(*) FROM pg_indexes WHERE schemaname='public' AND tablename='volunteer_structure_memberships' AND indexname IN ('ix_volunteer_structure_membership_volunteer','ix_volunteer_structure_membership_structure','ix_volunteer_structure_membership_status','ix_volunteer_structure_membership_structure_status','ix_volunteer_structure_membership_volunteer_status'); SELECT count(*) FROM public.volunteer_structure_memberships WHERE status='approved'; SELECT version_num FROM public.alembic_version;"
    if ($LASTEXITCODE -ne 0) { throw "PostgreSQL structural verification query failed." }
    $rawSchemaLines = @($schema)
    $schemaLines = @($rawSchemaLines | ForEach-Object { ([string]$_).Trim() } | Where-Object { $_.Length -gt 0 })
    Write-Output ("Schema diagnostic: raw_count={0}, normalized_count={1}" -f $rawSchemaLines.Count, $schemaLines.Count)
    for ($i = 0; $i -lt $rawSchemaLines.Count; $i++) {
        $raw = [string]$rawSchemaLines[$i]
        Write-Output ("Schema raw[{0}]: type={1}; value={2}" -f $i, $rawSchemaLines[$i].GetType().FullName, ($raw.Trim()))
    }
    for ($i = 0; $i -lt $schemaLines.Count; $i++) {
        Write-Output ("Schema normalized[{0}]: type={1}; value={2}" -f $i, $schemaLines[$i].GetType().FullName, $schemaLines[$i])
    }

    if ($schemaLines.Count -lt 5) {
        throw ("Schema verification failed: expected 5 structural rows, got {0}." -f $schemaLines.Count)
    }
    $membershipTablePresent = 0
    if (-not [int]::TryParse([string]$schemaLines[0], [ref]$membershipTablePresent)) {
        throw ("Schema verification failed: public table existence result is not an integer: '{0}'." -f $schemaLines[0])
    }
    if ($membershipTablePresent -ne $expectedMembershipTablePresent) {
        throw ("Schema verification failed: public.volunteer_structure_memberships existence result is {0}, expected {1}." -f $membershipTablePresent, $expectedMembershipTablePresent)
    }
    $constraintCount = 0
    $indexCount = 0
    $approvedCount = 0
    if (-not [int]::TryParse([string]$schemaLines[1], [ref]$constraintCount)) {
        throw ("Schema verification failed: constraint count is not an integer: '{0}'." -f $schemaLines[1])
    }
    if (-not [int]::TryParse([string]$schemaLines[2], [ref]$indexCount)) {
        throw ("Schema verification failed: index count is not an integer: '{0}'." -f $schemaLines[2])
    }
    if (-not [int]::TryParse([string]$schemaLines[3], [ref]$approvedCount)) {
        throw ("Schema verification failed: approved count is not an integer: '{0}'." -f $schemaLines[3])
    }
    if ($constraintCount -ne 2) {
        throw ("Schema verification failed: expected required unique/check constraints=2, got {0}." -f $constraintCount)
    }
    if ($indexCount -ne 5) {
        throw ("Schema verification failed: expected required membership indexes=5, got {0}." -f $indexCount)
    }
    if ($approvedCount -ne 0) {
        throw ("Schema verification failed: expected 0 approved memberships, got {0}." -f $approvedCount)
    }
    if ([string]$schemaLines[4] -cne $migrationRevision) {
        throw ("Schema verification failed: Alembic revision actual='{0}', expected='{1}'." -f $schemaLines[4], $migrationRevision)
    }

    Write-Output "PostgreSQL target schema was verified."
}
finally {
    $env:PGPASSWORD = $null
    $env:PGHOST = $null
    $env:PGPORT = $null
    $env:PGDATABASE = $null
    $env:PGUSER = $null
    $env:DATABASE_URL = $existingDatabaseUrl
    $env:SQLALCHEMY_DATABASE_URI = $existingAlchemyUrl
    $env:ALEMBIC_ALLOW_METADATA_CREATE_ALL = $existingAllowBootstrap
    $env:HC_MIGRATION_MODE = $existingMigrationMode
}
