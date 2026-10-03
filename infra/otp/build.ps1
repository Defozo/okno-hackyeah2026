$ErrorActionPreference = 'Stop'
$otpRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$otpData = Join-Path $otpRoot 'data'
python (Join-Path $otpRoot 'download.py')
if ($LASTEXITCODE -ne 0) { throw 'Nie udało się zweryfikować danych OTP' }
Copy-Item -LiteralPath (Join-Path $otpRoot 'otp-config.json'),(Join-Path $otpRoot 'build-config.json'),(Join-Path $otpRoot 'router-config.json') -Destination $otpData
docker run --rm --memory=14g -e JAVA_TOOL_OPTIONS=-Xmx12g --mount "type=bind,source=$otpData,target=/var/opentripplanner" opentripplanner/opentripplanner:2.7.0@sha256:640870b240ad206d05634e7a066588804c6e23abebf37cbc02b0c9ba66073486 --build --save
if ($LASTEXITCODE -ne 0) { throw 'Budowa grafu OTP nie powiodła się' }
python (Join-Path $otpRoot 'pin_graph.py')
