"""Step 2: Chuyển script thành giọng nói bằng ElevenLabs."""
import os
from pathlib import Path

from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv

from .cache import get_file, set_file

load_dotenv()

OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_voice(script: str, use_cache: bool = True) -> Path:
    cache_key = f"voice:{script[:200]}"
    if use_cache:
        cached = get_file(cache_key, "voice", "mp3")
        if cached:
            return cached

    client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

    audio = client.text_to_speech.convert(
        voice_id=voice_id,
        text=script,
        output_format="mp3_44100_128",
    )

    out_path = OUTPUT_DIR / "voice_temp.mp3"
    with open(out_path, "wb") as f:
        for chunk in audio:
            if chunk:
                f.write(chunk)

    if use_cache:
        return set_file(cache_key, out_path, "voice")
    return out_path
