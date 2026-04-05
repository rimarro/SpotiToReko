#!/usr/bin/env python3
"""
SpotiToReko — Spotify playlist → WAV downloader for Rekordbox
"""

import sys
import os
import re
import json
import shutil
import struct
import tempfile
import subprocess
from pathlib import Path
from difflib import SequenceMatcher

# ── ANSI colors ────────────────────────────────────────────────────────────────
# Enable ANSI on Windows (Windows 10+)
if os.name == "nt":
    os.system("")

GREEN  = "\033[92m"
YELLOW = "\033[93m"
GREY   = "\033[90m"
RED    = "\033[91m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

# ── Constants ──────────────────────────────────────────────────────────────────
VERSION_KEYWORDS = [
    "radio edit", "extended mix",
    "live", "remastered", "remix", "cover", "acoustic", "instrumental",
    "demo", "bootleg", "extended", "piano", "stripped", "concert",
    "unplugged", "tour edition", "deluxe",
]
SIMILARITY_THRESHOLD = 0.60
DURATION_TOLERANCE_S = 30
REQUIRED_PACKAGES = ["requests", "spotipy", "ytmusicapi", "mutagen"]

# Spotify key integer (0-11) × mode (0=minor, 1=major) → readable key name
KEY_NAMES = {
    (0, 1): "C",    (0, 0): "Cm",
    (1, 1): "C#",   (1, 0): "C#m",
    (2, 1): "D",    (2, 0): "Dm",
    (3, 1): "Eb",   (3, 0): "Ebm",
    (4, 1): "E",    (4, 0): "Em",
    (5, 1): "F",    (5, 0): "Fm",
    (6, 1): "F#",   (6, 0): "F#m",
    (7, 1): "G",    (7, 0): "Gm",
    (8, 1): "Ab",   (8, 0): "Abm",
    (9, 1): "A",    (9, 0): "Am",
    (10, 1): "Bb",  (10, 0): "Bbm",
    (11, 1): "B",   (11, 0): "Bm",
}

CONFIG_TEMPLATE = {
    "spotify_client_id": "PASTE_YOUR_CLIENT_ID_HERE",
    "spotify_client_secret": "PASTE_YOUR_CLIENT_SECRET_HERE",
    "playlist_id": "PASTE_YOUR_PLAYLIST_ID_HERE",
    "output_dir": str(Path.home() / "Music" / "SpotiToReko"),
}

SETUP_GUIDE = f"""
{BOLD}SpotiToReko — First-time setup{RESET}

config.json not found. A template has been created for you.

{BOLD}Steps:{RESET}
  1. Go to https://developer.spotify.com/dashboard
  2. Click "Create App", name it anything
  3. Set Redirect URI to: http://127.0.0.1:8080
  4. Copy your Client ID and Client Secret
  5. Open config.json next to this script and fill in the values
  6. Set playlist_id to the Spotify playlist ID you want to download
  7. Run this script again

"""


# ── Dependency checks ──────────────────────────────────────────────────────────

def check_python_version() -> None:
    if sys.version_info < (3, 8):
        print(f"{RED}Python 3.8 or higher is required.{RESET}")
        print(f"Current version: {sys.version}")
        print("Download Python from https://www.python.org/downloads/")
        sys.exit(1)


def check_and_install_packages() -> None:
    """Check for required pip packages and offer to install missing ones."""
    missing = []
    for package in REQUIRED_PACKAGES:
        # Map package install name to importable module name
        module = package.replace("-", "_")
        try:
            __import__(module)
        except ImportError:
            missing.append(package)

    if not missing:
        return

    print(f"{YELLOW}Missing Python packages: {', '.join(missing)}{RESET}")
    print("Installing now...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet"] + missing,
            check=True,
        )
        print(f"{GREEN}Packages installed. Please re-run the script.{RESET}")
    except subprocess.CalledProcessError:
        print(f"{RED}Auto-install failed. Run manually:{RESET}")
        print(f"  pip install {' '.join(missing)}")
    sys.exit(0)


