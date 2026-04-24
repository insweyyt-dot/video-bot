# Video Bot

Discord bot + Google Drive automation for animated YouTube Shorts production.

When you create a forum post with a script and audio attachment, the bot automatically:
1. Creates a Google Drive folder with the video number and title
2. Uploads the script (cleaned) and audio
3. Generates scene notes using Claude
4. Sets the folder to "anyone with link can edit"
5. Replies in the Discord thread with the folder link

## Files

- `video_bot.py` — Discord bot (watches a forum channel)
- `new_video.py` — Drive folder creation + uploads
- `scene_notes.py` — AI scene notes generator
- `shared.py` — Anthropic client helpers

## Setup

### 1. Install Python 3.10+ and dependencies

```
pip install -r requirements.txt
```

### 2. Set up Anthropic API key

Get a key at [console.anthropic.com](https://console.anthropic.com), then copy `.env.example` to `.env` and fill in `ANTHROPIC_API_KEY`.

### 3. Set up Google Drive OAuth

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → create a project
2. Enable the **Google Drive API** (APIs & Services → Library)
3. Configure OAuth consent screen (External, add yourself as test user, click Publish App)
4. Create **OAuth Client ID** → Application type: **Desktop app**
5. Download the JSON → save as `oauth_credentials.json` in this folder
6. Create a Google Drive folder where all video folders will live
7. Copy its folder ID (from the URL) → paste into `.env` as `GOOGLE_DRIVE_PARENT_FOLDER_ID`

### 4. Set up Discord bot

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications) → New Application
2. Bot tab → Reset Token → copy it into `.env` as `DISCORD_BOT_TOKEN`
3. Bot tab → enable **MESSAGE CONTENT INTENT** → Save
4. OAuth2 → URL Generator → scopes: `bot` → permissions: View Channels, Send Messages, Read Message History, Attach Files, Create Public Threads, Send Messages in Threads
5. Open the generated URL and invite the bot to your server
6. In Discord, create a **Forum Channel** for video briefs
7. Enable Developer Mode (User Settings → Advanced) → right-click the forum channel → Copy Channel ID
8. Paste into `.env` as `DISCORD_WATCH_CHANNEL_ID`

## Running

```
python video_bot.py
```

First run opens a browser for Google Drive sign-in and saves the token to `token.json`. Subsequent runs use the saved token.

## Usage

1. Go to the watched forum channel in Discord
2. Create a new forum post:
   - **Title** = video topic (e.g. "Ice Cream Kindness")
   - **Body** = the voiceover script
   - **Attachment** = the voiceover MP3
3. Within ~15 seconds, the bot replies in the thread with the Drive folder link

## Standalone CLI (no Discord)

You can also run `new_video.py` directly from the terminal:

```
python new_video.py --topic "Cat Manipulation" --script script.txt --audio voice.mp3
```

Or interactively:

```
python new_video.py
```
