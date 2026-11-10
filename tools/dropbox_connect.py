"""Connect Dropbox for the daily Replenishment job, once (or again if it stops).

Run from the repo folder:  python tools/dropbox_connect.py
1. A Dropbox page opens: click Allow, then copy the code it shows.
2. Paste the code here and press Enter.
The lasting Dropbox sign-in goes straight into the repo's GitHub secrets
(DROPBOX_APP_KEY, DROPBOX_REFRESH_TOKEN), plus SUPABASE_URL / SUPABASE_KEY from
.streamlit/secrets.toml. Nothing secret is printed or saved on this laptop.
Uses the "Smilez Studio TV" Dropbox app (its key is public, not a secret).
"""
import base64
import hashlib
import secrets
import subprocess
import sys
import tomllib
import webbrowser
from pathlib import Path
from urllib.parse import urlencode

import requests

APP_KEY = "s7q6yi6lqghg2o4"
REPO = "Shadedev4202k26/Gap-Analysis"
HERE = Path(__file__).resolve().parents[1]
# A worktree has no secrets.toml of its own: fall back to the main checkout's.
_common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=HERE,
                         capture_output=True, text=True).stdout.strip()
SECRETS_TOML = next((p for p in [HERE / ".streamlit" / "secrets.toml",
                                 (HERE / _common).resolve().parent / ".streamlit" / "secrets.toml"]
                     if p.exists()), HERE / ".streamlit" / "secrets.toml")


def set_secret(name, value):
    subprocess.run(["gh", "secret", "set", name, "-R", REPO], input=value.encode(),
                   check=True, stdout=subprocess.DEVNULL)
    print(f"  saved {name}")


def main():
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    url = "https://www.dropbox.com/oauth2/authorize?" + urlencode({
        "client_id": APP_KEY, "response_type": "code", "token_access_type": "offline",
        "code_challenge": challenge, "code_challenge_method": "S256"})
    print("A Dropbox page is opening. Click Allow, then copy the code it shows.")
    print("(If it doesn't open, paste this into the browser:)\n" + url + "\n")
    webbrowser.open(url)
    code = input("Paste the code here and press Enter: ").strip()
    r = requests.post("https://api.dropboxapi.com/oauth2/token", timeout=30, data={
        "grant_type": "authorization_code", "code": code, "client_id": APP_KEY,
        "code_verifier": verifier})
    if not r.ok or "refresh_token" not in r.json():
        sys.exit(f"Dropbox didn't accept that code ({r.status_code}). Run this again.")
    refresh = r.json()["refresh_token"]
    print("Dropbox connected. Saving to GitHub...")
    subprocess.run(["gh", "auth", "switch", "-u", "Shadedev4202k26"], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        set_secret("DROPBOX_APP_KEY", APP_KEY)
        set_secret("DROPBOX_REFRESH_TOKEN", refresh)
        if SECRETS_TOML.exists():
            sec = tomllib.loads(SECRETS_TOML.read_text("utf-8"))
            set_secret("SUPABASE_URL", sec["SUPABASE_URL"])
            set_secret("SUPABASE_KEY", sec["SUPABASE_KEY"])
    finally:
        subprocess.run(["gh", "auth", "switch", "-u", "SmilezMedia"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Done. You can close this window.")


if __name__ == "__main__":
    main()
