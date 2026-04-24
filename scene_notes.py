"""
Animation Scene Notes Generator.
Takes a script and generates inline animation notes
for Roblox Studio animators.
"""

import sys
from pathlib import Path
from shared import api_call, cached_system, init_client, MODEL

if sys.stdout.encoding and sys.stdout.encoding.lower().startswith("cp"):
    sys.stdout.reconfigure(encoding="utf-8")

_api_create = None

SYSTEM = """You annotate scripts for Roblox YouTube Shorts with inline animation notes.

You receive a voiceover script. Your job is to return the SAME script text but with animation notes inserted after each line or natural break.

FORMATTING:
- Keep every single line of the original script exactly as written
- After each line add a blank line, then the animation note in parentheses
- Add another blank line before the next script line

RULES:
- Notes describe: what characters are doing, their expressions, reactions, visual gags
- Keep notes SHORT and punchy. One line in parentheses. The animator fills in the details.
- Use casual language. These go to young animators on Discord.
- When something is a new visual (new character, new location, new setup), just describe it naturally in the note. Do NOT label scenes with numbers.
- When the same visual continues, the note just adds to it
- Suggest Roblox character types when relevant (bacon, noob, slender, etc.)
- Do NOT include any camera directions (no close-up, no zoom, no pan, no camera anything). Just describe what the characters are doing.
- Do NOT use emojis or emotes of any kind.

EXAMPLE INPUT:
Bro my friend really said he'd be there in 5 minutes
and showed up 3 hours later acting like nothing happened

EXAMPLE OUTPUT:
Bro my friend really said he'd be there in 5 minutes

(bacon character sitting alone, checking the time, looking bored)

and showed up 3 hours later acting like nothing happened

(friend walks in super casual, bacon character stares at him in disbelief)

IMPORTANT:
- Output the script lines AND the notes together with blank lines between them for readability. Nothing else.
- No intro, no summary, no "here are the notes", no scene labels.
- No emojis anywhere."""


def generate(script: str) -> str:
    resp = api_call(
        _api_create,
        model=MODEL,
        max_tokens=2000,
        temperature=0.5,
        system=cached_system(SYSTEM),
        messages=[{"role": "user", "content": script}],
    )
    return resp.content[0].text.strip()


def main():
    global _api_create
    client = init_client(Path(__file__).parent)
    _api_create = client.messages.create

    print("=== Animation Scene Notes Generator ===")
    print("Paste your script, then enter a blank line to generate.\n")

    while True:
        print("-" * 40)
        print("Paste script (blank line to submit, 'q' to quit):\n")
        lines = []
        while True:
            line = input()
            if line.strip().lower() == "q" and not lines:
                return
            if line == "" and lines:
                break
            lines.append(line)

        script = "\n".join(lines).strip()
        if not script:
            continue

        print("\nGenerating scene notes...\n")
        notes = generate(script)
        print(notes)
        print()


if __name__ == "__main__":
    main()
