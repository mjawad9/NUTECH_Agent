import requests
from config import get_secret

DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # ElevenLabs' built-in "Rachel" voice


def speak(text: str) -> bytes | None:
    """Convert text to MP3 audio using ElevenLabs. Returns None if no API key is set."""
    api_key = get_secret("ELEVENLABS_API_KEY")
    if not api_key:
        return None
    voice_id = get_secret("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={"text": text[:2500], "model_id": "eleven_multilingual_v2"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.content
