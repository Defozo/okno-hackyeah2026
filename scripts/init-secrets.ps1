$ErrorActionPreference = 'Stop'
# Generate dedicated local application credentials. Never echo secret values.
$secretNames = @('OKNO_DB_ADMIN_PASSWORD', 'OKNO_DB_MIGRATOR_PASSWORD', 'OKNO_DB_APP_PASSWORD', 'OKNO_SESSION_SECRET', 'OKNO_ENCRYPTION_KEY')
$inventory = (& psst list --json | ConvertFrom-Json).secrets.name
foreach ($secretName in $secretNames) {
    if ($inventory -contains $secretName) { Write-Host "$secretName already exists"; continue }
    $secretBytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($secretBytes)
    $secretValue = [Convert]::ToBase64String($secretBytes).Replace('+','-').Replace('/','_')
    $secretValue | & psst set $secretName --stdin --tag okno --quiet
    if ($LASTEXITCODE -ne 0) { throw "Could not store $secretName" }
    $secretValue = $null
    Write-Host "$secretName created"
}
