param(
    [string]$Database = "odoo_dev",
    [string[]]$DevFlags = @(),
    [int]$Port = 8070
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$config = Join-Path $root "odoo.conf"
$logFile = Join-Path $root "odoo-dev.log"

if (-not (Test-Path $python)) {
    throw "Python venv not found: $python"
}

$listenerPattern = ":$Port"
$listenerPids = netstat -ano |
    Select-String $listenerPattern |
    ForEach-Object {
        if ($_.Line -match "LISTENING\s+(\d+)\s*$") {
            [int]$Matches[1]
        }
    } |
    Sort-Object -Unique

if ($listenerPids) {
    foreach ($processId in $listenerPids) {
        Stop-Process -Id $processId -Force -ErrorAction Stop
    }
    Start-Sleep -Seconds 2
}

$argumentList = "-m odoo -c `"$config`" -d $Database"
if ($DevFlags.Count -gt 0) {
    $argumentList = "$argumentList --dev=$([string]::Join(",", $DevFlags))"
}

$process = Start-Process -FilePath $python `
    -ArgumentList $argumentList `
    -WorkingDirectory $root `
    -WindowStyle Hidden `
    -PassThru

"Started Odoo PID: $($process.Id)"
"Log file: $logFile"