def find_ytdlp() -> str:
    """Return the yt-dlp binary path, installing it via pip if not found."""
    for candidate in ["yt-dlp", "yt_dlp"]:
        path = shutil.which(candidate)
        if path:
            return path

    # Platform-specific known install locations
    extra_paths = [
        Path.home() / ".local" / "bin" / "yt-dlp",
        Path("/opt/homebrew/bin/yt-dlp"),
        Path("/usr/local/bin/yt-dlp"),
        Path(os.environ.get("APPDATA", "")) / "Python" / "Scripts" / "yt-dlp.exe",
    ]
    for p in extra_paths:
        if p.exists():
            return str(p)

    print(f"{YELLOW}yt-dlp not found. Installing via pip...{RESET}")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "yt-dlp"],
            check=True,
        )
        path = shutil.which("yt-dlp")
        if path:
            print(f"{GREEN}yt-dlp installed successfully.{RESET}")
            return path
        # Fall back to running as a Python module
        return f"{sys.executable} -m yt_dlp"
    except subprocess.CalledProcessError:
        print(f"{RED}Could not install yt-dlp automatically.{RESET}")
        if os.name == "nt":
            print("  Install with: winget install yt-dlp  or  pip install yt-dlp")
        else:
            print("  Install with: brew install yt-dlp  or  pip install yt-dlp")
        sys.exit(1)


# ── Config ─────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    config_path = Path(__file__).parent / "config.json"

    if not config_path.exists():
        print(SETUP_GUIDE)
        config_path.write_text(json.dumps(CONFIG_TEMPLATE, indent=2))
        print(f"  Created: {config_path}")
        sys.exit(0)

    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError as e:
        print(f"{RED}config.json is invalid JSON: {e}{RESET}")
        sys.exit(1)

    for key in ("spotify_client_id", "spotify_client_secret", "playlist_id"):
        val = config.get(key, "")
        if not val or "PASTE_YOUR" in val:
            print(f"{RED}Missing or unfilled '{key}' in config.json.{RESET}")
            print("Follow the setup guide and fill in your Spotify credentials.")
            sys.exit(1)

    config.setdefault("output_dir", str(Path.home() / "Music" / "SpotiToReko"))
    os.makedirs(config["output_dir"], exist_ok=True)
    return config


# ── Downloaded state ───────────────────────────────────────────────────────────

def load_downloaded(output_dir: str) -> dict:
    path = Path(output_dir) / "downloaded.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def save_downloaded(output_dir: str, data: dict) -> None:
    path = Path(output_dir) / "downloaded.json"
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, indent=2))
    os.replace(tmp_path, path)


# ── Spotify ────────────────────────────────────────────────────────────────────

def get_playlist_tracks(sp, playlist_id: str) -> list:
    tracks = []
    results = sp.playlist_tracks(playlist_id, limit=100, offset=0)

    while True:
        for item in results["items"]:
            t = item.get("track") or item.get("item")
            if not t or not t.get("id") or t.get("type") != "track":
                continue
            tracks.append(t)
        if results["next"] is None:
            break
        results = sp.next(results)

    # Batch-fetch artist genres (50 per request)
    artist_ids = list({a["id"] for t in tracks for a in t["artists"] if a.get("id")})
    genre_cache = {}
    try:
        import spotipy
        for i in range(0, len(artist_ids), 50):
            chunk = artist_ids[i:i + 50]
            for a in sp.artists(chunk)["artists"]:
                if a:
                    genre_cache[a["id"]] = a.get("genres", [])
    except spotipy.exceptions.SpotifyException:
        print(f"  {GREY}(Genre metadata unavailable — Spotify API restriction){RESET}")

    # Batch-fetch audio features: BPM and key (100 per request, non-fatal if restricted)
    track_ids = [t["id"] for t in tracks]
    audio_features_cache = {}
    try:
        for i in range(0, len(track_ids), 100):
            chunk = track_ids[i:i + 100]
            for af in (sp.audio_features(chunk) or []):
                if af and af.get("id"):
                    key_int = af.get("key", -1)
                    mode = af.get("mode", -1)
                    key_name = KEY_NAMES.get((key_int, mode), "") if key_int != -1 else ""
                    audio_features_cache[af["id"]] = {
                        "bpm": round(af.get("tempo", 0)) or 0,
                        "key": key_name,
                    }
    except Exception:
        print(f"  {GREY}(Audio features unavailable — Spotify API restriction){RESET}")

    normalized = []
    for t in tracks:
        artist_names = [a["name"] for a in t["artists"] if a.get("name")]
        first_artist_id = t["artists"][0].get("id") if t["artists"] else None
        genres = genre_cache.get(first_artist_id, [])
        album = t.get("album", {})
        release_date = album.get("release_date", "")
        year = release_date[:4] if release_date else ""
        images = album.get("images", [])
        cover_url = images[0]["url"] if images else ""
        track_num = str(t.get("track_number", ""))
        total_tracks = str(album.get("total_tracks", ""))
        track_number = f"{track_num}/{total_tracks}" if track_num and total_tracks else track_num
        af = audio_features_cache.get(t["id"], {})

        normalized.append({
            "id": t["id"],
            "title": t["name"],
            "artist": artist_names[0] if artist_names else "",
            "artists": ", ".join(artist_names),
            "album_artist": artist_names[0] if artist_names else "",
            "album": album.get("name", ""),
            "year": year,
            "track_number": track_number,
            "genres": genres,
            "duration_s": t.get("duration_ms", 0) // 1000,
            "cover_url": cover_url,
            "bpm": af.get("bpm", 0),
            "key": af.get("key", ""),
        })

    return normalized


