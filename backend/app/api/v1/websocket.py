from __future__ import annotations
"""
ClinNote AI — WebSocket Endpoint
===================================
Real-time audio streaming for ambient recording sessions.

WS /ws/recording/{session_id}

Protocol:
  Client → Server messages:
    {"type": "audio_chunk", "data": "<base64_audio>", "chunk_index": 0}
    {"type": "stop_recording"}
    {"type": "pause_recording"}
    {"type": "resume_recording"}
    {"type": "ping"}

  Server → Client messages:
    {"type": "partial_transcript", "text": "...", "chunk_index": 0, "language": "en"}
    {"type": "processing", "stage": "transcription", "message": "..."}
    {"type": "transcript_ready", "session_id": "...", "word_count": 150}
    {"type": "soap_ready", "note_id": "...", "session_id": "..."}
    {"type": "error", "code": "...", "message": "..."}
    {"type": "pong"}
    {"type": "connected", "session_id": "...", "message": "..."}

Authentication:
  Preferred — JWT token via the Sec-WebSocket-Protocol header.
              Client sends two subprotocols: ["bearer", "<access_token>"].
              The server accepts with subprotocol="bearer".
  Legacy   — JWT token in query parameter `?token=<access_token>`.
              This path emits a deprecation warning to logs because
              query strings can leak into access logs / proxies.
"""


import asyncio
import base64
import io
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.recording_session import RecordingSession, SessionStatus
from app.services.auth_service import AuthService, ACCESS_TOKEN_TYPE
from app.services.transcription_service import TranscriptionService
from app.websocket.manager import ws_manager

router = APIRouter(tags=["WebSocket"])
logger = logging.getLogger(__name__)
settings = get_settings()

# In-memory audio buffer per session {session_id: list[bytes]}
_audio_buffers: dict[str, list[bytes]] = {}


def clear_audio_buffer(session_id: str) -> None:
    """
    Remove the in-memory audio buffer for a recording session.

    Called by ``app.workers.transcription_tasks.process_final_transcript``
    after transcription succeeds (or on terminal failure) so that PHI audio
    is not retained in process memory beyond its useful lifetime.

    Safe to call multiple times — uses ``dict.pop`` with a default.
    """
    _audio_buffers.pop(session_id, None)


