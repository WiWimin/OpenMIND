$ErrorActionPreference = 'Stop'

Write-Output '== backend =='
Push-Location backend
try {
    ruff check .
    pytest
}
finally {
    Pop-Location
}

Write-Output '== frontend =='
Push-Location frontend
try {
    npm run typecheck
    npm run lint
    npm run test
}
finally {
    Pop-Location
}