# ── Matching ───────────────────────────────────────────────────────────────────

def normalize_for_matching(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\(?\bfeat\.?\s+[^)]+\)?", " ", s)
    s = re.sub(r"\(?\bft\.?\s+[^)]+\)?", " ", s)
    s = s.replace(" & ", " and ")
    s = re.sub(r"[^\w\s]", " ", s)
    return " ".join(s.split())


def score_match(spotify_track: dict, yt_result: dict) -> tuple:
    sp_title  = normalize_for_matching(spotify_track["title"])
    sp_artist = normalize_for_matching(spotify_track["artist"])
    yt_title  = normalize_for_matching(yt_result["title"])
    yt_artist = normalize_for_matching(yt_result.get("artist", ""))

    title_sim  = SequenceMatcher(None, sp_title, yt_title).ratio()
    artist_sim = SequenceMatcher(None, sp_artist, yt_artist).ratio()
    confidence = title_sim * 0.6 + artist_sim * 0.4

    sp_title_lower = spotify_track["title"].lower()
    yt_title_lower = yt_result["title"].lower()
    concerning = [kw for kw in VERSION_KEYWORDS if kw in yt_title_lower and kw not in sp_title_lower]

    sp_dur = spotify_track.get("duration_s", 0)
    yt_dur = yt_result.get("duration_seconds", sp_dur)
    if sp_dur and yt_dur and abs(sp_dur - yt_dur) > DURATION_TOLERANCE_S:
        concerning.append(f"duration mismatch ({sp_dur}s vs {yt_dur}s)")

    return confidence, concerning


# ── YouTube Music search ───────────────────────────────────────────────────────

def search_youtube_music(track: dict, ytm) -> list:
    query = f"{track['title']} {track['artist']}"
    try:
        results = ytm.search(query, filter="songs", limit=5)
    except Exception as e:
        print(f"  {YELLOW}YouTube Music search error: {e}{RESET}")
        return []

    candidates = []
    for r in (results or [])[:5]:
        video_id = r.get("videoId")
        if not video_id:
            continue
        artists = r.get("artists") or []
        artist_str = ", ".join(a["name"] for a in artists if a.get("name"))
        album_name = (r.get("album") or {}).get("name", "")
        candidates.append({
            "title": r.get("title", ""),
            "artist": artist_str,
            "album": album_name,
            "duration": r.get("duration") or "?:??",
            "duration_seconds": r.get("duration_seconds") or 0,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "video_id": video_id,
        })
        if len(candidates) == 3:
            break

    return candidates


# ── User prompt ────────────────────────────────────────────────────────────────

