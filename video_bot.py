"""
Discord Video Bot.

Simple flow:
1. You create a forum post in the watched forum channel:
   - Title = video topic
   - Body = the script
   - Attach = the voiceover audio
2. Bot auto-detects the new post, creates a Drive folder with script + audio +
   auto-generated scene notes, then replies in the thread with the Drive link.

Run: py video_bot.py
Leave it running while you work.
"""

import asyncio
import base64
import os
import sys
import tempfile
from pathlib import Path

import discord
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent
load_dotenv(dotenv_path=SCRIPT_DIR / ".env", override=True)


# ─── Restore secret files from base64 env vars (for cloud hosting) ────────────

def _restore_from_b64(env_var: str, target_filename: str):
    """If env_var is set, decode it and write to target_filename (if file doesn't exist)."""
    target = SCRIPT_DIR / target_filename
    if target.exists():
        return  # keep local file if already present
    b64 = os.getenv(env_var)
    if not b64:
        return
    try:
        target.write_bytes(base64.b64decode(b64))
        print(f"[Bot] Restored {target_filename} from {env_var}")
    except Exception as e:
        print(f"[Bot] Failed to restore {target_filename}: {e}")


_restore_from_b64("OAUTH_CREDENTIALS_B64", "oauth_credentials.json")
_restore_from_b64("TOKEN_B64", "token.json")


# Existing Drive pipeline
from new_video import run as create_video_setup

if sys.stdout.encoding and sys.stdout.encoding.lower().startswith("cp"):
    sys.stdout.reconfigure(encoding="utf-8")

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
WATCH_CHANNEL_ID = int(os.getenv("DISCORD_WATCH_CHANNEL_ID", "0"))

if not BOT_TOKEN:
    print("[!] Missing DISCORD_BOT_TOKEN in .env")
    sys.exit(1)
if not WATCH_CHANNEL_ID:
    print("[!] Missing DISCORD_WATCH_CHANNEL_ID in .env")
    sys.exit(1)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

client = discord.Client(intents=intents)

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac", ".opus"}


async def get_starter_message(thread: discord.Thread, attempts: int = 5):
    """Forum posts sometimes have a delay before the initial message is readable."""
    for _ in range(attempts):
        # Try cached starter
        if thread.starter_message:
            return thread.starter_message
        # Try fetching by thread ID (forum posts)
        try:
            msg = await thread.fetch_message(thread.id)
            if msg:
                return msg
        except Exception:
            pass
        # Fallback: history
        async for msg in thread.history(limit=5, oldest_first=True):
            if not msg.author.bot:
                return msg
        await asyncio.sleep(2)
    return None


@client.event
async def on_ready():
    print(f"[Bot] Logged in as {client.user}")
    print(f"[Bot] Watching forum channel: {WATCH_CHANNEL_ID}")
    print(f"[Bot] Ready. Create a forum post to trigger.\n")


@client.event
async def on_thread_create(thread: discord.Thread):
    if thread.parent_id != WATCH_CHANNEL_ID:
        return

    print(f"[Bot] New forum post: '{thread.name}'")

    try:
        starter = await get_starter_message(thread)
        if not starter:
            await thread.send("⚠️ couldn't read the post body. put the script in the body.")
            return

        script_text = starter.content.strip()
        if not script_text:
            await thread.send("⚠️ no script found. put the script in the body of the post.")
            return

        # Find audio attachment
        audio_attachment = None
        for att in starter.attachments:
            if Path(att.filename).suffix.lower() in AUDIO_EXTS:
                audio_attachment = att
                break

        status_msg = await thread.send("⏳ working on it...")

        # Download audio to temp file
        tmp_audio = None
        audio_path = None
        if audio_attachment:
            print(f"[Bot] Downloading audio: {audio_attachment.filename}")
            suffix = Path(audio_attachment.filename).suffix or ".mp3"
            fd, tmp_audio = tempfile.mkstemp(suffix=suffix, dir=str(SCRIPT_DIR))
            os.close(fd)
            await audio_attachment.save(tmp_audio)
            audio_path = Path(tmp_audio)
        else:
            print(f"[Bot] No audio attached, continuing without")

        topic = thread.name

        # Run Drive pipeline in a thread pool (doesn't block the bot)
        print(f"[Bot] Creating Drive folder for: {topic}")
        loop = asyncio.get_event_loop()
        try:
            link = await loop.run_in_executor(
                None,
                create_video_setup,
                topic,
                script_text,
                audio_path,
                False,  # skip_notes=False
            )
        finally:
            if tmp_audio:
                try:
                    os.unlink(tmp_audio)
                except Exception:
                    pass

        print(f"[Bot] ✅ Done: {link}\n")
        await status_msg.edit(content=f"📁 **Drive folder:** {link}")

    except Exception as e:
        print(f"[Bot] Error: {e}\n")
        try:
            await thread.send(f"❌ Error: {e}")
        except Exception:
            pass


if __name__ == "__main__":
    client.run(BOT_TOKEN)
