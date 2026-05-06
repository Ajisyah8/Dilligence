# Odoo Dev Workflow

Root project:

`C:\Users\SOULMATE PLUS IP\Documents\Project ADS\Dilligence-test`

## Start dev server

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-start.ps1
```

## Upgrade module

Upgrade one module and stop after init:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\module-upgrade.ps1 -Modules website_slides_survey -StopAfterInit
```

Upgrade multiple modules:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\module-upgrade.ps1 -Modules website_slides_survey,survey -StopAfterInit
```

## Restart quickly

Stop the current Odoo process for this repo and start it again in dev mode:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-restart.ps1
```

## Daily flow

1. Start Odoo once:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-start.ps1
```

2. After Python/XML/view/security/model changes:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\module-upgrade.ps1 -Modules website_slides_survey -StopAfterInit
```

3. If routing, assets, filestore config, or server state gets weird:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-restart.ps1
```
