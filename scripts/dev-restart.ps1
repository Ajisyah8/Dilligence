param(
    [string]$Database = "odoo_dev",
    [string[]]$DevFlags = @()
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$config = Join-Path $root "odoo.conf"
$logFile = Join-Path $root "odoo-dev.log"

if (-not (Test-Path $python)) {
    throw "Python venv not found: $python"
}

try {
    $moduleCommandPattern = [regex]::Escape("-m odoo")
    $running = Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -like "python*.exe" -and
            $_.CommandLine -match $moduleCommandPattern -and
            $_.CommandLine -match [regex]::Escape($config)
        }
} catch {
    Write-Warning "Could not inspect running Odoo processes: $($_.Exception.Message)"
    $running = @()
}

if ($running) {
    $running | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force
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
