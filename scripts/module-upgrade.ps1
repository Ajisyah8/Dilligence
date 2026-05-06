param(
    [Parameter(Mandatory = $true)]
    [string[]]$Modules,
    [string]$Database = "odoo_dev",
    [switch]$StopAfterInit
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$odooBin = Join-Path $root "odoo-bin"
$config = Join-Path $root "odoo.conf"

if (-not (Test-Path $python)) {
    throw "Python venv not found: $python"
}

$moduleList = [string]::Join(",", $Modules)
$args = @($odooBin, "-c", $config, "-d", $Database, "-u", $moduleList)
if ($StopAfterInit) {
    $args += "--stop-after-init"
}

& $python @args
