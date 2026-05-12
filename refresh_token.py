"""Quick script to refresh YouTube OAuth token locally."""
import json
import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

profile = sys.argv[1] if len(sys.argv) > 1 else "mythology"
token_path = os.path.join("profiles", profile, "token.json")
secrets_path = "client_secrets.json"

if not os.path.exists(secrets_path):
    print(f"ERROR: {secrets_path} not found!")
    sys.exit(1)

print(f"Opening browser for YouTube authorization...")
print(f"Sign in with your YouTube channel's Google account.\n")

flow = InstalledAppFlow.from_client_secrets_file(secrets_path, SCOPES)
creds = flow.run_local_server(port=0)

with open(token_path, "w") as f:
    f.write(creds.to_json())

print(f"\nToken saved to: {token_path}")
print(f"\nNow update your GitHub secret:")
print(f"  1. Copy the contents below")
print(f"  2. Go to repo Settings > Secrets > Actions > YOUTUBE_TOKEN > Update")
print(f"\n--- Copy everything below this line ---")
print(open(token_path).read())
