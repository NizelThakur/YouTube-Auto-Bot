import json
import os
import random
import subprocess
import sys
import time
import re

import requests


class Generator:
    def __init__(self, config, build_dir: str):
        self.cfg = config
        self.build_dir = build_dir

    # ------------------------------------------------------------------ #
    #  STORY GENERATION
    # ------------------------------------------------------------------ #

    def generate_story(self) -> dict:
        niche = self.cfg.get("channel", "niche", default="Mythology Horror")
        lang = self.cfg.get("channel", "language", default="Hindi")
        hashtag_count = self.cfg.get("metadata", "hashtag_count", default=8)

        # Fail fast if no API key
        key = self.cfg.api_key("gemini")
        if not key:
            raise Exception(
                "GEMINI_API_KEY is not set! "
                "Add it to your .env file (local) or GitHub Secrets (CI)."
            )

        print(f"  Generating {lang} story for '{niche}'...")

        prompt = (
            f"You are a master {lang} horror storyteller writing YouTube Shorts scripts.\n\n"
            f"Write a 50 to 55 second horror mythology YouTube Shorts script for a '{niche}' channel.\n"
            f"TARGET LENGTH: 120-140 words maximum (spoken at natural pace = 50-55 seconds).\n"
            f"LANGUAGE: {lang} — simple conversational language, easy for mass audience.\n\n"
            f"TOPIC: haunted hospital / cursed ancient temple / ghost encounter / Indian mythology horror\n\n"
            f"STYLE RULES:\n"
            f"- First sentence must be shocking/eerie (the hook)\n"
            f"- Feels like a TRUE incident (first or close third person)\n"
            f"- At least 2 clear suspense moments\n"
            f"- Shocking twist ending in last 20 seconds\n"
            f"- Insert [PAUSE] at dramatic moments (minimum 8 times)\n"
            f"- End with a chilling final line\n\n"
            f"STRUCTURE (use these exact labels):\n"
            f"[HOOK - 0 to 3s]\n"
            f"[SETUP - 3 to 15s]\n"
            f"[SUSPENSE - 15 to 40s]\n"
            f"[CLIMAX - 40 to 50s]\n"
            f"[TWIST - last 10s]\n\n"
            f"Return ONLY valid raw JSON (no markdown, no code fences):\n"
            f'{{"story": "<full narration with [PAUSE] tags and section labels>", '
            f'"keywords": ["<10 specific English Pexels search terms e.g. abandoned hospital corridor night>"], '
            f'"title": "<EXTREMELY viral & clickable {lang} title with 2 emojis, highlighting curiosity gap>", '
            f'"description": "<High-retention {lang} hook description + {hashtag_count} CURRENT TRENDING VIRAL hashtags (do NOT just use generic tags, find hyper-relevant viral tags)>"}}'
        )

        # Try primary model, then fallback.
        # gemini-2.0-flash has very high free-tier quota → best fallback.
        models_to_try = [
            self.cfg.get("channel", "model", default="gemini-2.5-flash"),
            "gemini-2.0-flash",
        ]

        last_error = None
        for model_idx, model in enumerate(models_to_try):
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={key}"
            )
            if model_idx > 0:
                print(f"  Switching to fallback model: {model}")

            for attempt in range(3):
                try:
                    # Initial delay to avoid rate limits on GitHub Actions
                    if attempt == 0 and os.getenv("GITHUB_ACTIONS"):
                        wait = random.randint(15, 30)
                        print(f"  Waiting {wait}s (rate limit buffer)...")
                        time.sleep(wait)

                    resp = requests.post(
                        url,
                        headers={"Content-Type": "application/json"},
                        json={"contents": [{"parts": [{"text": prompt}]}]},
                        timeout=90,
                    )

                    # On 429, wait longer and retry
                    if resp.status_code == 429:
                        wait = 60 * (attempt + 1)
                        print(f"  429 Rate Limited — waiting {wait}s before retry...")
                        time.sleep(wait)
                        last_error = Exception(f"429 rate limit on {model}")
                        continue

                    resp.raise_for_status()
                    raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                    raw = raw.replace("```json", "").replace("```", "").strip()
                    data = json.loads(raw)

                    # Basic validation
                    story = data.get("story", "")
                    if len(story.split()) < 50:
                        raise ValueError(f"Story too short ({len(story.split())} words)")
                    if len(story.split()) > 200:
                        print(f"  Warning: Story slightly long ({len(story.split())} words), continuing anyway.")

                    print(f"  Story generated with {model} ({len(story.split())} words).")
                    return data

                except Exception as e:
                    last_error = e
                    print(f"  {model} attempt {attempt + 1}/3 failed: {e}")
                    if "429" in str(e):
                        # Quota exhausted — try fallback model
                        break
                    if attempt < 2:
                        time.sleep(30)

        raise Exception(f"Story generation failed on all models: {last_error}")

    # ------------------------------------------------------------------ #
    #  AUDIO GENERATION
    # ------------------------------------------------------------------ #

    def generate_audio(self, story: str):
        audio_path = os.path.join(self.build_dir, "audio.mp3")
        vtt_path = os.path.join(self.build_dir, "subtitles.vtt")

        # Clean text for TTS — order matters:
        # 1. Replace [PAUSE] with ellipsis (preserves dramatic pacing)
        # 2. Strip all remaining [BRACKETED] labels (section markers etc.)
        # 3. Collapse whitespace
        clean = story.replace("[PAUSE]", "...")
        clean = re.sub(r'\[.*?\]', '', clean)
        clean = " ".join(clean.split())

        if not clean.strip():
            raise Exception("Story text is empty after cleaning!")

        el_key = self.cfg.api_key("elevenlabs")
        voice_id = self.cfg.get("voice", "elevenlabs_voice_id", default="AZnzlk1Xhkbc9v3EByMW")
        fallback_voices = self.cfg.get("voice", "fallback_voices", default=["hi-IN-MadhurNeural"])

        if el_key:
            try:
                print("  Generating audio with ElevenLabs...")
                from elevenlabs.client import ElevenLabs

                client = ElevenLabs(api_key=el_key)
                audio_gen = client.text_to_speech.convert(
                    text=clean,
                    voice_id=voice_id,
                    model_id="eleven_multilingual_v2",
                )
                # audio_gen is a generator — collect bytes and write to file
                with open(audio_path, "wb") as af:
                    for chunk in audio_gen:
                        af.write(chunk)
                print("  ElevenLabs audio saved.")

                # Generate VTT subtitle file via edge-tts (for timing reference)
                print("  Generating subtitle timing with Edge-TTS...")
                dummy = os.path.join(self.build_dir, "_dummy_audio.mp3")
                subprocess.run(
                    [sys.executable, "-m", "edge_tts",
                     "--voice", fallback_voices[0],
                     "--text", clean,
                     "--write-media", dummy,
                     "--write-subtitles", vtt_path],
                    check=True, capture_output=True
                )
                if os.path.exists(dummy):
                    os.remove(dummy)
                print("  Subtitles generated.")
                return

            except Exception as e:
                print(f"  ElevenLabs failed: {e}. Falling back to Edge-TTS...")

        # Edge-TTS fallback (audio + subtitles in one shot)
        voice = random.choice(fallback_voices)
        print(f"  Generating audio with Edge-TTS ({voice})...")
        subprocess.run(
            [sys.executable, "-m", "edge_tts",
             "--voice", voice,
             "--text", clean,
             "--write-media", audio_path,
             "--write-subtitles", vtt_path],
            check=True
        )
        print("  Edge-TTS audio and subtitles saved.")

    # ------------------------------------------------------------------ #
    #  BACKGROUND VIDEOS
    # ------------------------------------------------------------------ #

    def fetch_backgrounds(self, keywords: list):
        import shutil

        # Use pre-existing backgrounds from profile folder if available
        try:
            profile_bgs = sorted([
                f for f in os.listdir(self.cfg.profile_dir)
                if f.startswith("bg_") and f.endswith(".mp4")
            ])
        except FileNotFoundError:
            profile_bgs = []

        if profile_bgs:
            print(f"  Using {len(profile_bgs)} pre-downloaded background clips...")
            for f in profile_bgs:
                shutil.copy(os.path.join(self.cfg.profile_dir, f),
                            os.path.join(self.build_dir, f))
            return

        pexels_key = self.cfg.api_key("pexels")
        if not pexels_key:
            raise Exception(
                "No Pexels API key configured and no pre-existing bg videos!\n"
                "Either add PEXELS_API_KEY to .env / GitHub Secrets,\n"
                "or place bg_0.mp4, bg_1.mp4, ... in your profile folder."
            )

        print(f"  Downloading background clips from Pexels...")
        headers = {"Authorization": pexels_key}
        count = 0

        for i, keyword in enumerate(keywords[:8]):
            try:
                resp = requests.get(
                    "https://api.pexels.com/videos/search",
                    headers=headers,
                    params={"query": keyword, "orientation": "portrait",
                            "size": "medium", "per_page": 3},
                    timeout=20,
                )
                resp.raise_for_status()
                videos = resp.json().get("videos", [])
                if not videos:
                    continue

                # Pick a random video from results
                video = random.choice(videos)
                # Prefer HD file
                files = sorted(video["video_files"], key=lambda x: x.get("width", 0), reverse=True)
                url = files[0]["link"]

                out_path = os.path.join(self.build_dir, f"bg_{count}.mp4")
                with open(out_path, "wb") as f:
                    for chunk in requests.get(url, stream=True, timeout=60).iter_content(8192):
                        f.write(chunk)
                count += 1
                print(f"    bg_{count-1}.mp4 ← '{keyword}'")
                time.sleep(0.5)  # Rate limit courtesy

            except Exception as e:
                print(f"    Failed '{keyword}': {e}")

        if count == 0:
            raise Exception("No background videos could be downloaded from Pexels!")

        # Download thumbnail image
        try:
            thumb_q = self.cfg.get("video", "thumbnail_query", default="dark ancient temple")
            resp = requests.get(
                "https://api.pexels.com/v1/search",
                headers=headers,
                params={"query": thumb_q, "orientation": "portrait", "per_page": 3},
                timeout=20,
            )
            resp.raise_for_status()
            photos = resp.json().get("photos", [])
            if photos:
                img = requests.get(random.choice(photos)["src"]["large"], timeout=30).content
                with open(os.path.join(self.build_dir, "thumbnail.jpg"), "wb") as f:
                    f.write(img)
                print(f"  Thumbnail saved.")
        except Exception as e:
            print(f"  Thumbnail fetch failed (non-critical): {e}")

    # ------------------------------------------------------------------ #
    #  ENTRY POINT
    # ------------------------------------------------------------------ #

    def run(self) -> dict:
        print("--- [1/3] GENERATION ---")
        content = self.generate_story()

        # Save metadata for uploader
        with open(os.path.join(self.build_dir, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump({
                "title": content["title"],
                "description": content["description"],
            }, f, indent=2, ensure_ascii=False)

        self.generate_audio(content["story"])
        self.fetch_backgrounds(content.get("keywords", ["dark ancient ruins night"]))

        print("[1/3] Generation complete.\n")
        return content
