$ErrorActionPreference = 'Stop'
$projectPath = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
[string[]]$testArgs = if ($args.Count) { $args } else { @('tests') }
& docker run --rm --network none --entrypoint python --mount "type=bind,source=$projectPath,target=/workspace,readonly" --workdir /workspace okno-app:local -m pytest -q -p no:cacheprovider @testArgs
exit $LASTEXITCODE
