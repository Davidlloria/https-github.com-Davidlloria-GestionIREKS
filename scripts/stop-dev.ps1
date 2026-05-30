[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $projectRoot "runtime\dev-processes.json"

if (-not (Test-Path $pidFile)) {
    Write-Host "No existe archivo de procesos: $pidFile"
    exit 0
}

$metadata = Get-Content $pidFile -Raw | ConvertFrom-Json
$stopped = @()
$missing = @()

foreach ($proc in $metadata.processes) {
    $processId = [int]$proc.pid
    if ($processId -le 0) {
        continue
    }

    $running = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if (-not $running) {
        $missing += $processId
        continue
    }

    if ($Force) {
        Stop-Process -Id $processId -Force
    } else {
        Stop-Process -Id $processId
    }
    $stopped += $processId
}

# Limpieza adicional: si queda algun proceso hijo (por ejemplo uvicorn --reload),
# intentamos detenerlo por patron de comando.
if ($Force) {
    try {
        $candidates = Get-CimInstance Win32_Process |
            Where-Object {
                $_.Name -eq "python.exe" -and
                $_.CommandLine -like "*app.api.main:app*"
            }
        foreach ($candidate in $candidates) {
            $candidateId = [int]$candidate.ProcessId
            $running = Get-Process -Id $candidateId -ErrorAction SilentlyContinue
            if ($running) {
                Stop-Process -Id $candidateId -Force
                if ($stopped -notcontains $candidateId) {
                    $stopped += $candidateId
                }
            }
        }
    } catch {
        Write-Warning "No se pudo hacer limpieza avanzada por comando (CIM): $($_.Exception.Message)"
    }
}

if (Test-Path $pidFile) {
    Remove-Item $pidFile -Force
}

if ($stopped.Count -gt 0) {
    Write-Host "Procesos detenidos: $($stopped -join ', ')"
}
if ($missing.Count -gt 0) {
    Write-Host "PIDs no encontrados (ya detenidos): $($missing -join ', ')"
}
Write-Host "Archivo PID eliminado: $pidFile"
