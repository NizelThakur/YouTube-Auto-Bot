# YouTube Auto Bot 🤖

Automated YouTube Shorts pipeline that generates horror/mythology stories, converts them to narrated videos, and uploads to YouTube — on autopilot.

## How It Works

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Generator   │ ──▶ │   Assembler  │ ──▶ │   Uploader  │
│              │     │              │     │             │
│ • Gemini AI  │     │ • ffmpeg     │     │ • YouTube   │
│   story gen  │     │ • Scale/crop │     │   Data API  │
│ • Edge-TTS   │     │ • Subtitles  │     │ • Duplicate │
│   audio      │     │ • Loop BG    │     │   detection │
│ • Pexels     │     │ • Merge      │     │             │
│   backgrounds│     │              │     │             │
└─────────────┘     └──────────────┘     └─────────────┘
```

## Quick Start

### Prerequisites

- Python 3.10+
- ffmpeg (installed and in PATH)

### Setup

```bash
# Clone
git clone https://github.com/NizelThakur/YouTube-Auto-Bot.git
cd YouTube-Auto-Bot

# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env with your actual keys
```

### Required API Keys

| Key | Purpose | Get it from |
|-----|---------|-------------|
| `GEMINI_API_KEY` | Story generation | [Google AI Studio](https://aistudio.google.com/apikey) |
| `PEXELS_API_KEY` | Background videos | [Pexels API](https://www.pexels.com/api/) |
| `ELEVENLABS_API_KEY` | Premium voice (optional) | [ElevenLabs](https://elevenlabs.io) |

> If no ElevenLabs key is set, the bot uses **Edge-TTS** (free, unlimited) automatically.

### YouTube OAuth Setup (first time only)

```bash
# This opens a browser for Google login
python main.py --profile mythology --dry-run
```

This creates `profiles/mythology/token.json` with your OAuth credentials.

## Usage

```bash
# Run a single profile
python main.py --profile mythology

# Run all profiles
python main.py --all

# Test without uploading
python main.py --profile mythology --dry-run
```

## Profile Configuration

Each profile lives in `profiles/<name>/` with a `config.json`:

```json
{
  "channel": {
    "niche": "Mythology & Horror",
    "language": "Hindi",
    "model": "gemini-2.5-flash"
  },
  "metadata": {
    "hashtag_count": 8,
    "tags": ["shorts", "horror", "hindi"]
  },
  "voice": {
    "elevenlabs_voice_id": "AZnzlk1Xhkbc9v3EByMW",
    "fallback_voices": ["hi-IN-MadhurNeural", "hi-IN-SwaraNeural"]
  },
  "video": {
    "subtitle_style": "Fontname=Liberation Sans,FontSize=18,...",
    "thumbnail_query": "ancient dark temple India mystical night"
  },
  "automation": {
    "privacy_status": "private"
  }
}
```

You can also place pre-downloaded background clips as `bg_0.mp4`, `bg_1.mp4`, etc. in the profile folder to skip Pexels API calls.

## GitHub Actions (Automated Daily Uploads)

The bot runs automatically at **09:00 IST** and **21:00 IST** via GitHub Actions.

### Required Secrets

Go to **Settings → Secrets and Variables → Actions** and add:

| Secret | Value |
|--------|-------|
| `GEMINI_API_KEY` | Your Gemini API key |
| `PEXELS_API_KEY` | Your Pexels API key |
| `ELEVENLABS_API_KEY` | Your ElevenLabs key (optional) |
| `YOUTUBE_CLIENT_SECRETS` | Contents of `client_secrets.json` |
| `YOUTUBE_TOKEN` | Contents of `profiles/<name>/token.json` |

### Manual Trigger

You can also trigger the workflow manually from the **Actions** tab → **YouTube Shorts Bot** → **Run workflow**.

## Scheduler (Alternative to GitHub Actions)

For local 24/7 operation:

```bash
python schedule_bot.py
# Runs at 09:00 and 21:00 daily — keep the terminal open
```

## Project Structure

```
├── main.py                 # CLI entry point
├── schedule_bot.py         # Local scheduler
├── requirements.txt
├── .env.example            # API key template
├── client_secrets.json     # YouTube OAuth client (git-ignored)
├── profiles/
│   └── mythology/
│       ├── config.json     # Profile configuration
│       ├── token.json      # YouTube OAuth token (git-ignored)
│       └── upload_history.json
└── src/bot/
    ├── pipeline.py         # Orchestrates the 3 stages
    ├── config.py           # Profile config loader
    ├── generator.py        # Story + audio + backgrounds
    ├── assembler.py        # ffmpeg video assembly
    └── uploader.py         # YouTube upload
```
