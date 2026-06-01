[CmdletBinding()]
param(
    [switch]$RequireTesseract
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $projectRoot "frontend"

function Get-MajorVersion {
    param([string]$VersionText)

    $text = [string]$VersionText
    if (-not $text) { return -1 }
    if ($text.StartsWith("v")) { $text = $text.Substring(1) }
    $parts = $text.Split(".")
    if ($parts.Length -lt 1) { return -1 }
    $major = 0
    if (-not [int]::TryParse($parts[0], [ref]$major)) { return -1 }
    return $major
}

function Get-MinorVersion {
    param([string]$VersionText)

    $text = [string]$VersionText
    if (-not $text) { return -1 }
    if ($text.StartsWith("v")) { $text = $text.Substring(1) }
    $parts = $text.Split(".")
    if ($parts.Length -lt 2) { return -1 }
    $minor = 0
    if (-not [int]::TryParse($parts[1], [ref]$minor)) { return -1 }
    return $minor
}

Write-Host "[env] Proyecto: $projectRoot"

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw "No se encontro python en PATH."
}

$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
    throw "No se encontro node en PATH."
}

$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npm) {
    $npm = Get-Command npm -ErrorAction SilentlyContinue
}
if (-not $npm) {
    throw "No se encontro npm en PATH."
}

$pyVersionRaw = (& python --version).Trim()
$nodeVersionRaw = (& node --version).Trim()
$npmVersionRaw = (& $npm.Source --version).Trim()

$pyParts = $pyVersionRaw.Split(" ", [System.StringSplitOptions]::RemoveEmptyEntries)
$pyVersion = if ($pyParts.Length -ge 2) { $pyParts[1] } else { "" }
$pyMajor = Get-MajorVersion -VersionText $pyVersion
$pyMinor = Get-MinorVersion -VersionText $pyVersion
if ($pyMajor -lt 3 -or ($pyMajor -eq 3 -and $pyMinor -lt 12)) {
    throw "Python 3.12+ requerido. Detectado: $pyVersionRaw"
}

$nodeMajor = Get-MajorVersion -VersionText $nodeVersionRaw
if ($nodeMajor -lt 20) {
    throw "Node 20+ requerido. Detectado: $nodeVersionRaw"
}

Write-Host "[env] Python: $pyVersionRaw"
Write-Host "[env] Node:   $nodeVersionRaw"
Write-Host "[env] npm:    $npmVersionRaw"

$requiredPaths = @(
    (Join-Path $projectRoot "requirements.txt"),
    (Join-Path $projectRoot ".env.example"),
    (Join-Path $projectRoot "docs\local-environment.md"),
    (Join-Path $projectRoot "scripts\start-dev.ps1"),
    (Join-Path $projectRoot "scripts\validate-gates.ps1"),
    (Join-Path $frontendDir "package-lock.json"),
    (Join-Path $frontendDir ".env.example")
)

foreach ($path in $requiredPaths) {
    if (-not (Test-Path $path)) {
        throw "Falta archivo requerido: $path"
    }
}

$frontendEnvPath = Join-Path $frontendDir ".env"
if (Test-Path $frontendEnvPath) {
    $apiLine = Select-String -Path $frontendEnvPath -Pattern "^VITE_API_BASE_URL=" -SimpleMatch:$false -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($apiLine) {
        Write-Host "[env] frontend/.env -> $($apiLine.Line.Trim())"
    }
    else {
        Write-Warning "frontend/.env existe pero no define VITE_API_BASE_URL; se usara el default de frontend/src/api/http.ts"
    }
}
else {
    Write-Host "[env] frontend/.env no existe; se usara VITE_API_BASE_URL por defecto."
}

$tesseractOk = $false
$tesseractCmd = ""
$tesseractCheck = @'
import json
import os
from app.services.order_document_parser import OrderDocumentParser

ok = bool(OrderDocumentParser._try_configure_tesseract())
payload = {'ok': ok, 'cmd': os.environ.get('TESSERACT_CMD', '')}
print(json.dumps(payload))
'@

$tesseractRaw = (& python -c $tesseractCheck 2>$null)
$tesseractJson = ""
if ($tesseractRaw) {
    $tesseractJson = ([string]$tesseractRaw).Trim()
}
if ($LASTEXITCODE -eq 0 -and $tesseractJson) {
    try {
        $payload = $tesseractJson | ConvertFrom-Json
        $tesseractOk = [bool]$payload.ok
        $tesseractCmd = [string]$payload.cmd
    }
    catch {
        $tesseractOk = $false
    }
}

if ($tesseractOk) {
    if ($tesseractCmd) {
        Write-Host "[env] Tesseract: detectado via TESSERACT_CMD ($tesseractCmd)"
    }
    else {
        Write-Host "[env] Tesseract: detectado."
    }
}
else {
    $msg = "Tesseract no detectado. OCR de albaranes/facturas no estara disponible."
    if ($RequireTesseract) {
        throw $msg
    }
    Write-Warning $msg
}

Write-Host "[env] OK"
