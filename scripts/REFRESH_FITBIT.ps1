##################################################################
#  Fitness Bridge AI — Fitbit Token Refresh Script
#  Run this when Fitbit gives persistent 401 errors,
#  or when your refresh token has expired (~8 months idle).
#  Reads your existing FITBIT_CLIENT_ID / FITBIT_CLIENT_SECRET
#  from .env so you don't need to re-paste them.
##################################################################

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$EnvFile     = Join-Path $ProjectRoot ".env"

if (-not (Test-Path $EnvFile)) {
    Write-Host ""
    Write-Host "  ❌ .env file not found at: $EnvFile" -ForegroundColor Red
    Write-Host "     Run SETUP.bat and then GET_TOKENS.ps1 first." -ForegroundColor DarkYellow
    exit 1
}

function Write-Step($n, $text) {
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host "  Step $n — $text" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
}

function Get-EnvValue($key) {
    $line = Get-Content $EnvFile | Where-Object { $_ -match "^${key}=" } | Select-Object -First 1
    if ($line) { return ($line -split "=", 2)[1].Trim() }
    return $null
}

function Set-EnvValue($key, $value) {
    $content = Get-Content $EnvFile
    $updated = $content -replace "^${key}=.*", "${key}=${value}"
    if (-not ($updated -match "^${key}=")) {
        $updated += "`n${key}=${value}"
    }
    $updated | Set-Content $EnvFile
    # Also update the live environment so the running app picks it up immediately
    [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
}

# ──────────────────────────────────────────────────────────────
#  Header
# ──────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "║   Fitness Bridge AI — Fitbit Token Refresh   ║" -ForegroundColor Yellow
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Yellow

# ──────────────────────────────────────────────────────────────
#  Step 1 — Load or prompt for credentials
# ──────────────────────────────────────────────────────────────

Write-Step 1 "Loading Fitbit credentials from .env"

$fitbitClientId     = Get-EnvValue "FITBIT_CLIENT_ID"
$fitbitClientSecret = Get-EnvValue "FITBIT_CLIENT_SECRET"

if ($fitbitClientId -and $fitbitClientSecret) {
    Write-Host ""
    Write-Host "  ✅ Found FITBIT_CLIENT_ID and FITBIT_CLIENT_SECRET in .env" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "  ⚠️  Credentials not found in .env — please enter them now." -ForegroundColor DarkYellow
    Write-Host "     (Find them at https://dev.fitbit.com/apps)" -ForegroundColor White
    Write-Host ""
    if (-not $fitbitClientId) {
        $fitbitClientId = Read-Host "  Paste your Fitbit CLIENT ID"
        Set-EnvValue "FITBIT_CLIENT_ID" $fitbitClientId
    }
    if (-not $fitbitClientSecret) {
        $fitbitClientSecret = Read-Host "  Paste your Fitbit CLIENT SECRET"
        Set-EnvValue "FITBIT_CLIENT_SECRET" $fitbitClientSecret
    }
}

# ──────────────────────────────────────────────────────────────
#  Step 2 — OAuth authorization
# ──────────────────────────────────────────────────────────────

Write-Step 2 "Fitbit OAuth Authorization"

$redirectUri     = "http://localhost:8501/"
$encodedRedirect = [uri]::EscapeDataString($redirectUri)
$scopes          = "sleep%20heartrate%20activity%20profile"
$authUrl         = "https://www.fitbit.com/oauth2/authorize?client_id=${fitbitClientId}&response_type=code&scope=${scopes}&redirect_uri=${encodedRedirect}"

Write-Host ""
Write-Host "  Opening Fitbit authorization in your browser..." -ForegroundColor White
Write-Host ""
Write-Host "  After you click 'Allow':" -ForegroundColor White
Write-Host "  • You'll be redirected to http://localhost:8501 (Streamlit error page is fine)" -ForegroundColor White
Write-Host "  • Look at the address bar for the code:" -ForegroundColor White
Write-Host "    http://localhost:8501/?code=XXXXXXXX&state=" -ForegroundColor DarkGray
Write-Host "  • Copy ONLY the value between 'code=' and '&state'" -ForegroundColor White
Write-Host ""
Write-Host "  ⚡ The authorization code expires in ~10 minutes — don't delay." -ForegroundColor DarkYellow
Write-Host ""

Start-Process $authUrl
$authCode = Read-Host "  Paste the Fitbit authorization code here"

# ──────────────────────────────────────────────────────────────
#  Step 3 — Exchange code for tokens
# ──────────────────────────────────────────────────────────────

Write-Step 3 "Exchanging code for new Fitbit tokens..."

try {
    $base64 = [Convert]::ToBase64String(
        [Text.Encoding]::ASCII.GetBytes("${fitbitClientId}:${fitbitClientSecret}")
    )

    $body = "grant_type=authorization_code&code=${authCode}&redirect_uri=${encodedRedirect}"

    $response = Invoke-RestMethod `
        -Uri "https://api.fitbit.com/oauth2/token" `
        -Method Post `
        -Headers @{
            Authorization  = "Basic $base64"
            "Content-Type" = "application/x-www-form-urlencoded"
        } `
        -Body $body

    $fitbitAccessToken  = $response.access_token
    $fitbitRefreshToken = $response.refresh_token
    $fitbitExpiresIn    = $response.expires_in   # seconds from now

    if (-not $fitbitAccessToken -or -not $fitbitRefreshToken) {
        throw "Token response missing access_token or refresh_token"
    }

    Set-EnvValue "FITBIT_ACCESS_TOKEN"  $fitbitAccessToken
    Set-EnvValue "FITBIT_REFRESH_TOKEN" $fitbitRefreshToken

    # Compute and store Unix expiry timestamp
    $fitbitExpiresAt = $null
    if ($fitbitExpiresIn) {
        $fitbitExpiresAt = [long]([DateTimeOffset]::UtcNow.ToUnixTimeSeconds()) + [long]$fitbitExpiresIn
        Set-EnvValue "FITBIT_TOKEN_EXPIRES_AT" "$fitbitExpiresAt"
    }

    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║   Fitbit tokens refreshed successfully  ✅   ║" -ForegroundColor Green
    Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Variables updated in .env:" -ForegroundColor White
    Write-Host "    FITBIT_ACCESS_TOKEN     ✅" -ForegroundColor Green

    if ($fitbitExpiresAt) {
        try {
            $expiry = [DateTimeOffset]::FromUnixTimeSeconds($fitbitExpiresAt).LocalDateTime
            Write-Host ("    FITBIT_TOKEN_EXPIRES_AT  ✅  (access token valid until " + $expiry.ToString("dd MMM yyyy HH:mm 'local'") + ")") -ForegroundColor Green
        } catch {
            Write-Host "    FITBIT_TOKEN_EXPIRES_AT  ✅" -ForegroundColor Green
        }
    }

    $fitbitRefreshExpiry = (Get-Date).AddMonths(8)
    Write-Host ("    FITBIT_REFRESH_TOKEN    ✅  (valid ~8 months — expires around " + $fitbitRefreshExpiry.ToString("dd MMM yyyy") + ")") -ForegroundColor Green

    Write-Host ""
    Write-Host "  ℹ️  The app auto-refreshes the access token while running." -ForegroundColor White
    Write-Host "     Only re-run this script if:" -ForegroundColor White
    Write-Host "     • You revoke access on Fitbit" -ForegroundColor White
    Write-Host "     • The refresh token expires (~8 months idle)" -ForegroundColor White
    Write-Host "     • You see persistent 401 errors after restarting the app" -ForegroundColor White
    Write-Host ""
    Write-Host "  Restart Streamlit to apply the new tokens:" -ForegroundColor White
    Write-Host "    streamlit run app.py" -ForegroundColor DarkCyan
    Write-Host ""
}
catch {
    Write-Host ""
    Write-Host "  ❌ Fitbit token exchange failed." -ForegroundColor Red
    Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Tips:" -ForegroundColor DarkYellow
    Write-Host "  • Authorization codes expire in ~10 minutes — try again quickly." -ForegroundColor DarkYellow
    Write-Host "  • Make sure you copied only the code= value, not the full URL." -ForegroundColor DarkYellow
    Write-Host "  • Confirm FITBIT_CLIENT_ID and FITBIT_CLIENT_SECRET are correct." -ForegroundColor DarkYellow
    Write-Host "  • Redirect URI in your Fitbit app settings must include: $redirectUri" -ForegroundColor DarkYellow
    Write-Host ""
    exit 1
}
