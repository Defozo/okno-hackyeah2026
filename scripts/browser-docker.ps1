param([ValidateSet('browser-check.cjs', 'keyboard-check.cjs', 'ux-regression.cjs')][string]$Check = 'browser-check.cjs')
$ErrorActionPreference = 'Stop'
$projectPath = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$axePath = Join-Path $projectPath '.runtime/axe.min.js'
if (-not (Test-Path -LiteralPath $axePath)) {
    New-Item -ItemType Directory -Force (Split-Path $axePath -Parent) | Out-Null
    Invoke-WebRequest 'https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.3/axe.min.js' -OutFile $axePath
}
if ((Get-FileHash -LiteralPath $axePath -Algorithm SHA256).Hash -ne 'D8B6DA0B871C914820AB57529FDF3940DF93DC159193C9634115B3687D07DBFC') { throw 'Unexpected axe-core checksum' }
$gatewayAddress = (& docker run --rm --network okno_outbound --entrypoint python okno-app:local -c "import socket; print(socket.gethostbyname('host.docker.internal'))").Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve Docker host address' }
& docker run --rm --network okno_outbound --entrypoint /usr/local/lib/python3.12/site-packages/playwright/driver/node --mount "type=bind,source=$projectPath,target=/workspace" --workdir /workspace -e PLAYWRIGHT_MODULE=/usr/local/lib/python3.12/site-packages/playwright/driver/package -e CHROMIUM_HOST_IP=$gatewayAddress -e RECORD_VIDEO=$env:RECORD_VIDEO -e OKNO_URL=$env:OKNO_URL -e OKNO_TEST_LOCAL_CA=$env:OKNO_TEST_LOCAL_CA okno-app:local "scripts/$Check"
exit $LASTEXITCODE
