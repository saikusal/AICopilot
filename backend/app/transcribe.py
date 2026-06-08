import os
import tempfile
import httpx
from .config import Settings

_whisper_model = None


async def transcribe_audio(audio: bytes, content_type: str, settings: Settings) -> str:
    provider = settings.stt_provider.lower().strip()
    if provider in {"local", "local_whisper", "whisper", "faster_whisper"}:
        return _transcribe_with_faster_whisper(audio, settings)
    return await _transcribe_with_deepgram(audio, content_type, settings)


async def _transcribe_with_deepgram(audio: bytes, content_type: str, settings: Settings) -> str:
    if not settings.deepgram_api_key:
        raise RuntimeError("DEEPGRAM_API_KEY is not configured")

    params = {
        "model": settings.deepgram_model,
        "smart_format": "true",
        "punctuate": "true",
        "utterances": "true",
    }
    headers = {
        "Authorization": f"Token {settings.deepgram_api_key}",
        "Content-Type": content_type or "audio/webm",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.deepgram.com/v1/listen",
            params=params,
            headers=headers,
            content=audio,
        )
        response.raise_for_status()
        data = response.json()

    channels = data.get("results", {}).get("channels", [])
    if not channels:
        return ""
    alternatives = channels[0].get("alternatives", [])
    if not alternatives:
        return ""
    return alternatives[0].get("transcript", "").strip()


def _transcribe_with_faster_whisper(audio: bytes, settings: Settings) -> str:
    global _whisper_model
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper is not installed") from exc

    if _whisper_model is None:
        _whisper_model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )

    suffix = ".webm"
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(audio)
        segments, _info = _whisper_model.transcribe(
            path,
            language="en",
            vad_filter=True,
            beam_size=1,
        )
        return " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
