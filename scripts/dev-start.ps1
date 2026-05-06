param(
    [string]$Database = "odoo_dev",
    [string[]]$DevFlags = @("xml", "assets", "qweb", "reload")
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$globalPython = "C:\Users\SOULMATE PLUS IP\AppData\Local\Programs\Python\Python312\python.exe"
$odooBin = Join-Path $root "odoo-bin"
$config = Join-Path $root "odoo.conf"
$devMode = [string]::Join(",", $DevFlags)

if (-not (Test-Path $python)) {
    if (Test-Path $globalPython) {
        $python = $globalPython
    } else {
        throw "Python runtime not found. Checked: $python and $globalPython"
    }
}

& $python $odooBin -c $config -d $Database --dev=$devMode
