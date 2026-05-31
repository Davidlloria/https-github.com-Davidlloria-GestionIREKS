param(
    [switch]$SkipFrontend,
    [switch]$SkipIntegrity
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$frontendDir = Join-Path $projectRoot "frontend"
$tmpDir = Join-Path $projectRoot ".pytest_tmp"

$oldTmp = $env:TMP
$oldTemp = $env:TEMP

Write-Host "[gates] Proyecto: $projectRoot"

try {
    New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
    $env:TMP = (Resolve-Path $tmpDir).Path
    $env:TEMP = $env:TMP

    Write-Host "[gates] Ejecutando pytest..."
    python -m pytest tests -q

    # Restaurar TMP/TEMP antes de lanzar herramientas Node para evitar
    # que procesos internos usen directorios temporales efimeros.
    $env:TMP = $oldTmp
    $env:TEMP = $oldTemp

    if (-not $SkipIntegrity) {
        Write-Host "[gates] Ejecutando integrity_check..."
        python -c "from app.core.database import run_integrity_check; print(run_integrity_check())"
    }

    if (-not $SkipFrontend) {
        Write-Host "[gates] Ejecutando lint/build frontend..."
        Push-Location $frontendDir
        try {
            npm.cmd run lint
            npm.cmd run build
        }
        finally {
            Pop-Location
        }
    }

    Write-Host "[gates] OK"
}
finally {
    $env:TMP = $oldTmp
    $env:TEMP = $oldTemp
    if (Test-Path $tmpDir) {
        Remove-Item -LiteralPath $tmpDir -Recurse -Force
    }
}