def prompt_user_for_match(spotify_track: dict, candidates: list):
    dur = spotify_track.get("duration_s", 0)
    dur_str = f"{dur // 60}:{dur % 60:02d}" if dur else "?:??"
    print(f"\n  {YELLOW}? Needs confirmation:{RESET}")
    print(f"    Spotify: {BOLD}{spotify_track['title']}{RESET} — {spotify_track['artist']}")
    print(f"             {spotify_track['album']} ({spotify_track['year']}) [{dur_str}]")

    if not candidates:
        print(f"  {RED}No YouTube Music results found.{RESET}")
        print("  Enter a YouTube URL manually, or press Enter to skip:")
        url = input("  > ").strip()
        return url if url else None

    print(f"\n  YouTube Music matches:")
    for i, c in enumerate(candidates, 1):
        conf, kws = score_match(spotify_track, c)
        flags = f"  {RED}[{', '.join(kws)}]{RESET}" if kws else ""
        print(f"  [{i}] {c['title']} — {c['artist']} ({c['duration']})  {conf:.0%} match{flags}")

    print(f"\n  [0] Skip this track")
    print(f"  Enter 1-{len(candidates)}, 0 to skip, a YouTube URL, or press Enter for [1]:")

    while True:
        choice = input("  > ").strip()
        if choice in ("", "1"):
            return candidates[0]["url"]
        if choice == "0":
            return None
        if choice in ("2", "3"):
            idx = int(choice) - 1
            if idx < len(candidates):
                return candidates[idx]["url"]
        if choice.startswith("http"):
            return choice
        print(f"  Invalid choice. Enter 1-{len(candidates)}, 0, or a URL:")


# ── Filename sanitization ──────────────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    name = name.replace("/", "-").replace("\\", "-")
    name = name.replace("\x00", "").replace(":", " -")
    # Windows reserved characters
    if os.name == "nt":
        for ch in r'<>"|?*':
            name = name.replace(ch, "")
    name = name.strip(". ")
    encoded = name.encode("utf-8")
    if len(encoded) > 200:
        name = encoded[:200].decode("utf-8", errors="ignore").strip()
    return name


# ── Metadata ───────────────────────────────────────────────────────────────────

def _riff_chunk(tag: bytes, data: bytes) -> bytes:
    """Pack a RIFF sub-chunk with even-length padding."""
    if len(data) % 2:
        data += b"\x00"
    return tag + struct.pack("<I", len(data)) + data


def write_riff_info(filepath: Path, track: dict) -> None:
    """Write a RIFF LIST INFO chunk into a WAV file.

    This is the native WAV metadata format — reliably read by Rekordbox,
    DAWs, and audio software that ignores ID3 chunks in WAV files.
    """
    fields = [
        (b"INAM", track.get("title", "")),
        (b"IART", track.get("artists") or track.get("artist", "")),
        (b"IPRD", track.get("album", "")),
        (b"ICRD", track.get("year", "")),
        (b"IGNR", track["genres"][0] if track.get("genres") else ""),
        (b"ITRK", (track.get("track_number") or "").split("/")[0]),
        (b"ICMT", "Downloaded by SpotiToReko"),
    ]
    if track.get("bpm"):
        fields.append((b"IBPM", str(track["bpm"])))
    if track.get("key"):
        fields.append((b"IKEY", track["key"]))

    info_data = b"INFO"
    for tag, value in fields:
        if value:
            info_data += _riff_chunk(tag, value.encode("utf-8") + b"\x00")

    list_chunk = _riff_chunk(b"LIST", info_data)

    data = filepath.read_bytes()
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return

    # Rebuild the file, stripping any existing LIST INFO chunk
    rebuilt = data[:12]
    pos = 12
    while pos + 8 <= len(data):
        chunk_id = data[pos:pos + 4]
        chunk_size = struct.unpack("<I", data[pos + 4:pos + 8])[0]
        padded = chunk_size + (chunk_size % 2)
        end = pos + 8 + padded
        if chunk_id == b"LIST" and data[pos + 8:pos + 12] == b"INFO":
            pos = end
            continue
        rebuilt += data[pos:end]
        pos = end

    rebuilt += list_chunk
    # Update the top-level RIFF size field
    rebuilt = rebuilt[:4] + struct.pack("<I", len(rebuilt) - 8) + rebuilt[8:]
    filepath.write_bytes(rebuilt)


