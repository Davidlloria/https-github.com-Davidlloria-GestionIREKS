[CmdletBinding()]
param(
    [string]$BindHost = "127.0.0.1",
    [int]$ApiPort = 8000,
    [int]$FrontendPort = 5173,
    [switch]$Reload,
    [switch]$Visible,
    [switch]$DryRun,
    [int]$StartupTimeoutSeconds = 25
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $projectRoot "frontend"
$runtimeDir = Join-Path $projectRoot "runtime"
$logDir = Join-Path $runtimeDir "dev-logs"
$pidFile = Join-Path $runtimeDir "dev-processes.json"

if (-not (Test-Path $frontendDir)) {
    throw "No existe el directorio frontend: $frontendDir"
}

$pythonVenv = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (Test-Path $pythonVenv) {
    $python = $pythonVenv
} else {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        throw "No se encontro python en PATH ni en .venv."
    }
    $python = $pythonCmd.Source
}

$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npm) {
    $npm = Get-Command npm -ErrorAction SilentlyContinue
}
if (-not $npm) {
    throw "No se encontro npm en PATH."
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (Test-Path $pidFile) {
    if (-not $DryRun) {
        throw "Ya existe $pidFile. Deten primero con .\\scripts\\stop-dev.ps1"
    }
    Write-Warning "Ya existe $pidFile. En ejecucion real deberias detener antes con scripts/stop-dev.ps1"
}

function Test-PortListening {
    param([int]$Port)

    $rows = netstat -ano | Select-String -Pattern (":$Port\s")
    foreach ($row in $rows) {
        if ($row.Line -match "LISTENING") {
            return $true
        }
    }
    return $false
}

function Wait-Port {
    param(
        [int]$Port,
        [int]$TimeoutSeconds
    )
    for ($i = 0; $i -lt $TimeoutSeconds; $i++) {
        if (Test-PortListening -Port $Port) {
            return $true
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Start-ManagedProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$ArgList,
        [string]$WorkingDirectory
    )

    $outFile = Join-Path $logDir "$Name.out.log"
    $errFile = Join-Path $logDir "$Name.err.log"

    if ($DryRun) {
        Write-Host "[dry-run] $FilePath $($ArgList -join ' ')" -ForegroundColor Yellow
        return @{
            name = $Name
            pid = 0
            log_out = $outFile
            log_err = $errFile
            command = "$FilePath $($ArgList -join ' ')"
        }
    }

    if (Test-Path $outFile) { Remove-Item $outFile -Force }
    if (Test-Path $errFile) { Remove-Item $errFile -Force }

    $windowStyle = if ($Visible) { "Normal" } else { "Hidden" }
    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgList `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle $windowStyle `
        -RedirectStandardOutput $outFile `
        -RedirectStandardError $errFile `
        -PassThru

    return @{
        name = $Name
        pid = $process.Id
        log_out = $outFile
        log_err = $errFile
        command = "$FilePath $($ArgList -join ' ')"
    }
}

function Stop-IfRunning {
    param([int]$Pid)
    if ($Pid -le 0) { return }
    $running = Get-Process -Id $Pid -ErrorAction SilentlyContinue
    if ($running) {
        Stop-Process -Id $Pid -Force
    }
}

$apiArgs = @("-m", "uvicorn", "app.api.main:app", "--host", $BindHost, "--port", "$ApiPort")
if ($Reload) {
    $apiArgs = @("-m", "uvicorn", "app.api.main:app", "--reload", "--host", $BindHost, "--port", "$ApiPort")
}

$apiProcess = Start-ManagedProcess `
    -Name "api" `
    -FilePath $python `
    -ArgList $apiArgs `
    -WorkingDirectory $projectRoot

if (-not $DryRun) {
    if (-not (Wait-Port -Port $ApiPort -TimeoutSeconds $StartupTimeoutSeconds)) {
        Stop-IfRunning -Pid ([int]$apiProcess.pid)
        throw "La API no levanto en el puerto $ApiPort dentro de $StartupTimeoutSeconds segundos. Revisa $($apiProcess.log_err)"
    }
}

$frontendProcess = Start-ManagedProcess `
    -Name "frontend" `
    -FilePath $npm.Source `
    -ArgList @("run", "dev", "--", "--host", $BindHost, "--port", "$FrontendPort", "--strictPort") `
    -WorkingDirectory $frontendDir

if (-not $DryRun) {
    if (-not (Wait-Port -Port $FrontendPort -TimeoutSeconds $StartupTimeoutSeconds)) {
        Stop-IfRunning -Pid ([int]$frontendProcess.pid)
        Stop-IfRunning -Pid ([int]$apiProcess.pid)
        if (Test-Path $pidFile) {
            Remove-Item $pidFile -Force
        }
        throw "El frontend no levanto en el puerto $FrontendPort dentro de $StartupTimeoutSeconds segundos. Revisa $($frontendProcess.log_err)"
    }
}

$metadata = @{
    started_at = (Get-Date).ToString("o")
    host = $BindHost
    api_port = $ApiPort
    frontend_port = $FrontendPort
    processes = @($apiProcess, $frontendProcess)
}

if (-not $DryRun) {
    $metadata | ConvertTo-Json -Depth 4 | Set-Content -Path $pidFile -Encoding UTF8
}

Write-Host ""
Write-Host "API:      http://$BindHost`:$ApiPort" -ForegroundColor Green
Write-Host "Frontend: http://$BindHost`:$FrontendPort" -ForegroundColor Green
Write-Host "Logs:     $logDir" -ForegroundColor Green
if (-not $DryRun) {
    Write-Host "PID file: $pidFile" -ForegroundColor Green
}
