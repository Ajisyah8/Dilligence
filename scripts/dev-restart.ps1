param(
    [string]$Database = "odoo_dev",
    [string[]]$DevFlags = @("xml", "assets", "qweb", "reload")
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$odooBin = Join-Path $root "odoo-bin"
$config = Join-Path $root "odoo.conf"
$devMode = [string]::Join(",", $DevFlags)
$logFile = Join-Path $root "odoo-dev.log"

if (-not (Test-Path $python)) {
    throw "Python venv not found: $python"
}

$currentCommandPattern = [regex]::Escape($odooBin)
$running = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -like "python*.exe" -and
        $_.CommandLine -match $currentCommandPattern -and
        $_.CommandLine -match [regex]::Escape($config)
    }

if ($running) {
    $running | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force
    }
    Start-Sleep -Seconds 2
}

$process = Start-Process -FilePath $python `
    -ArgumentList @($odooBin, "-c", $config, "-d", $Database, "--dev=$devMode") `
    -WorkingDirectory $root `
    -WindowStyle Hidden `
    -PassThru

"Started Odoo PID: $($process.Id)"
"Log file: $logFile"
