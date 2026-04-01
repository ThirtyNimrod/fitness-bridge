##################################################################
#  Fitness Bridge AI — API Token Setup Script
#  Run this script AFTER running SETUP.bat
#  It will guide you through getting Strava + Fitbit tokens
#  and write them directly into your .env file.
##################################################################

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $ProjectRoot ".env"

# Ensure .env exists
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $ProjectRoot ".env.example") $EnvFile
}

function Write-Step($n, $text) {
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host "  Step $n — $text" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
}

function Set-EnvValue($key, $value) {
    $content = Get-Content $EnvFile
    $updated = $content -replace "^${key}=.*", "${key}=${value}"
    if (-not ($updated -match "^${key}=")) {
        $updated += "`n${key}=${value}"
    }
    $updated | Set-Content $EnvFile
}

# ──────────────────────────────────────────────
#  STRAVA
# ──────────────────────────────────────────────

Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "║     Fitness Bridge AI — Token Setup          ║" -ForegroundColor Yellow
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Yellow

Write-Step 1 "Strava API Credentials"
Write-Host @"

  1. Go to: https://www.strava.com/settings/api
  2. If you haven't created an app yet, fill in any name/website.
  3. Authorization Callback Domain MUST be `localhost`.
  4. On the API settings page you will see:
       - Client ID     (a short number like 216215)
       - Client Secret (click 'Show' to reveal)
"@

$stravaClientId     = Read-Host "  Paste your Strava CLIENT ID"
$stravaClientSecret = Read-Host "  Paste your Strava CLIENT SECRET"

Set-EnvValue "STRAVA_CLIENT_ID"     $stravaClientId
Set-EnvValue "STRAVA_CLIENT_SECRET" $stravaClientSecret

Write-Step 2 "Strava OAuth Authorization"
$stravaScopes = "read,activity:read_all"
$stravaAuthUrl = "https://www.strava.com/oauth/authorize?client_id=${stravaClientId}&response_type=code&redirect_uri=http://localhost/exchange_token&approval_prompt=force&scope=${stravaScopes}"

Write-Host ""
Write-Host "  Open this URL in your browser:" -ForegroundColor White
Write-Host ""
Write-Host "  $stravaAuthUrl" -ForegroundColor DarkCyan
Write-Host ""
Write-Host "  After you click 'Authorize':" -ForegroundColor White
Write-Host "  - You'll be redirected to a localhost URL that might say 'Site can't be reached'" -ForegroundColor White
Write-Host "  - Look at the address bar for the code, it will look like:" -ForegroundColor White
Write-Host "    http://localhost/exchange_token?state=&code=XXXXXXXX&scope=..." -ForegroundColor DarkGray
Write-Host "  - Copy ONLY the part between 'code=' and '&scope='" -ForegroundColor White
Write-Host ""

Start-Process $stravaAuthUrl
$stravaAuthCode = Read-Host "  Paste the Strava authorization code here"

try {
    # Use Python from the venv to do the token exchange (avoids PowerShell TLS issues)
    $pythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    $pyScript = @"
import urllib.request, urllib.parse, json, sys
data = urllib.parse.urlencode({
    'client_id': '$stravaClientId',
    'client_secret': '$stravaClientSecret',
    'code': '$stravaAuthCode',
    'grant_type': 'authorization_code'
}).encode()
req = urllib.request.Request('https://www.strava.com/api/v3/oauth/token', data=data, method='POST')
with urllib.request.urlopen(req) as r:
    body = json.load(r)
print(body['refresh_token'])
"@
    $stravaRefreshToken = & $pythonExe -c $pyScript
    if ($LASTEXITCODE -ne 0 -or -not $stravaRefreshToken) { throw "Python exchange failed" }

    Set-EnvValue "STRAVA_REFRESH_TOKEN" $stravaRefreshToken
    Write-Host ""
    Write-Host "  ✅ Strava credentials saved with proper scopes!" -ForegroundColor Green
}
catch {
    Write-Host ""
    Write-Host "  ❌ Strava Token exchange failed." -ForegroundColor Red
    Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "  The auth code expires quickly. Re-run and paste the code immediately." -ForegroundColor DarkYellow
    exit 1
}

# ──────────────────────────────────────────────
#  FITBIT
# ──────────────────────────────────────────────

Write-Step 2 "Fitbit Developer App"
Write-Host @"

  1. Go to: https://dev.fitbit.com/apps/new
  2. Fill in the form:
       - Application Name : anything (e.g. "FitnessBridge")
       - Description       : personal training tool
       - Application Website: https://github.com/ThirtyNimrod/fitness-bridge
       - Redirect URL      : https://github.com/ThirtyNimrod/fitness-bridge
       - OAuth 2.0 Application Type: PERSONAL  ← required for HRV data
       - Default Access Type: Read-Only
  3. Submit. You'll land on a page showing Client ID and Client Secret.
"@

$fitbitClientId     = Read-Host "  Paste your Fitbit CLIENT ID"
$fitbitClientSecret = Read-Host "  Paste your Fitbit CLIENT SECRET"

