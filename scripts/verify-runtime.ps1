$ErrorActionPreference = 'Stop'
$projectPath = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$containerName = 'okno-api-1'
$remoteCode = @'
import hashlib, json
from pathlib import Path
root = Path('/app')
paths = sorted(list((root / 'api').rglob('*.py')) + [p for p in (root / 'web/dist').rglob('*') if p.is_file()])
print(json.dumps([{'path': p.relative_to(root).as_posix(), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]))
'@
$remoteOutput = & docker exec $containerName python -c $remoteCode
if ($LASTEXITCODE -ne 0) { throw 'Cannot read running application files' }
$remoteFiles = @($remoteOutput | ConvertFrom-Json)
$mismatches = @()
foreach ($file in $remoteFiles) {
    $localPath = Join-Path $projectPath $file.path
    if (-not (Test-Path -LiteralPath $localPath -PathType Leaf)) {
        $mismatches += $file.path
    } elseif ((Get-FileHash -LiteralPath $localPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) {
        $mismatches += $file.path
    }
}
$imageId = (& docker inspect --format '{{.Image}}' $containerName).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot read running image identity' }
$report = [ordered]@{
    checked_at = [DateTime]::UtcNow.ToString('o')
    image = $imageId
    file_count = $remoteFiles.Count
    matching = $mismatches.Count -eq 0
    mismatches = @($mismatches)
    files = @($remoteFiles)
}
$outputPath = Join-Path $projectPath 'docs/evidence/runtime-manifest.json'
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $outputPath -Encoding utf8
[ordered]@{ image = $imageId; files = $remoteFiles.Count; mismatches = $mismatches.Count } | ConvertTo-Json
if ($mismatches.Count -gt 0) { throw 'Running files differ from the workspace' }
