"""
Minimal shared helpers used by scene_notes.py and new_video.py.
"""

import os
import sys
import time
from pathlib import Path

from anthropic import Anthropic, InternalServerError, APIStatusError
from dotenv import load_dotenv

MODEL = "claude-sonnet-4-6"


def load_env(script_dir: Path | None = None) -> None:
    if script_dir is None:
        script_dir = Path(__file__).parent
    load_dotenv(dotenv_path=script_dir / ".env", override=True)


def init_client(script_dir: Path | None = None) -> Anthropic:
    load_env(script_dir)
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("\n[!] ANTHROPIC_API_KEY not found in .env.")
        print("    Get a key at console.anthropic.com, add it to your .env file.")
        sys.exit(1)
    return Anthropic(api_key=api_key)


def api_call(create_fn, **kwargs):
    """Call create_fn(**kwargs) with exponential backoff on 500/529 errors."""
    delays = [5, 15, 30, 60, 120, 180]
    for attempt, delay in enumerate(delays + [None]):
        try:
            return create_fn(**kwargs)
        except (InternalServerError, APIStatusError) as e:
            if delay is None:
                raise
            code = getattr(e, "status_code", 0)
            if code not in (500, 529):
                raise
            print(f"  [API {code}] retrying in {delay}s... (attempt {attempt+1}/{len(delays)})")
            time.sleep(delay)


def cached_system(text: str) -> list[dict]:
    """Wrap a system prompt for ephemeral prompt caching (5-min TTL)."""
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]
