##################################################################
#  Fitness Bridge AI — Strava Token Refresh Script
#  Run this when Strava gives persistent 401 errors.
#  Reads your existing STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET
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
Write-Host "║   Fitness Bridge AI — Strava Token Refresh   ║" -ForegroundColor Yellow
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Yellow

# ──────────────────────────────────────────────────────────────
#  Step 1 — Load or prompt for credentials
# ──────────────────────────────────────────────────────────────

Write-Step 1 "Loading Strava credentials from .env"

$stravaClientId     = Get-EnvValue "STRAVA_CLIENT_ID"
$stravaClientSecret = Get-EnvValue "STRAVA_CLIENT_SECRET"

if ($stravaClientId -and $stravaClientSecret) {
    Write-Host ""
    Write-Host "  ✅ Found STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET in .env" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "  ⚠️  Credentials not found in .env — please enter them now." -ForegroundColor DarkYellow
    Write-Host "     (Find them at https://www.strava.com/settings/api)" -ForegroundColor White
    Write-Host ""
    if (-not $stravaClientId) {
        $stravaClientId = Read-Host "  Paste your Strava CLIENT ID"
        Set-EnvValue "STRAVA_CLIENT_ID" $stravaClientId
    }
    if (-not $stravaClientSecret) {
        $stravaClientSecret = Read-Host "  Paste your Strava CLIENT SECRET"
        Set-EnvValue "STRAVA_CLIENT_SECRET" $stravaClientSecret
    }
}

# ──────────────────────────────────────────────────────────────
#  Step 2 — OAuth authorization
# ──────────────────────────────────────────────────────────────

Write-Step 2 "Strava OAuth Authorization"

$stravaScopes  = "read,activity:read_all"
$stravaAuthUrl = "https://www.strava.com/oauth/authorize?client_id=${stravaClientId}&response_type=code&redirect_uri=http://localhost/exchange_token&approval_prompt=force&scope=${stravaScopes}"

Write-Host ""
Write-Host "  Opening Strava authorization in your browser..." -ForegroundColor White
Write-Host ""
Write-Host "  After you click 'Authorize':" -ForegroundColor White
Write-Host "  • You'll be redirected to a localhost URL that says 'Site can't be reached'" -ForegroundColor White
Write-Host "  • Look at the address bar for the code:" -ForegroundColor White
Write-Host "    http://localhost/exchange_token?state=&code=XXXXXXXX&scope=..." -ForegroundColor DarkGray
Write-Host "  • Copy ONLY the part between 'code=' and '&scope='" -ForegroundColor White
Write-Host ""

Start-Process $stravaAuthUrl
$stravaAuthCode = Read-Host "  Paste the Strava authorization code here"

# ──────────────────────────────────────────────────────────────
#  Step 3 — Exchange code for tokens
# ──────────────────────────────────────────────────────────────

Write-Step 3 "Exchanging code for new Strava tokens..."

try {
    $pythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $pythonExe)) {
        $pythonExe = "python"  # fall back to system Python
    }

    $pyScript = @"
import urllib.request, urllib.parse, json, sys
data = urllib.parse.urlencode({
    'client_id': '$stravaClientId',
    'client_secret': '$stravaClientSecret',
    'code': '$stravaAuthCode',
    'grant_type': 'authorization_code'
}).encode()
req = urllib.request.Request('https://www.strava.com/api/v3/oauth/token', data=data, method='POST')
try:
    with urllib.request.urlopen(req) as r:
        body = json.load(r)
    print(body['refresh_token'])
    print(body['access_token'])
    print(body.get('expires_at', ''))
except Exception as e:
    print(f'ERROR:{e}', file=sys.stderr)
    sys.exit(1)
"@

    $output = & $pythonExe -c $pyScript 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Python token exchange failed: $output" }

    $lines              = $output -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    $stravaRefreshToken = $lines[0]
    $stravaAccessToken  = $lines[1]
    $stravaExpiresAt    = $lines[2]

    if (-not $stravaRefreshToken) { throw "Empty refresh token returned" }

    Set-EnvValue "STRAVA_REFRESH_TOKEN" $stravaRefreshToken
    if ($stravaAccessToken)  { Set-EnvValue "STRAVA_ACCESS_TOKEN"    $stravaAccessToken  }
    if ($stravaExpiresAt)    { Set-EnvValue "STRAVA_TOKEN_EXPIRES_AT" $stravaExpiresAt   }

    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║   Strava tokens refreshed successfully  ✅   ║" -ForegroundColor Green
    Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Variables updated in .env:" -ForegroundColor White
    Write-Host "    STRAVA_REFRESH_TOKEN    ✅  (never expires unless revoked)" -ForegroundColor Green
    Write-Host "    STRAVA_ACCESS_TOKEN     ✅" -ForegroundColor Green

    if ($stravaExpiresAt) {
        try {
            $expiry = [DateTimeOffset]::FromUnixTimeSeconds([long]$stravaExpiresAt).LocalDateTime
            Write-Host ("    STRAVA_TOKEN_EXPIRES_AT  ✅  (access token valid until " + $expiry.ToString("dd MMM yyyy HH:mm 'local'") + ")") -ForegroundColor Green
        } catch {
            Write-Host "    STRAVA_TOKEN_EXPIRES_AT  ✅" -ForegroundColor Green
        }
    }

    Write-Host ""
    Write-Host "  ℹ️  The app auto-refreshes the access token while running." -ForegroundColor White
    Write-Host "     Only re-run this script if you revoke access on Strava" -ForegroundColor White
    Write-Host "     or see persistent 401 errors after restarting the app." -ForegroundColor White
    Write-Host ""
    Write-Host "  Restart Streamlit to apply the new tokens:" -ForegroundColor White
    Write-Host "    streamlit run app.py" -ForegroundColor DarkCyan
    Write-Host ""
}
catch {
    Write-Host ""
    Write-Host "  ❌ Strava token exchange failed." -ForegroundColor Red
    Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Tips:" -ForegroundColor DarkYellow
    Write-Host "  • The auth code expires in ~30 seconds — paste it quickly." -ForegroundColor DarkYellow
    Write-Host "  • Make sure you copied only the code= value, not the full URL." -ForegroundColor DarkYellow
    Write-Host "  • Check STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET are correct." -ForegroundColor DarkYellow
    Write-Host ""
    exit 1
}
