param(
    [string]$Database = "odoo_dev"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$config = Join-Path $root "odoo.conf"

if (-not (Test-Path $python)) {
    throw "Python venv not found: $python"
}

& $python -m odoo -c $config -d $Database -i base --without-demo --stop-after-init
