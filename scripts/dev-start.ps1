param(
    [string]$Database = "odoo_dev",
    [string[]]$DevFlags = @()
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$config = Join-Path $root "odoo.conf"

if (-not (Test-Path $python)) {
    throw "Python venv not found: $python"
}

$args = @("-m", "odoo", "-c", $config, "-d", $Database)
if ($DevFlags.Count -gt 0) {
    $args += "--dev=$([string]::Join(",", $DevFlags))"
}

& $python @args
