"""
New Video Setup Tool.
Creates a Google Drive folder for a new video, generates scene notes,
uploads script + audio + notes, sets 'anyone with link' permissions,
returns the link.

First run: browser opens for Google sign-in. Token is saved to token.json.
Later runs: uses the saved token, no browser needed.

Usage (CLI):
    py new_video.py --topic "Cat Manipulation" --script script.txt --audio voice.mp3

Usage (interactive):
    py new_video.py
"""

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from shared import init_client

if sys.stdout.encoding and sys.stdout.encoding.lower().startswith("cp"):
    sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = Path(__file__).parent
SCOPES = ["https://www.googleapis.com/auth/drive"]
OAUTH_CREDS_FILE = SCRIPT_DIR / "oauth_credentials.json"
TOKEN_FILE = SCRIPT_DIR / "token.json"


# ─── Config ───────────────────────────────────────────────────────────────────

def get_env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        print(f"\n[!] Missing {key} in .env")
        sys.exit(1)
    return val


# ─── Drive auth (OAuth installed app flow) ────────────────────────────────────

def drive_service():
    if not OAUTH_CREDS_FILE.exists():
        print(f"\n[!] OAuth credentials file not found: {OAUTH_CREDS_FILE}")
        print("    Setup:")
        print("    1. Go to console.cloud.google.com")
        print("    2. APIs & Services → Credentials")
        print("    3. Create Credentials → OAuth Client ID")
        print("    4. Application type: Desktop app")
        print("    5. Download JSON, save as oauth_credentials.json in this folder")
        sys.exit(1)

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(str(OAUTH_CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return build("drive", "v3", credentials=creds)


# ─── Drive ops ────────────────────────────────────────────────────────────────

def next_video_number(svc, parent_id: str) -> int:
    q = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = svc.files().list(q=q, fields="files(name)", pageSize=1000).execute()
    numbers = []
    for f in results.get("files", []):
        m = re.match(r"Video #(\d+)", f["name"])
        if m:
            numbers.append(int(m.group(1)))
    return max(numbers) + 1 if numbers else 1


def create_folder(svc, name: str, parent_id: str) -> str:
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = svc.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def set_public_editor(svc, folder_id: str):
    svc.permissions().create(
        fileId=folder_id,
        body={"role": "writer", "type": "anyone"},
        fields="id",
    ).execute()


def upload_file(svc, folder_id: str, file_path: Path, rename: str = None, mime: str = None):
    metadata = {
        "name": rename or file_path.name,
        "parents": [folder_id],
    }
    media = MediaFileUpload(str(file_path), mimetype=mime, resumable=True)
    try:
        svc.files().create(body=metadata, media_body=media, fields="id").execute()
    finally:
        # Release the file handle so temp files can be deleted on Windows
        del media


def clean_script(text: str) -> str:
    """Remove . and , punctuation, put each sentence on its own line."""
    text = text.replace("\n", " ").strip()
    # preserve ellipsis temporarily
    text = text.replace("...", "<<ELLIPSIS>>").replace("…", "<<ELLIPSIS>>")
    # remove commas
    text = text.replace(",", "")
    # split on sentence-ending punctuation
    parts = re.split(r"(?<=[.!?])\s+", text)
    cleaned = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # drop trailing periods (keep ! and ?)
        while p.endswith("."):
            p = p[:-1].rstrip()
        # restore ellipsis (drop it, keeps flow cleaner)
        p = p.replace("<<ELLIPSIS>>", "").strip()
        # collapse multiple spaces
        p = re.sub(r"\s+", " ", p)
        if p:
            cleaned.append(p)
    return "\n".join(cleaned)


def upload_text(svc, folder_id: str, name: str, content: str):
    tmp_fd, tmp_name = tempfile.mkstemp(suffix=".txt", dir=str(SCRIPT_DIR))
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(content)
        upload_file(svc, folder_id, Path(tmp_name), rename=name, mime="text/plain")
    finally:
        try:
            os.unlink(tmp_name)
        except Exception:
            pass


# ─── Scene notes integration ──────────────────────────────────────────────────

def generate_notes(script: str, client) -> str | None:
    try:
        import scene_notes
        scene_notes._api_create = client.messages.create
        return scene_notes.generate(script)
    except Exception as e:
        print(f"  [!] scene notes failed: {e}")
        return None


# ─── Clipboard ────────────────────────────────────────────────────────────────

def copy_to_clipboard(text: str) -> bool:
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        return False


# ─── Main flow ────────────────────────────────────────────────────────────────

def run(topic: str, script_text: str, audio_path: Path = None, skip_notes: bool = False):
    parent_id = get_env("GOOGLE_DRIVE_PARENT_FOLDER_ID")

    # Clean the script: remove . and , and put each sentence on its own line
    cleaned_script = clean_script(script_text)

    print("\nConnecting to Google Drive...")
    svc = drive_service()

    print("Finding next video number...")
    n = next_video_number(svc, parent_id)
    folder_name = f"Video #{n} - {topic}"

    print(f"Creating folder: {folder_name}")
    folder_id = create_folder(svc, folder_name, parent_id)

    print("Setting public editor permissions...")
    set_public_editor(svc, folder_id)

    print("Uploading script...")
    upload_text(svc, folder_id, "01 - Script.txt", cleaned_script)

    if audio_path and audio_path.exists():
        print(f"Uploading audio ({audio_path.name})...")
        upload_file(svc, folder_id, audio_path, rename=f"02 - Voiceover{audio_path.suffix}")
    else:
        print("  [skip] no audio file provided")

    if not skip_notes:
        print("Generating scene notes...")
        client = init_client(SCRIPT_DIR)
        notes = generate_notes(cleaned_script, client)
        if notes:
            print("Uploading scene notes...")
            upload_text(svc, folder_id, "03 - Scene Notes.txt", notes)

    link = f"https://drive.google.com/drive/folders/{folder_id}"
    copied = copy_to_clipboard(link)

    print("\n" + "=" * 50)
    print("✅ Done")
    print(f"📁 {folder_name}")
    print(f"🔗 {link}")
    if copied:
        print("📋 Link copied to clipboard")
    print("=" * 50)
    return link


# ─── CLI / Interactive ────────────────────────────────────────────────────────

def interactive():
    print("=== New Video Setup ===\n")

    topic = input("Topic / title: ").strip()
    if not topic:
        print("[!] Topic is required")
        return

    print("\nPaste script (blank line to submit):")
    lines = []
    while True:
        line = input()
        if line == "" and lines:
            break
        if line.strip() == "" and not lines:
            continue
        lines.append(line)
    script_text = "\n".join(lines).strip()
    if not script_text:
        print("[!] Script is required")
        return

    audio_in = input("\nAudio file path (drag & drop, or leave blank): ").strip().strip('"').strip("'")
    audio_path = Path(audio_in) if audio_in else None

    run(topic, script_text, audio_path)


def cli():
    parser = argparse.ArgumentParser(description="Create a new video setup in Google Drive")
    parser.add_argument("--topic", help="Video topic/title")
    parser.add_argument("--script", help="Path to script file")
    parser.add_argument("--audio", help="Path to voiceover audio file")
    parser.add_argument("--skip-notes", action="store_true", help="Skip scene notes generation")
    args = parser.parse_args()

    if not args.topic and not args.script:
        interactive()
        return

    if not args.topic or not args.script:
        print("[!] Need both --topic and --script (or run with no args for interactive mode)")
        sys.exit(1)

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"[!] Script file not found: {script_path}")
        sys.exit(1)
    script_text = script_path.read_text(encoding="utf-8").strip()

    audio_path = Path(args.audio) if args.audio else None
    if audio_path and not audio_path.exists():
        print(f"[!] Audio file not found: {audio_path}")
        sys.exit(1)

    run(args.topic, script_text, audio_path, skip_notes=args.skip_notes)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=SCRIPT_DIR / ".env", override=True)
    cli()
