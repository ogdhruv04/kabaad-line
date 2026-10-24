"""ElevenLabs text-to-speech for collector briefings (plain REST, no SDK version drift)."""
import httpx

from . import config


def synthesize(text: str) -> bytes | None:
    """Return MP3 bytes, or None if ElevenLabs isn't configured (the app still works, just without audio)."""
    if not (config.ELEVENLABS_API_KEY and config.ELEVENLABS_VOICE_ID):
        return None
    r = httpx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": config.ELEVENLABS_API_KEY, "Content-Type": "application/json"},
        json={"text": text, "model_id": config.ELEVENLABS_TTS_MODEL, "language_code": "hi"},
        timeout=60,
    )
    r.raise_for_status()
    return r.content