def write_metadata(filepath: Path, track: dict) -> bool:
    try:
        import requests as req
        from mutagen.wave import WAVE
        from mutagen.id3 import (
            TIT2, TPE1, TPE2, TALB, TDRC, TRCK, TCON, TBPM, TKEY, APIC, COMM,
        )

        audio = WAVE(str(filepath))
        if audio.tags is None:
            audio.add_tags()

        tags = audio.tags
        tags["TIT2"] = TIT2(encoding=3, text=[track["title"]])
        tags["TPE1"] = TPE1(encoding=3, text=[track["artists"]])
        tags["TPE2"] = TPE2(encoding=3, text=[track["album_artist"]])
        tags["TALB"] = TALB(encoding=3, text=[track["album"]])
        if track.get("year"):
            tags["TDRC"] = TDRC(encoding=3, text=[track["year"]])
        if track.get("track_number"):
            tags["TRCK"] = TRCK(encoding=3, text=[track["track_number"]])
        if track.get("genres"):
            tags["TCON"] = TCON(encoding=3, text=[track["genres"][0]])
        if track.get("bpm"):
            tags["TBPM"] = TBPM(encoding=3, text=[str(track["bpm"])])
        if track.get("key"):
            tags["TKEY"] = TKEY(encoding=3, text=[track["key"]])
        tags["COMM"] = COMM(encoding=3, lang="eng", desc="", text=["Downloaded by SpotiToReko"])

        if track.get("cover_url"):
            try:
                resp = req.get(track["cover_url"], timeout=10)
                resp.raise_for_status()
                mime = "image/png" if "png" in resp.headers.get("Content-Type", "") else "image/jpeg"
                tags["APIC"] = APIC(encoding=3, mime=mime, type=3, desc="Cover", data=resp.content)
            except Exception as e:
                print(f"  {GREY}Cover art failed: {e}{RESET}")

        # ID3v2.3 has broader compatibility with Rekordbox than the default v2.4
        audio.save(v2_version=3)

        # Also write native RIFF INFO chunk — read by Rekordbox and most DAWs
        write_riff_info(filepath, track)

        return True

    except Exception as e:
        print(f"  {RED}Metadata write failed: {e}{RESET}")
        return False


def needs_metadata(filepath: Path) -> bool:
    """Return True if the WAV file is missing a RIFF LIST INFO chunk with a title."""
    try:
        data = filepath.read_bytes()
        if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
            return False
        pos = 12
        while pos + 8 <= len(data):
            chunk_id = data[pos:pos + 4]
            chunk_size = struct.unpack("<I", data[pos + 4:pos + 8])[0]
            if chunk_id == b"LIST" and data[pos + 8:pos + 12] == b"INFO":
                return b"INAM" not in data[pos + 12:pos + 8 + chunk_size]
            pos += 8 + chunk_size + (chunk_size % 2)
        return True  # No LIST INFO chunk found
    except Exception:
        return False


# ── Download ───────────────────────────────────────────────────────────────────

