$ErrorActionPreference = 'Stop'
$projectPath = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readyPath = Join-Path $projectPath '.runtime/restart-ready'
$continuePath = Join-Path $projectPath '.runtime/restart-continue'
$reportPath = Join-Path $projectPath 'docs/evidence/restart-report.json'
$clientName = 'okno-restart-check-' + [Guid]::NewGuid().ToString('N').Substring(0, 10)
New-Item -ItemType Directory -Force (Split-Path $readyPath -Parent) | Out-Null
foreach ($path in @($readyPath, $continuePath, $reportPath)) {
    if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path }
}
try {
    $clientId = & docker run -d --name $clientName --network okno_outbound --entrypoint python --mount "type=bind,source=$projectPath,target=/workspace" --workdir /workspace okno-app:local scripts/restart-check.py
    if ($LASTEXITCODE -ne 0) { throw 'Cannot start restart verification client' }
    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    while (-not (Test-Path -LiteralPath $readyPath)) {
        if ([DateTime]::UtcNow -gt $deadline) { throw 'Client did not save its synthetic plan' }
        Start-Sleep -Milliseconds 500
    }
    $before = (& docker inspect --format '{{.State.StartedAt}}' okno-api-1).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect API before restart' }
    & docker restart okno-api-1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Cannot restart API' }
    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    do {
        $healthy = $false
        try { $healthy = (Invoke-RestMethod http://localhost:18430/health/ready -TimeoutSec 5).status -eq 'ready' } catch { }
        if (-not $healthy) { Start-Sleep -Milliseconds 500 }
    } until ($healthy -or [DateTime]::UtcNow -gt $deadline)
    if (-not $healthy) { throw 'API did not become ready after restart' }
    $after = (& docker inspect --format '{{.State.StartedAt}}' okno-api-1).Trim()
    if ($LASTEXITCODE -ne 0 -or $before -eq $after) { throw 'API restart identity did not change' }
    Set-Content -LiteralPath $continuePath -Value 'API restarted and readiness verified.' -Encoding utf8
    $clientExit = (& docker wait $clientName).Trim()
    & docker logs $clientName
    if ($clientExit -ne '0') { throw 'Restart verification client failed' }
    $report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
    $report | Add-Member -NotePropertyName api_started_before -NotePropertyValue $before
    $report | Add-Member -NotePropertyName api_started_after -NotePropertyValue $after
    $report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $reportPath -Encoding utf8
} finally {
    & docker rm -f $clientName 2>$null | Out-Null
    foreach ($path in @($readyPath, $continuePath)) {
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path }
    }
}
