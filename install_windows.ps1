# SpotiToReko — Windows installer
# Run in PowerShell: Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
# Then: .\install_windows.ps1

$ErrorActionPreference = "Stop"

Write-Host "`nSpotiToReko — Windows Setup`n" -ForegroundColor White

# ── Python ─────────────────────────────────────────────────────────────────────
$python = $null
foreach ($candidate in @("python", "python3", "py")) {
    try {
        $ver = & $candidate --version 2>&1
        if ($ver -match "Python 3") {
            $python = $candidate
            Write-Host "✓ $ver" -ForegroundColor Green
            break
        }
    } catch {}
}

if (-not $python) {
    Write-Host "Python 3 not found. Installing via winget..." -ForegroundColor Yellow
    try {
        winget install --id Python.Python.3 -e --source winget
        $python = "python"
        Write-Host "✓ Python installed. Please restart this script." -ForegroundColor Green
        exit 0
    } catch {
        Write-Host "winget install failed. Download Python from https://www.python.org/downloads/" -ForegroundColor Red
        exit 1
    }
}

# ── yt-dlp ─────────────────────────────────────────────────────────────────────
$ytdlp = $null
try {
    $ytdlpVer = & yt-dlp --version 2>&1
    $ytdlp = "yt-dlp"
    Write-Host "✓ yt-dlp $ytdlpVer" -ForegroundColor Green
} catch {
    Write-Host "Installing yt-dlp..." -ForegroundColor Yellow
    & $python -m pip install --quiet yt-dlp
    Write-Host "✓ yt-dlp installed" -ForegroundColor Green
}

# ── Python packages ────────────────────────────────────────────────────────────
Write-Host "Installing Python packages..."
& $python -m pip install --quiet requests spotipy ytmusicapi mutagen
Write-Host "✓ Python packages installed" -ForegroundColor Green

# ── Done ───────────────────────────────────────────────────────────────────────
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "`nSetup complete!" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Edit config.json with your Spotify credentials"
Write-Host "  2. Run: $python `"$scriptDir\spotitoreko.py`""
Write-Host ""