def download_track(yt_url: str, track: dict, output_dir: str, ytdlp_bin: str) -> Path:
    tmpdir = Path(tempfile.mkdtemp(prefix="spotitoreko_"))
    try:
        # Support "python -m yt_dlp" fallback
        if " " in ytdlp_bin:
            cmd = ytdlp_bin.split()
        else:
            cmd = [ytdlp_bin]

        cmd += [
            "-x", "--audio-format", "wav",
            "--audio-quality", "0",
            "--no-playlist",
            "--no-part",
            "--quiet", "--no-warnings",
            "-o", str(tmpdir / "%(id)s.%(ext)s"),
            yt_url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"  {RED}yt-dlp error: {result.stderr.strip()[:300]}{RESET}")
            return None

        wav_files = list(tmpdir.glob("*.wav"))
        if not wav_files:
            print(f"  {RED}No WAV produced by yt-dlp{RESET}")
            return None

        tmp_wav = wav_files[0]
        if not write_metadata(tmp_wav, track):
            return None

        title_safe  = sanitize_filename(track["title"])
        artist_safe = sanitize_filename(track["artist"])
        final_name  = f"{title_safe} - {artist_safe}.wav"
        final_path  = Path(output_dir) / final_name

        if final_path.exists():
            stem = f"{title_safe} - {artist_safe} ({track['id'][:8]})"
            final_path = Path(output_dir) / f"{stem}.wav"

        shutil.move(str(tmp_wav), str(final_path))
        return final_path

    except subprocess.TimeoutExpired:
        print(f"  {RED}Download timed out (5 min){RESET}")
        return None
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    check_python_version()
    check_and_install_packages()

    # Deferred imports (guaranteed present after check above)
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    from ytmusicapi import YTMusic

    config = load_config()
    output_dir = config["output_dir"]

    print(f"\n{BOLD}SpotiToReko{RESET} — Spotify → WAV Downloader")
    print(f"Output: {output_dir}\n")

    ytdlp_bin = find_ytdlp()

    cache_path = Path(__file__).parent / ".spotify_cache"
    auth_manager = SpotifyOAuth(
        client_id=config["spotify_client_id"],
        client_secret=config["spotify_client_secret"],
        redirect_uri="http://127.0.0.1:8080",
        scope="playlist-read-private playlist-read-collaborative",
        cache_path=str(cache_path),
        open_browser=True,
    )
    sp = spotipy.Spotify(auth_manager=auth_manager)
    ytm = YTMusic()

    downloaded = load_downloaded(output_dir)
    print("  Loading playlist...", end=" ", flush=True)
    try:
        tracks = get_playlist_tracks(sp, config["playlist_id"])
    except spotipy.exceptions.SpotifyException as e:
        print(f"\n{RED}Spotify error: {e}{RESET}")
        print("Check your Client ID and Secret in config.json.")
        sys.exit(1)

    print(f"{len(tracks)} tracks ({len(downloaded)} already downloaded)\n")

    count_downloaded = 0
    count_patched = 0
    count_skipped = 0
    count_prompted = 0
    count_failed = 0

    try:
        for i, track in enumerate(tracks, 1):
            track_id = track["id"]
            label = f"{track['artist']} - {track['title']}"
            print(f"[{i}/{len(tracks)}] {BOLD}{label}{RESET}")

            if track_id in downloaded:
                filename = downloaded[track_id]
                filepath = Path(output_dir) / filename

                if not filepath.exists():
                    # File was deleted or moved — remove from log and re-download
                    print(f"  {YELLOW}File missing from disk, re-downloading...{RESET}")
                    del downloaded[track_id]
                    save_downloaded(output_dir, downloaded)
                    # fall through to download logic below

                elif needs_metadata(filepath):
                    print(f"  {YELLOW}~ Patching metadata...{RESET}", end=" ", flush=True)
                    if write_metadata(filepath, track):
                        print(f"{GREEN}done{RESET}")
                        count_patched += 1
                    else:
                        count_failed += 1
                    continue

                else:
                    print(f"  {GREY}- Already downloaded: {filename}{RESET}")
                    count_skipped += 1
                    continue

            candidates = search_youtube_music(track, ytm)

            if candidates:
                confidence, keywords = score_match(track, candidates[0])
                should_ask = bool(keywords) or confidence < SIMILARITY_THRESHOLD
            else:
                confidence, keywords = 0.0, []
                should_ask = True

            if should_ask:
                count_prompted += 1
                chosen_url = prompt_user_for_match(track, candidates)
                if chosen_url is None:
                    print(f"  {GREY}- Skipped by user{RESET}")
                    count_skipped += 1
                    continue
            else:
                chosen_url = candidates[0]["url"]
                print(f"  Auto: {candidates[0]['title']} ({confidence:.0%})")

            print("  Downloading...", end=" ", flush=True)
            final_path = download_track(chosen_url, track, output_dir, ytdlp_bin)

            if final_path:
                downloaded[track_id] = final_path.name
                save_downloaded(output_dir, downloaded)
                marker = YELLOW if should_ask else GREEN
                symbol = "?" if should_ask else "v"
                print(f"  {marker}{symbol} {final_path.name}{RESET}")
                count_downloaded += 1
            else:
                print(f"  {RED}x Failed{RESET}")
                count_failed += 1

    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Interrupted. Progress saved.{RESET}")

    print(f"\n{'─' * 50}")
    print(f"  {GREEN}v Downloaded:  {count_downloaded}{RESET}")
    print(f"  {YELLOW}~ Patched:     {count_patched}{RESET}")
    print(f"  {YELLOW}? Prompted:    {count_prompted}{RESET}")
    print(f"  {GREY}- Skipped:     {count_skipped}{RESET}")
    print(f"  {RED}x Failed:      {count_failed}{RESET}")
    print()


if __name__ == "__main__":
    main()
