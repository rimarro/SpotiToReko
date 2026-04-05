# SpotiToReko

Download your Spotify playlists as high-quality WAV files with full metadata, ready to import into Rekordbox.

It searches YouTube Music for each track, auto-matches high-confidence results, and prompts you to confirm anything ambiguous. Files are tagged with title, artist, album, cover art, and genre.

---

## Download & Install

### macOS

[![Download for macOS](https://img.shields.io/badge/Download-macOS_Installer-000000?style=for-the-badge&logo=apple)](https://raw.githubusercontent.com/rimarro/SpotiToReko/main/install_mac.sh)

```bash
# After downloading, make it executable and run:
chmod +x install_mac.sh
./install_mac.sh
```

### Windows

[![Download for Windows](https://img.shields.io/badge/Download-Windows_Installer-0078D4?style=for-the-badge&logo=windows)](https://raw.githubusercontent.com/rimarro/SpotiToReko/main/install_windows.ps1)

```powershell
# In PowerShell (run as Administrator if needed):
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
.\install_windows.ps1
```

The installers handle Python, yt-dlp, and all required packages automatically.

---

## Requirements

- Python 3.8+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- A [Spotify Developer App](https://developer.spotify.com/dashboard) (free)

Python packages (auto-installed):
```
requests  spotipy  ytmusicapi  mutagen
```

---

## Setup

### 1. Get Spotify credentials

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Click **Create App** — name it anything
3. Set **Redirect URI** to `http://127.0.0.1:8080`
4. Copy your **Client ID** and **Client Secret**

### 2. Configure

Run the script once to generate a `config.json` template:

```bash
python3 spotitoreko.py
```

Then fill in your credentials:

```json
{
  "spotify_client_id": "your_client_id",
  "spotify_client_secret": "your_client_secret",
  "playlist_id": "your_playlist_id",
  "output_dir": "/path/to/output"
}
```

To find a playlist ID: open the playlist in Spotify → Share → Copy link. The ID is the string after `/playlist/` and before `?`.

### 3. Run

```bash
python3 spotitoreko.py
```

A browser window will open for Spotify auth on the first run. After that, tokens are cached automatically.

---

## How it works

1. Fetches all tracks from your Spotify playlist (including genres and cover art)
2. Searches YouTube Music for each track
3. Scores matches by title/artist similarity and duration
4. Auto-downloads high-confidence matches; prompts you for anything uncertain
5. Downloads as WAV via yt-dlp and writes ID3 tags with mutagen
6. Saves a `downloaded.json` log — already-downloaded tracks are skipped on re-runs

---

## Output

Files are saved as:
```
Track Title - Artist Name.wav
```

With the following tags: Title, Artist, Album Artist, Album, Year, Track Number, Genre, Cover Art, Comment.

---

## License

MIT
