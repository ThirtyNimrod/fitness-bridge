# Usage:
#   .\scripts\manage.ps1 run
#   .\scripts\manage.ps1 stop
#   .\scripts\manage.ps1 restart

param([string]$Command = "run")

$PidFile    = Join-Path $PSScriptRoot "..\run.pid"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Start-App {
    $proc = Start-Process ".venv\Scripts\streamlit.exe" `
        -ArgumentList "run app.py" `
        -WorkingDirectory $ProjectRoot `
        -PassThru -NoNewWindow
    $proc.Id | Set-Content $PidFile
    Write-Host "✅ App started (PID $($proc.Id))"
}

function Stop-App {
    if (Test-Path $PidFile) {
        $storedPid = Get-Content $PidFile
        Stop-Process -Id $storedPid -Force -ErrorAction SilentlyContinue
        Remove-Item $PidFile
        Write-Host "🛑 App stopped (PID $storedPid)"
    } else {
        Write-Host "⚠️  No PID file found — app may not be running."
    }
}

switch ($Command) {
    "run"     { Start-App }
    "stop"    { Stop-App }
    "restart" { Stop-App; Start-App }
    default   { Write-Host "Usage: manage.ps1 [run|stop|restart]" }
}
