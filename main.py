"""
Entry point for Railway / Railpack deployment.
Just imports and runs the Discord bot defined in video_bot.py.
"""

from video_bot import client, BOT_TOKEN

if __name__ == "__main__":
    client.run(BOT_TOKEN)
