#!/usr/bin/env bash
# SpotiToReko — macOS installer
set -e

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
RESET='\033[0m'

echo -e "${BOLD}SpotiToReko — macOS Setup${RESET}\n"

# ── Python ─────────────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo -e "${YELLOW}Python 3 not found.${RESET}"
    if command -v brew &>/dev/null; then
        echo "Installing Python via Homebrew..."
        brew install python
    else
        echo -e "${RED}Homebrew not found.${RESET}"
        echo "Install Homebrew first: https://brew.sh"
        echo "Then re-run this script."
        exit 1
    fi
else
    echo -e "${GREEN}✓ Python $(python3 --version 2>&1 | cut -d' ' -f2)${RESET}"
fi

# ── yt-dlp ─────────────────────────────────────────────────────────────────────
if ! command -v yt-dlp &>/dev/null; then
    echo "Installing yt-dlp..."
    if command -v brew &>/dev/null; then
        brew install yt-dlp
    else
        python3 -m pip install --quiet yt-dlp
    fi
else
    echo -e "${GREEN}✓ yt-dlp $(yt-dlp --version)${RESET}"
fi

# ── Python packages ────────────────────────────────────────────────────────────
echo "Installing Python packages..."
python3 -m pip install --quiet requests spotipy ytmusicapi mutagen
echo -e "${GREEN}✓ Python packages installed${RESET}"

# ── Done ───────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo ""
echo -e "${BOLD}Setup complete!${RESET}"
echo ""
echo "Next steps:"
echo "  1. Edit config.json with your Spotify credentials"
echo "  2. Run: python3 \"${SCRIPT_DIR}/spotitoreko.py\""
echo ""
