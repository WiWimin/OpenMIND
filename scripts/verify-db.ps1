# Verify the OpenMIND development database stack.
#
# Checks, in order:
#   1. PostgreSQL readiness inside the `db` container
#   2. pgvector extension is installed (and its version)
#   3. the `vector` type is actually usable
#   4. Alembic schema is at head
#   5. backend health endpoint reports backend + database as up
#
# Exits non-zero on the first failure so it can be used in CI.

[CmdletBinding()]
param(
    [string]$HealthUrl = $(if ($env:HEALTH_URL) { $env:HEALTH_URL } else { 'http://localhost:8000/api/v1/health/db' })
)

$ErrorActionPreference = 'Stop'

$rootDir = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $rootDir 'docker/compose.dev.yml'
$envFile = Join-Path $rootDir 'docker/.env'

# Runs `docker compose -f <composeFile> <DockerArgs...>` and captures the result.
# An explicit array + splatting is used so that docker flags such as -U / -d
# are forwarded verbatim instead of being parsed as PowerShell parameters.
function Invoke-ComposeRaw {
    param([Parameter(Mandatory)][string[]]$DockerArgs)

    $all = @('compose', '-f', $composeFile) + $DockerArgs
    # Native commands (alembic in particular) log to stderr. Merging stderr into
    # the output stream with 2>&1 would otherwise surface as terminating errors
    # under $ErrorActionPreference = 'Stop'.
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & docker @all 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    $text = ($output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    return [pscustomobject]@{
        ExitCode = $exitCode
        Output   = $text
    }
}

function Fail {
    param([string]$Message)
    Write-Host "FAIL: $Message" -ForegroundColor Red
    exit 1
}

function Get-CleanLines {
    param([string]$Text)
    return @(($Text -split "`r?`n") | Where-Object { $_.Trim() -ne '' } | ForEach-Object { $_.Trim() })
}

# Alembic writes INFO log lines to stdout alongside the revision listing.
# A revision line looks like `0002_enable_pgvector (head)`.
function Get-Revision {
    param([string]$Text)
    $line = Get-CleanLines -Text $Text |
        Where-Object { $_ -match '^[0-9A-Za-z_]+(\s+\(head\))?$' } |
        Select-Object -Last 1
    if ($null -eq $line) { return '' }
    return ($line -replace '\s', '')
}

Push-Location $rootDir
try {
    if (-not (Test-Path -LiteralPath $envFile)) {
        Fail "$envFile not found. Copy docker/.env.example to docker/.env first."
    }

    # Parse docker/.env (KEY=VALUE lines) to resolve database credentials.
    $envValues = @{}
    foreach ($line in Get-Content -LiteralPath $envFile) {
        $trimmed = $line.Trim()
        if ($trimmed -eq '' -or $trimmed.StartsWith('#')) { continue }
        $parts = $trimmed.Split('=', 2)
        if ($parts.Count -ne 2) { continue }
        $envValues[$parts[0].Trim()] = $parts[1].Trim()
    }

    $dbUser = if ($envValues.ContainsKey('POSTGRES_USER')) { $envValues['POSTGRES_USER'] } else { 'openmind' }
    $dbName = if ($envValues.ContainsKey('POSTGRES_DB')) { $envValues['POSTGRES_DB'] } else { 'openmind' }
    $psqlBase = @('exec', '-T', 'db', 'psql', '-U', $dbUser, '-d', $dbName, '-tAc')

    Write-Host '== 1/5 PostgreSQL readiness =='
    $ready = Invoke-ComposeRaw -DockerArgs @('exec', '-T', 'db', 'pg_isready', '-U', $dbUser, '-d', $dbName)
    Write-Host $ready.Output.TrimEnd()
    if ($ready.ExitCode -ne 0) {
        Fail 'pg_isready returned non-zero. Is the `db` container running and healthy?'
    }

    Write-Host '== 2/5 pgvector extension version =='
    $ext = Invoke-ComposeRaw -DockerArgs ($psqlBase + "SELECT extversion FROM pg_extension WHERE extname = 'vector';")
    $extVersion = ($ext.Output -replace '\s', '')
    if ($ext.ExitCode -ne 0 -or $extVersion -eq '') {
        Fail "pgvector extension is not enabled in database '$dbName'. Run: docker compose -f docker/compose.dev.yml exec backend alembic upgrade head"
    }
    Write-Host "pgvector version: $extVersion"

    Write-Host '== 3/5 vector type usability =='
    $probe = Invoke-ComposeRaw -DockerArgs ($psqlBase + "SELECT '[1,2,3]'::vector;")
    $probeOut = ($probe.Output -replace '\s', '')
    if ($probe.ExitCode -ne 0 -or $probeOut -ne '[1,2,3]') {
        Fail "vector type probe returned unexpected output: '$probeOut'"
    }
    Write-Host "vector probe: $probeOut"

    Write-Host '== 4/5 Alembic migration state =='
    $heads = Invoke-ComposeRaw -DockerArgs @('exec', '-T', 'backend', 'alembic', 'heads')
    $current = Invoke-ComposeRaw -DockerArgs @('exec', '-T', 'backend', 'alembic', 'current')
    $headRevision = Get-Revision -Text $heads.Output
    $currentRevision = Get-Revision -Text $current.Output
    if ($headRevision -eq '') {
        Fail 'Could not determine the Alembic head revision.'
    }
    Write-Host "head: $headRevision"
    Write-Host "current: $currentRevision"
    if ($currentRevision -ne $headRevision) {
        Fail "Database is not at Alembic head. Run: docker compose -f docker/compose.dev.yml exec backend alembic upgrade head"
    }

    Write-Host '== 5/5 backend database health endpoint =='
    $code = 0
    $body = ''
    try {
        $response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 15
        $code = [int]$response.StatusCode
        $body = $response.Content
    }
    catch {
        $code = 0
        $body = $_.Exception.Message
    }
    Write-Host "HTTP $code $HealthUrl"
    Write-Host "body: $body"
    if ($code -ne 200) {
        Fail "Health endpoint returned HTTP $code, expected 200. Is the backend container running?"
    }
    if ($body -notmatch '"database"\s*:\s*"up"') {
        Fail 'Health endpoint did not report "database":"up".'
    }

    Write-Host ''
    Write-Host 'OK: all database checks passed.' -ForegroundColor Green
}
catch {
    Write-Host "FAIL: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    Pop-Location
}