@router.websocket("/ws/recording/{session_id}")
async def recording_websocket(
    websocket: WebSocket,
    session_id: str,
    token: str | None = None,
) -> None:
    """
    WebSocket endpoint for real-time ambient recording and transcription.

    Authentication (in priority order):
      (a) Sec-WebSocket-Protocol header — client sends two subprotocols:
          ["bearer", "<jwt>"]. Server accepts with subprotocol="bearer".
      (b) ?token=<JWT> query parameter (legacy — emits deprecation warning;
          leaks JWT into proxy/access logs).

    Args:
        session_id: Recording session UUID.
        token     : Legacy JWT access token query-string fallback.

    The WebSocket protocol is documented in the module docstring.
    """
    # ------------------------------------------------------------------ #
    # Authentication — prefer Sec-WebSocket-Protocol; fall back to ?token=
    # ------------------------------------------------------------------ #
    subprotocols = list(getattr(websocket, "scope", {}).get("subprotocols", []) or [])
    auth_token: str | None = None
    auth_via_subprotocol = False

    # (a) Subprotocol auth: client sends ["bearer", "<jwt>"]
    if subprotocols:
        if len(subprotocols) >= 2 and subprotocols[0].lower() == "bearer":
            auth_token = subprotocols[1]
            auth_via_subprotocol = True

    # (b) Legacy query-string auth
    if not auth_token and token:
        auth_token = token
        logger.warning(
            "WebSocket auth via query string is deprecated and leaks JWT into "
            "access logs; use Sec-WebSocket-Protocol header."
        )

    if not auth_token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return

    try:
        payload = AuthService.decode_token(auth_token)
        if payload.get("type") != ACCESS_TOKEN_TYPE:
            await websocket.close(code=4001, reason="Invalid token type")
            return
        user_id = payload.get("sub")
    except Exception:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    # ------------------------------------------------------------------ #
    # Validate session ownership
    # ------------------------------------------------------------------ #
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        await websocket.close(code=4004, reason="Invalid session ID format")
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(RecordingSession).where(RecordingSession.id == session_uuid)
        )
        session = result.scalar_one_or_none()

    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return

    user_role = payload.get("role", "viewer")
    if str(session.user_id) != user_id and user_role != "admin":
        await websocket.close(code=4003, reason="Access denied")
        return

    if session.status not in (SessionStatus.RECORDING, SessionStatus.PAUSED):
        await websocket.close(code=4009, reason=f"Session is not active (status: {session.status.value})")
        return

    # ------------------------------------------------------------------ #
    # Connect — when auth came via Sec-WebSocket-Protocol, echo "bearer"
    # back so the browser's subprotocol handshake completes successfully.
    # ------------------------------------------------------------------ #
    if auth_via_subprotocol:
        await websocket.accept(subprotocol="bearer")
        await ws_manager.connect(websocket, session_id, accept=False)
    else:
        await ws_manager.connect(websocket, session_id)
    _audio_buffers.setdefault(session_id, [])

    await ws_manager.send_to_client(websocket, {
        "type": "connected",
        "session_id": session_id,
        "message": "WebSocket connected. Ready to receive audio chunks.",
    })

    logger.info("WS session opened: session=%s user=%s", session_id, user_id)

    # ------------------------------------------------------------------ #
    # Message processing loop
    # ------------------------------------------------------------------ #
    try:
        async with TranscriptionService() as transcription_svc:
            chunk_count = 0
            max_duration_exceeded = False

            while True:
                # Check max duration (FR-09)
                if session.start_time:
                    start = session.start_time.replace(tzinfo=timezone.utc) if session.start_time.tzinfo is None else session.start_time
                    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
                    if elapsed >= settings.RECORDING_MAX_DURATION:
                        max_duration_exceeded = True
                        await ws_manager.send_to_client(websocket, {
                            "type": "error",
                            "code": "MAX_DURATION_EXCEEDED",
                            "message": f"Maximum recording duration of {settings.RECORDING_MAX_DURATION // 60} minutes reached. Recording stopped.",
                        })
                        break

                try:
                    raw_message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                except asyncio.TimeoutError:
                    # Send keepalive ping
                    await ws_manager.send_to_client(websocket, {"type": "ping"})
                    continue

                try:
                    message = json.loads(raw_message)
                except json.JSONDecodeError:
                    await ws_manager.send_error(
                        session_id, "INVALID_JSON",
                        "Message must be valid JSON",
                        websocket=websocket,
                    )
                    continue

                msg_type = message.get("type", "")

                # -------------------------------------------------------- #
                # audio_chunk
                # -------------------------------------------------------- #
                if msg_type == "audio_chunk":
                    audio_b64 = message.get("data", "")
                    chunk_index = message.get("chunk_index", chunk_count)

                    if not audio_b64:
                        continue

                    try:
                        audio_bytes = base64.b64decode(audio_b64)
                    except Exception:
                        await ws_manager.send_error(
                            session_id, "INVALID_AUDIO",
                            "Audio data must be base64-encoded",
                            websocket=websocket,
                        )
                        continue

                    # Append to buffer
                    _audio_buffers[session_id].append(audio_bytes)
                    chunk_count += 1

                    # Also store in Redis for final transcription
                    try:
                        import redis.asyncio as aioredis
                        redis_client = aioredis.from_url(settings.REDIS_URL)
                        audio_key = f"audio:{session_id}"
                        # Append chunk to existing audio in Redis
                        existing = await redis_client.get(audio_key) or b""
                        await redis_client.setex(
                            audio_key,
                            settings.RECORDING_MAX_DURATION + 300,  # TTL with buffer
                            existing + audio_bytes,
                        )
                        await redis_client.aclose()
                    except Exception as exc:
                        logger.warning("Redis audio storage failed: %s", exc)

                    # Partial transcription of this chunk
                    try:
                        partial = await transcription_svc.transcribe_chunk(
                            audio_bytes=audio_bytes,
                            chunk_index=chunk_index,
                        )
                        await ws_manager.send_partial_transcript(
                            session_id=session_id,
                            text=partial["text"],
                            chunk_index=partial["chunk_index"],
                            language=partial.get("language", "en"),
                            confidence=partial.get("confidence"),
                        )
                    except Exception as exc:
                        logger.warning("Partial transcription error: %s", exc)
                        # Non-fatal — continue recording

                # -------------------------------------------------------- #
                # stop_recording
                # -------------------------------------------------------- #
                elif msg_type == "stop_recording":
                    await ws_manager.send_processing(session_id, "transcription")

                    # Trigger Celery task
                    try:
                        from app.workers.transcription_tasks import process_final_transcript
                        process_final_transcript.apply_async(args=[session_id])
                    except Exception as exc:
                        logger.error("Failed to enqueue transcription: %s", exc)
                        await ws_manager.send_error(
                            session_id, "PROCESSING_ERROR",
                            "Failed to start transcription pipeline",
                        )
                    break  # Exit WebSocket loop

                # -------------------------------------------------------- #
                # pause_recording
                # -------------------------------------------------------- #
                elif msg_type == "pause_recording":
                    async with AsyncSessionLocal() as db:
                        result = await db.execute(
                            select(RecordingSession).where(RecordingSession.id == session_uuid)
                        )
                        sess = result.scalar_one_or_none()
                        if sess and sess.status == SessionStatus.RECORDING:
                            sess.status = SessionStatus.PAUSED
                            await db.commit()
                    await ws_manager.send_to_client(websocket, {
                        "type": "paused",
                        "session_id": session_id,
                    })

                # -------------------------------------------------------- #
                # resume_recording
                # -------------------------------------------------------- #
                elif msg_type == "resume_recording":
                    async with AsyncSessionLocal() as db:
                        result = await db.execute(
                            select(RecordingSession).where(RecordingSession.id == session_uuid)
                        )
                        sess = result.scalar_one_or_none()
                        if sess and sess.status == SessionStatus.PAUSED:
                            sess.status = SessionStatus.RECORDING
                            await db.commit()
                    await ws_manager.send_to_client(websocket, {
                        "type": "resumed",
                        "session_id": session_id,
                    })

                # -------------------------------------------------------- #
                # ping
                # -------------------------------------------------------- #
                elif msg_type == "ping":
                    await ws_manager.send_to_client(websocket, {"type": "pong"})

    except WebSocketDisconnect:
        logger.info("WS client disconnected: session=%s", session_id)
    except Exception as exc:
        logger.error("WS error for session %s: %s", session_id, exc)
        try:
            await ws_manager.send_error(
                session_id, "INTERNAL_ERROR",
                "An internal error occurred",
                websocket=websocket,
            )
        except Exception:
            pass
    finally:
        ws_manager.disconnect(websocket, session_id)
        # Clean up in-memory buffer
        _audio_buffers.pop(session_id, None)
        logger.info("WS session closed: session=%s chunks_received=%d", session_id, chunk_count if 'chunk_count' in dir() else 0)
