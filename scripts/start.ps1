param([switch]$Transit, [switch]$Build, [switch]$Tls)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$previousRoutingMode = $env:ROUTING_MODE
$previousOrigin = $env:APP_ORIGIN
$previousCookieSecure = $env:COOKIE_SECURE
$composeArgs = @('compose')
try {
    if ($Transit) {
        $composeArgs += @('--profile', 'transit')
        $env:ROUTING_MODE = 'otp'
    }
    if ($Tls) {
        $composeArgs += @('--profile', 'tls')
        $env:APP_ORIGIN = 'https://localhost:18443'
        $env:COOKIE_SECURE = 'true'
    }
    $composeArgs += @('up','-d')
    if ($Build) { $composeArgs += '--build' }
    & psst OKNO_DB_ADMIN_PASSWORD OKNO_DB_MIGRATOR_PASSWORD OKNO_DB_APP_PASSWORD OKNO_SESSION_SECRET OKNO_ENCRYPTION_KEY -- docker @composeArgs
    $startExitCode = $LASTEXITCODE
} finally {
    $env:ROUTING_MODE = $previousRoutingMode
    $env:APP_ORIGIN = $previousOrigin
    $env:COOKIE_SECURE = $previousCookieSecure
}
exit $startExitCode
