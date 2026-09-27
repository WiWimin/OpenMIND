$ErrorActionPreference = 'Stop'

Push-Location (Join-Path $PSScriptRoot '..')
try {
    docker compose -f docker/compose.dev.yml up --build
}
finally {
    Pop-Location
}
