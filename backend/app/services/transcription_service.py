from __future__ import annotations
"""
ClinNote AI — DeepInfra Whisper v3 Transcription Service
==========================================================
Handles chunked real-time transcription during recording and final
full-audio transcription when recording completes.

API:
  POST https://api.deepinfra.com/v1/inference/openai/audio/transcriptions
  Authorization: Bearer {DEEPINFRA_API_KEY}
  Body (multipart/form-data):
    file  : audio file bytes (wav/mp3/ogg/webm/m4a)
    model : openai/whisper-large-v3
    response_format: verbose_json  → returns segments with timestamps
    language: en (optional, improves accuracy)

HIPAA Note:
  Audio is sent to DeepInfra under the assumption that a Business Associate
  Agreement (BAA) is in place. Audio bytes are never persisted — only the
  resulting text is stored (encrypted).
"""


import asyncio
import io
import logging
from typing import Any

import httpx

from app.config import get_settings
from app.utils.medical_vocab import apply_medical_corrections

logger = logging.getLogger(__name__)
settings = get_settings()


class TranscriptionService:
    """
    Async client for DeepInfra Whisper Large v3 transcription.

    Usage:
        svc = TranscriptionService()
        partial = await svc.transcribe_chunk(audio_bytes, chunk_index=0)
        final   = await svc.transcribe_final(session_id="uuid")
    """

    DEEPINFRA_ENDPOINT = "https://api.deepinfra.com/v1/inference/openai/audio/transcriptions"
    MAX_RETRIES = 3
    RETRY_BACKOFF = 2.0  # seconds

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {settings.DEEPINFRA_API_KEY}"},
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

    async def __aenter__(self) -> "TranscriptionService":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ #
    # Chunked transcription (real-time, during recording)
    # ------------------------------------------------------------------ #

    async def transcribe_chunk(
        self,
        audio_bytes: bytes,
        chunk_index: int,
        language: str = "en",
        filename: str = "chunk.wav",
    ) -> dict[str, Any]:
        """
        Send a 3-second audio chunk to Whisper and return a partial transcript.

        Args:
            audio_bytes : Raw audio bytes for this chunk (WAV/WebM/MP3).
            chunk_index : Sequential chunk number (for ordering partial results).
            language    : BCP-47 language hint (default "en").
            filename    : Filename hint for Whisper (helps with format detection).

        Returns:
            dict with keys:
              - text         : Transcribed text for this chunk.
              - chunk_index  : Echo of input chunk_index.
              - language     : Detected or provided language.
              - segments     : List of word-level segments (if returned).
              - confidence   : Average log-probability (if available).

        Raises:
            httpx.HTTPStatusError: If the API returns a non-2xx status.
            RuntimeError: After MAX_RETRIES exhausted.
        """
        result = await self._call_whisper(audio_bytes, filename, language)
        text = result.get("text", "")
        corrected = apply_medical_corrections(text)

        return {
            "text": corrected,
            "chunk_index": chunk_index,
            "language": result.get("language", language),
            "segments": result.get("segments", []),
            "confidence": self._avg_confidence(result.get("segments", [])),
        }

    # ------------------------------------------------------------------ #
    # Final transcription (full audio after recording ends)
    # ------------------------------------------------------------------ #

    async def transcribe_final(
        self,
        audio_bytes: bytes,
        session_id: str,
        language: str = "en",
    ) -> dict[str, Any]:
        """
        Send the complete recording audio to Whisper for high-accuracy transcription.
        Applies medical vocabulary corrections to the output.

        Args:
            audio_bytes: Full recording audio bytes.
            session_id : Recording session UUID (for logging/tracing only).
            language   : BCP-47 language hint.

        Returns:
            dict with keys:
              - text          : Full corrected transcript.
              - raw_text      : Original Whisper output (before corrections).
              - language      : Detected language.
              - diarization   : List of speaker segments [{speaker, start, end, text}].
              - word_count    : Word count of corrected text.
              - confidence    : Average Whisper confidence.
              - segments      : Raw segment list from Whisper.

        Raises:
            RuntimeError: After MAX_RETRIES exhausted.
        """
        logger.info("Starting final transcription for session %s", session_id)
        result = await self._call_whisper(audio_bytes, "recording.wav", language)

        raw_text: str = result.get("text", "")
        corrected_text = apply_medical_corrections(raw_text)
        segments = result.get("segments", [])
        diarization = self._build_diarization(segments)

        logger.info(
            "Final transcription complete for session %s — %d words",
            session_id,
            len(corrected_text.split()),
        )

        return {
            "text": corrected_text,
            "raw_text": raw_text,
            "language": result.get("language", language),
            "diarization": diarization,
            "word_count": len(corrected_text.split()),
            "confidence": self._avg_confidence(segments),
            "segments": segments,
        }

    # ------------------------------------------------------------------ #
    # Medical vocabulary correction
    # ------------------------------------------------------------------ #

    async def apply_medical_correction(self, text: str) -> str:
        """
        Apply medical terminology corrections to transcribed text.

        Args:
            text: Raw transcription string.

        Returns:
            Corrected text with proper medical terminology.
        """
        return apply_medical_corrections(text)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    async def _call_whisper(
        self,
        audio_bytes: bytes,
        filename: str,
        language: str,
    ) -> dict[str, Any]:
        """
        Make the HTTP call to DeepInfra Whisper with exponential retry.

        Args:
            audio_bytes: Raw audio bytes.
            filename   : Filename for multipart upload.
            language   : Language hint.

        Returns:
            Parsed JSON response from Whisper.

        Raises:
            RuntimeError: After MAX_RETRIES consecutive failures.
        """
        last_exc: Exception | None = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                files = {
                    "file": (filename, io.BytesIO(audio_bytes), "audio/wav"),
                }
                data = {
                    "model": settings.DEEPINFRA_WHISPER_MODEL,
                    "response_format": "verbose_json",
                    "language": language,
                }
                response = await self._client.post(
                    self.DEEPINFRA_ENDPOINT,
                    files=files,
                    data=data,
                )
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "Whisper API returned %s on attempt %d/%d",
                    exc.response.status_code,
                    attempt,
                    self.MAX_RETRIES,
                )
                last_exc = exc
                if exc.response.status_code in (400, 401, 403):
                    # Non-retryable errors
                    raise

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                logger.warning(
                    "Whisper connection error on attempt %d/%d: %s",
                    attempt,
                    self.MAX_RETRIES,
                    exc,
                )
                last_exc = exc

            if attempt < self.MAX_RETRIES:
                await asyncio.sleep(self.RETRY_BACKOFF ** attempt)

        raise RuntimeError(
            f"DeepInfra Whisper API failed after {self.MAX_RETRIES} attempts: {last_exc}"
        )

    @staticmethod
    def _avg_confidence(segments: list[dict]) -> float | None:
        """Calculate average log-probability confidence from Whisper segments."""
        if not segments:
            return None
        probs = [
            s.get("avg_logprob") or s.get("confidence")
            for s in segments
            if s.get("avg_logprob") is not None or s.get("confidence") is not None
        ]
        if not probs:
            return None
        # Convert log-prob to [0,1] range
        import math
        raw_avg = sum(probs) / len(probs)
        # If it's a log-prob (negative), convert to probability
        if raw_avg <= 0:
            return round(math.exp(raw_avg), 4)
        return round(raw_avg, 4)

    @staticmethod
    def _build_diarization(segments: list[dict]) -> list[dict[str, Any]]:
        """
        Build speaker-labeled diarization from Whisper segments.
        Whisper does not natively diarize, so all segments are labeled "S1".
        A future version could integrate pyannote.audio for real diarization.

        Args:
            segments: Raw segment list from Whisper verbose_json output.

        Returns:
            List of diarization dicts: [{speaker, start, end, text}]
        """
        return [
            {
                "speaker": "S1",  # Single speaker — extend with pyannote for diarization
                "start": float(seg.get("start", 0)),
                "end": float(seg.get("end", 0)),
                "text": seg.get("text", "").strip(),
            }
            for seg in segments
            if seg.get("text")
        ]
