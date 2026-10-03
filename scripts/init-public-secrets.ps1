$ErrorActionPreference = 'Stop'
$inventory = (& psst list --json | ConvertFrom-Json).secrets.name
$names = @('OKNO_DEMO_DB_ADMIN_PASSWORD','OKNO_DEMO_DB_MIGRATOR_PASSWORD','OKNO_DEMO_DB_APP_PASSWORD','OKNO_DEMO_SESSION_SECRET','OKNO_DEMO_ENCRYPTION_KEY','OKNO_DEMO_GATEWAY_KEY')
foreach ($name in $names) {
    if ($inventory -contains $name) { Write-Host "$name exists"; continue }
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    $value = [Convert]::ToBase64String($bytes).Replace('+','-').Replace('/','_')
    $value | & psst set $name --stdin --tag okno-demo --quiet
    if ($LASTEXITCODE -ne 0) { throw "Cannot store $name" }
    $value = $null
    Write-Host "$name created"
}
if ($inventory -notcontains 'OKNO_DEMO_NGROK_AUTHTOKEN') {
    $config = Get-Content -LiteralPath (Join-Path $env:LOCALAPPDATA 'ngrok/ngrok.yml') -Raw
    $match = [regex]::Match($config, '(?m)^\s*authtoken:\s*([^\s#]+)\s*$')
    if (-not $match.Success) { throw 'Existing ngrok credential unavailable' }
    $match.Groups[1].Value.Trim('"', "'") | & psst set OKNO_DEMO_NGROK_AUTHTOKEN --stdin --tag okno-demo --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Cannot store ngrok credential' }
    $config = $null
    $match = $null
    Write-Host 'OKNO_DEMO_NGROK_AUTHTOKEN stored in psst'
}
