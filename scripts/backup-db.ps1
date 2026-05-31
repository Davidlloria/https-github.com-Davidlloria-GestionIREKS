[CmdletBinding()]
param(
    [string]$DestinationDir = "data/backups",
    [string]$Prefix = "gestion_ireks_backup",
    [string]$Tag = ""
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$resolvedDestinationDir = Join-Path $projectRoot $DestinationDir

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw "No se encontro python en PATH."
}

New-Item -ItemType Directory -Force -Path $resolvedDestinationDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$safeTag = $Tag.Trim()
if ($safeTag) {
    $safeTag = ($safeTag -replace "[^a-zA-Z0-9_-]", "_")
}

$filename = if ($safeTag) {
    "$Prefix`_$timestamp`_$safeTag.db"
} else {
    "$Prefix`_$timestamp.db"
}

$destinationPath = Join-Path $resolvedDestinationDir $filename
$env:GESTION_IREKS_BACKUP_DEST = $destinationPath

try {
    python -c "import os; from pathlib import Path; from app.core.database import backup_database; dest = Path(os.environ['GESTION_IREKS_BACKUP_DEST']); backup_database(dest); print(dest)"
}
finally {
    Remove-Item Env:GESTION_IREKS_BACKUP_DEST -ErrorAction SilentlyContinue
}

if (-not (Test-Path $destinationPath)) {
    throw "No se pudo generar el backup en: $destinationPath"
}

$sizeBytes = (Get-Item $destinationPath).Length
Write-Host "Backup generado: $destinationPath"
Write-Host ("Tamano (bytes): {0}" -f $sizeBytes)
