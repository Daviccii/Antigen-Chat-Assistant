"""
Voice endpoints: local speech-to-text and text-to-speech.

- STT: faster-whisper, runs fully on-device (CPU by default), no audio ever
  leaves the machine.
- TTS: Piper, a fast local neural TTS engine. Shells out to the `piper`
  binary rather than requiring a heavyweight Python TTS stack.

Install (from backend/, with your venv active):

    pip install faster-whisper

Piper is a pure Python package with its own API — no separate binary or
subprocess needed:

    pip install piper-tts
    python -m piper.download_voices en_US-lessac-medium

The download command drops en_US-lessac-medium.onnx and .onnx.json into
your current directory. Point PIPER_VOICE_MODEL_PATH below at the .onnx
file's full path.

Wire this into your app in main.py:

    from .voice import router as voice_router
    app.include_router(voice_router)
"""
import io
import os
import tempfile
import wave
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .auth import get_current_active_user
from .models import User

router = APIRouter(prefix="/voice", tags=["voice"])


# ---------------------------------------------------------------------------
# Speech-to-text (faster-whisper)
# ---------------------------------------------------------------------------

_whisper_model = None


def get_whisper_model():
    """Lazily load the Whisper model once and reuse it across requests."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        # "base" balances speed/accuracy well on CPU for a personal assistant.
        # Bump to "small" or "medium" if your machine can handle it and you
        # want better accuracy, especially for accents or background noise.
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    return _whisper_model


@router.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """Transcribe uploaded audio to text using a local Whisper model."""
    model = get_whisper_model()

    suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name

    try:
        segments, _info = model.transcribe(tmp_path, language="en")
        text = " ".join(seg.text.strip() for seg in segments).strip()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if not text:
        raise HTTPException(status_code=422, detail="Could not make out any speech in that audio")

    return {"text": text}


# ---------------------------------------------------------------------------
# Text-to-speech (Piper)
# ---------------------------------------------------------------------------

# Map of friendly voice name -> path to its .onnx model file. Add more
# entries here as you download additional voices with
# `python -m piper.download_voices <voice-name>`.
# Voice models should be placed in the backend directory
backend_dir = Path(__file__).parent.parent
VOICE_MODELS = {
    "lessac": str(backend_dir / "en_US-lessac-medium.onnx"),
}
DEFAULT_VOICE = "lessac"

_piper_voices = {}


def get_piper_voice(voice_name: str | None = None):
    """Lazily load a Piper voice model once and reuse it across requests."""
    name = voice_name if voice_name in VOICE_MODELS else DEFAULT_VOICE
    if name not in _piper_voices:
        from piper import PiperVoice

        voice_path = VOICE_MODELS[name]
        if not os.path.exists(voice_path):
            raise FileNotFoundError(
                f"Voice model file not found: {voice_path}. "
                f"Download it with: python -m piper.download_voices en_US-lessac-medium"
            )
        _piper_voices[name] = PiperVoice.load(voice_path)
    return _piper_voices[name]


@router.get("/voices")
async def list_voices(current_user: User = Depends(get_current_active_user)):
    """List configured voice names so the frontend can offer a picker."""
    return {"voices": list(VOICE_MODELS.keys()), "default": DEFAULT_VOICE}


class SpeakRequest(BaseModel):
    text: str
    voice: str | None = None


@router.post("/speak")
async def speak(
    payload: SpeakRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Synthesize speech for the given text with a local Piper voice; returns WAV audio."""
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="No text provided")

    try:
        voice = get_piper_voice(payload.voice)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not load Piper voice '{payload.voice or DEFAULT_VOICE}': {exc}",
        )

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)
    buf.seek(0)

    return StreamingResponse(buf, media_type="audio/wav")