Set-EnvValue "FITBIT_CLIENT_ID"     $fitbitClientId
Set-EnvValue "FITBIT_CLIENT_SECRET" $fitbitClientSecret

# ──────────────────────────────────────────────
#  FITBIT OAUTH FLOW
# ──────────────────────────────────────────────

Write-Step 3 "Fitbit OAuth Authorization"

$redirectUri = "http://localhost:8501/"
$encodedRedirect = [uri]::EscapeDataString($redirectUri)
$scopes = "sleep%20heartrate%20activity%20profile"
$authUrl = "https://www.fitbit.com/oauth2/authorize?client_id=${fitbitClientId}&response_type=code&scope=${scopes}&redirect_uri=${encodedRedirect}"

Write-Host ""
Write-Host "  Open this URL in your browser:" -ForegroundColor White
Write-Host ""
Write-Host "  $authUrl" -ForegroundColor DarkCyan
Write-Host ""
Write-Host "  After you click 'Allow':" -ForegroundColor White
Write-Host "  - You'll be redirected to http://localhost:8501 (it may show a Streamlit error page, that's fine)" -ForegroundColor White
Write-Host "  - Look at the address bar, it will look like:" -ForegroundColor White
Write-Host "    http://localhost:8501/?code=XXXXXXXX&state=" -ForegroundColor DarkGray
Write-Host "  - Copy ONLY the code value (the part after 'code=' and before '&state')" -ForegroundColor White
Write-Host ""

# Open browser automatically
Start-Process $authUrl

$authCode = Read-Host "  Paste the authorization code here"

Write-Step 4 "Exchanging code for Fitbit tokens..."

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

    Set-EnvValue "FITBIT_ACCESS_TOKEN"  $fitbitAccessToken
    Set-EnvValue "FITBIT_REFRESH_TOKEN" $fitbitRefreshToken

    Write-Host ""
    Write-Host "  ✅ Fitbit tokens obtained and saved!" -ForegroundColor Green
}
catch {
    Write-Host ""
    Write-Host "  ❌ Token exchange failed." -ForegroundColor Red
    Write-Host "     The authorization code may have expired (they last ~10 minutes)." -ForegroundColor Red
    Write-Host "     Re-run this script and complete the browser step quickly." -ForegroundColor Red
    exit 1
}

# ──────────────────────────────────────────────
#  DONE
# ──────────────────────────────────────────────

Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║   All credentials saved to .env  ✅          ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

# ── Token expiry summary ──────────────────────────────────────────────────────
Write-Host "  ⏱  Token Expiry Info" -ForegroundColor Cyan
Write-Host ""

# Strava access token expires in ~6h but its REFRESH token never expires
$stravaExpiresAt = (Get-Content $EnvFile | Select-String "^STRAVA_TOKEN_EXPIRES_AT=") -replace "^STRAVA_TOKEN_EXPIRES_AT=", ""
if ($stravaExpiresAt) {
    try {
        $stravaExpiry = [DateTimeOffset]::FromUnixTimeSeconds([long]$stravaExpiresAt).LocalDateTime
        Write-Host ("  🟠 Strava access token expires:  " + $stravaExpiry.ToString("dd MMM yyyy HH:mm 'local'")) -ForegroundColor DarkYellow
    } catch {}
}
Write-Host "     ↳ Strava REFRESH token: never expires (unless you revoke app access on Strava)" -ForegroundColor DarkGray

$fitbitExpiresAt = (Get-Content $EnvFile | Select-String "^FITBIT_TOKEN_EXPIRES_AT=") -replace "^FITBIT_TOKEN_EXPIRES_AT=", ""
if ($fitbitExpiresAt) {
    try {
        $fitbitExpiry = [DateTimeOffset]::FromUnixTimeSeconds([long]$fitbitExpiresAt).LocalDateTime
        Write-Host ("  🔵 Fitbit  access token expires:  " + $fitbitExpiry.ToString("dd MMM yyyy HH:mm 'local'")) -ForegroundColor DarkYellow
    } catch {}
}

# Fitbit refresh tokens expire if unused for 8 months, or after ~1 year
$fitbitRefreshExpiry = (Get-Date).AddMonths(8)
Write-Host ("     ↳ Fitbit REFRESH token:  valid ~8 months if used — expires around " + $fitbitRefreshExpiry.ToString("dd MMM yyyy")) -ForegroundColor DarkGray

Write-Host ""
Write-Host "  ℹ️  The app auto-refreshes access tokens while running." -ForegroundColor White
Write-Host "     You only need to re-run this script if:" -ForegroundColor White
Write-Host "     • You revoke app access on Strava or Fitbit" -ForegroundColor White
Write-Host "     • The Fitbit refresh token expires (~8 months idle)" -ForegroundColor White
Write-Host "     • You see persistent 401 errors even after an app restart" -ForegroundColor White
Write-Host ""
Write-Host "  Next: make sure Ollama is running, then start the app:" -ForegroundColor White
Write-Host "    ollama serve" -ForegroundColor DarkCyan
Write-Host "    streamlit run app.py" -ForegroundColor DarkCyan
Write-Host ""
