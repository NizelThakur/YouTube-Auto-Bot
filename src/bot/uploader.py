import hashlib
import json
import os
import time
from datetime import datetime, timezone

import googleapiclient.discovery
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


class Uploader:
    def __init__(self, config, build_dir: str):
        self.cfg = config
        self.build_dir = build_dir
        self.video_file = os.path.join(build_dir, "final_short.mp4")
        self.meta_file = os.path.join(build_dir, "metadata.json")

    # ------------------------------------------------------------------ #
    #  HELPERS
    # ------------------------------------------------------------------ #

    def _sha256(self, path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _load_history(self) -> list:
        path = self.cfg.history_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data
            except (json.JSONDecodeError, OSError) as e:
                print(f"  Warning: Could not read upload history: {e}")
        return []

    def _save_history(self, video_id: str, title: str, sha: str):
        history = self._load_history()
        history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "video_id": video_id,
            "sha256": sha,
            "title": title,
            "profile": self.cfg.profile_name,
            "url": f"https://youtube.com/shorts/{video_id}",
        })
        path = self.cfg.history_path()
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)

    def _get_youtube_client(self):
        token_path = self.cfg.token_path()
        creds = None

        if os.path.exists(token_path):
            try:
                creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            except Exception as e:
                print(f"  Warning: Failed to load token.json: {e}")
                creds = None

        # If no valid creds, try interactive OAuth (local only)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("  Refreshing YouTube OAuth token...")
                try:
                    creds.refresh(Request())
                    with open(token_path, "w") as f:
                        f.write(creds.to_json())
                    print("  Token refreshed and saved.")
                except Exception as e:
                    print(f"  Token refresh failed: {e}")
                    creds = None

            if not creds or not creds.valid:
                if os.getenv("GITHUB_ACTIONS"):
                    raise Exception(
                        "YouTube credentials are invalid/expired and cannot be "
                        "refreshed in CI. Re-run the OAuth flow locally:\n"
                        "  1. Delete profiles/<name>/token.json\n"
                        "  2. Run: python main.py --profile <name> --dry-run\n"
                        "  3. Complete the browser OAuth flow\n"
                        "  4. Update the YOUTUBE_TOKEN secret in GitHub"
                    )
                print("  [Auth] No valid credentials. Opening browser for Google login...")
                from google_auth_oauthlib.flow import InstalledAppFlow
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.cfg.client_secrets_path(), SCOPES
                )
                creds = flow.run_local_server(port=0)
                with open(token_path, "w") as f:
                    f.write(creds.to_json())
                print("  New token saved.")

        return googleapiclient.discovery.build("youtube", "v3", credentials=creds)

    # ------------------------------------------------------------------ #
    #  ENTRY POINT
    # ------------------------------------------------------------------ #

    def run(self, dry_run: bool = False):
        print("--- [3/3] UPLOAD ---")

        # Validate files exist
        for path, name in [(self.video_file, "Video"), (self.meta_file, "Metadata")]:
            if not os.path.exists(path):
                raise FileNotFoundError(f"{name} file not found: {path}")

        # Load metadata
        with open(self.meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)

        title = meta.get("title", "Hindi Horror Story")
        description = meta.get("description", "#shorts #horror #hindi")
        tags = self.cfg.get("metadata", "tags", default=["shorts", "horror", "hindi"])
        privacy = self.cfg.get("automation", "privacy_status", default="private")

        # File hash for duplicate detection
        sha = self._sha256(self.video_file)
        video_size_mb = os.path.getsize(self.video_file) / 1024 / 1024

        print(f"  Title    : {title}")
        print(f"  Privacy  : {privacy}")
        print(f"  File size: {video_size_mb:.1f} MB")
        print(f"  SHA256   : {sha[:16]}...")

        # Duplicate check
        for entry in self._load_history():
            if entry.get("sha256") == sha:
                print(f"  ⚠️  Duplicate! Already uploaded as {entry.get('video_id')}. Skipping.")
                return

        if dry_run:
            print("  [DRY RUN] Skipping actual upload.")
            print("[3/3] Upload skipped (dry run).\n")
            return

        # Upload with retry
        youtube = self._get_youtube_client()

        print("  Uploading to YouTube...")
        request_body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": "24",  # Entertainment
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
            },
        }

        max_retries = 3
        for retry in range(max_retries):
            try:
                upload_request = youtube.videos().insert(
                    part="snippet,status",
                    body=request_body,
                    media_body=MediaFileUpload(
                        self.video_file, chunksize=10 * 1024 * 1024, resumable=True
                    ),
                )

                response = None
                while response is None:
                    status, response = upload_request.next_chunk()
                    if status:
                        pct = int(status.progress() * 100)
                        print(f"  Uploading... {pct}%")

                video_id = response["id"]
                url = f"https://youtube.com/shorts/{video_id}"

                print(f"\n  ✅ SUCCESS! Uploaded: {url}\n")
                self._save_history(video_id, title, sha)
                print("[3/3] Upload complete.\n")
                return video_id

            except Exception as e:
                if retry < max_retries - 1:
                    wait = 10 * (retry + 1)
                    print(f"  Upload attempt {retry + 1} failed: {e}. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    raise Exception(f"Upload failed after {max_retries} attempts: {e}")
