param([switch]$Build)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:OKNO_DEMO_NGROK_IMAGE = 'ngrok/ngrok@sha256:14d80d083e5b53145f416bbbd36238336c9de4016c43fd950eb2eb845670583b'
$transitNetworks = (& docker inspect okno-otp-1 --format '{{json .NetworkSettings.Networks}}' | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0) { throw 'Start the local transit profile first: ./scripts/start.ps1 -Transit' }
$networks = & docker network ls --format '{{.Name}}'
if ($networks -notcontains 'okno_demo_transit') {
    & docker network create --internal --subnet 10.253.188.0/28 okno_demo_transit | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Cannot create dedicated transit network' }
}
if (-not $transitNetworks.PSObject.Properties['okno_demo_transit']) {
    & docker network connect --alias otp okno_demo_transit okno-otp-1
    if ($LASTEXITCODE -ne 0) { throw 'Cannot attach routing service' }
}
if ($Build) {
    & docker build -t okno-app:competition-20261003 .
    if ($LASTEXITCODE -ne 0) { throw 'Application image build failed' }
}
& docker image inspect okno-app:competition-20261003 --format '{{.Id}}' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Application image unavailable. Run ./scripts/start-public.ps1 -Build first.' }
& psst OKNO_DEMO_DB_ADMIN_PASSWORD OKNO_DEMO_DB_MIGRATOR_PASSWORD OKNO_DEMO_DB_APP_PASSWORD OKNO_DEMO_SESSION_SECRET OKNO_DEMO_ENCRYPTION_KEY OKNO_DEMO_GATEWAY_KEY OKNO_DEMO_NGROK_AUTHTOKEN -- docker compose -f compose.public.yaml up -d
exit $LASTEXITCODE
