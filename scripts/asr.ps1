param(
    [Parameter(Position = 0)]
    [ValidateSet('up', 'down', 'status', 'logs', 'smoke', 'restart')]
    [string]$Command = 'status',
    [switch]$NoBackendRecreate
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $RepoRoot 'docker\compose.dev.yml'
$EnvFile = Join-Path $RepoRoot 'docker\.env'
$Fixture = Join-Path $RepoRoot 'frontend\e2e\fixtures\sample-audio-zh.wav'
$ComposeArgs = @('-f', $ComposeFile, '--env-file', $EnvFile, '--profile', 'asr')

function Get-DotEnvValue {
    param([string]$Name, [string]$Default)
    $fromProcess = [Environment]::GetEnvironmentVariable($Name)
    if ($fromProcess) { return $fromProcess }
    if (-not (Test-Path $EnvFile)) { return $Default }
    $line = Get-Content $EnvFile | Where-Object { $_ -match "^$Name=" } | Select-Object -Last 1
    if (-not $line) { return $Default }
    $value = ($line -split '=', 2)[1].Trim()
    if ($value) { return $value }
    return $Default
}

$HostPort = Get-DotEnvValue 'ASR_HOST_PORT' '10096'
$Model = Get-DotEnvValue 'FUNASR_MODEL' 'sensevoice'
$BaseUrl = "http://127.0.0.1:$HostPort"

function Invoke-Compose {
    param([string[]]$ComposeCommand)
    & docker compose @ComposeArgs @ComposeCommand
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed with exit code $LASTEXITCODE"
    }
}

function Get-Health {
    try {
        return Invoke-RestMethod -Uri "$BaseUrl/health" -TimeoutSec 5
    }
    catch {
        return $null
    }
}

function Wait-Healthy {
    param([int]$TimeoutSeconds = 1200)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $health = Get-Health
        if ($health -and $health.status -eq 'ok') {
            Write-Host "FunASR is healthy: $BaseUrl/health"
            return
        }
        Start-Sleep -Seconds 5
    }
    throw "FunASR did not become healthy within $TimeoutSeconds seconds. Check: scripts/asr.ps1 logs"
}

function Recreate-Backend {
    $env:ASR_API_BASE = 'http://asr:8000/v1'
    $env:ASR_API_KEY = 'local-dev'
    $env:ASR_MODEL = $Model
    & docker compose -f $ComposeFile --env-file $EnvFile up -d --force-recreate backend
    if ($LASTEXITCODE -ne 0) {
        throw "backend recreate failed with exit code $LASTEXITCODE"
    }
}

switch ($Command) {
    'up' {
        if (-not (Test-Path $EnvFile)) {
            throw "Missing $EnvFile; copy docker/.env.example to docker/.env first."
        }
        Invoke-Compose @('up', '-d', '--build', 'asr')
        Wait-Healthy
        if (-not $NoBackendRecreate) {
            Recreate-Backend
        }
        Write-Host "Local FunASR is ready; model=$Model, endpoint=$BaseUrl/v1"
        Write-Host "To persist across a plain 'docker compose up', add to docker/.env:"
        Write-Host "  ASR_API_BASE=http://asr:8000/v1"
        Write-Host "  ASR_API_KEY=local-dev"
        Write-Host "  ASR_MODEL=$Model"
    }
    'down' {
        Invoke-Compose @('stop', 'asr')
        Write-Host 'FunASR stopped. Audio uploads fail until it is started again.'
    }
    'restart' {
        Invoke-Compose @('restart', 'asr')
        Wait-Healthy
    }
    'logs' {
        Invoke-Compose @('logs', '-f', 'asr')
    }
    'status' {
        Invoke-Compose @('ps', 'asr')
        $health = Get-Health
        if ($health) {
            $health | ConvertTo-Json -Compress
        }
        else {
            Write-Host "FunASR is not reachable at $BaseUrl/health"
        }
    }
    'smoke' {
        if (-not (Test-Path $Fixture)) {
            throw "Missing fixture: $Fixture"
        }
        Push-Location (Split-Path -Parent $Fixture)
        try {
            & curl.exe -sS -X POST "$BaseUrl/v1/audio/transcriptions" `
                -F "file=@$(Split-Path -Leaf $Fixture)" `
                -F "model=$Model"
            if ($LASTEXITCODE -ne 0) {
                throw "curl failed with exit code $LASTEXITCODE"
            }
        }
        finally {
            Pop-Location
        }
    }
}
