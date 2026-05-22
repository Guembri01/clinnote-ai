from __future__ import annotations
"""
ClinNote AI — WebSocket Connection Manager
============================================
Manages real-time WebSocket connections for ambient recording sessions.

Each recording session has its own room identified by session_id.
Multiple clients (e.g. physician on tablet + doctor on desktop) can
observe the same session's partial transcription stream.

Message protocol:
  Client → Server:
    {"type": "audio_chunk", "data": "<base64_audio>", "chunk_index": 0}
    {"type": "stop_recording"}
    {"type": "pause_recording"}
    {"type": "resume_recording"}
    {"type": "ping"}

  Server → Client:
    {"type": "partial_transcript", "text": "...", "chunk_index": 0, "language": "en"}
    {"type": "processing", "message": "Generating SOAP note..."}
    {"type": "transcript_ready", "session_id": "...", "word_count": 150}
    {"type": "soap_ready", "note_id": "...", "session_id": "..."}
    {"type": "error", "code": "...", "message": "..."}
    {"type": "pong"}
"""


import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections grouped by recording session rooms.

    Each session can have multiple observers connected simultaneously.
    Messages broadcast to a room reach all connected clients in that room.

    Thread safety: FastAPI/Starlette runs WebSocket handlers in the same
    async event loop, so no additional locking is required for the dict.
    """

    def __init__(self) -> None:
        # session_id → list of connected WebSocket clients
        self._rooms: dict[str, list[WebSocket]] = defaultdict(list)
        # Track total connections for monitoring
        self._total_connections: int = 0

    # ------------------------------------------------------------------ #
    # Connection lifecycle
    # ------------------------------------------------------------------ #

    async def connect(
        self,
        websocket: WebSocket,
        session_id: str,
        accept: bool = True,
    ) -> None:
        """
        Register a WebSocket connection with a session room.

        Args:
            websocket  : The incoming WebSocket connection.
            session_id : Recording session UUID to associate with.
            accept     : If True (default), call ``websocket.accept()``.
                         Set False when the caller has already accepted the
                         connection (e.g. to echo a subprotocol).
        """
        if accept:
            await websocket.accept()
        self._rooms[session_id].append(websocket)
        self._total_connections += 1
        logger.info(
            "WS connect: session=%s total_in_room=%d total_connections=%d",
            session_id,
            len(self._rooms[session_id]),
            self._total_connections,
        )

    def disconnect(self, websocket: WebSocket, session_id: str) -> None:
        """
        Remove a WebSocket from a session room on disconnect.

        Args:
            websocket  : The disconnecting WebSocket.
            session_id : Session room to remove from.
        """
        room = self._rooms.get(session_id, [])
        if websocket in room:
            room.remove(websocket)
            self._total_connections = max(0, self._total_connections - 1)
            logger.info(
                "WS disconnect: session=%s remaining_in_room=%d",
                session_id,
                len(room),
            )
        # Clean up empty rooms
        if not room:
            self._rooms.pop(session_id, None)

    # ------------------------------------------------------------------ #
    # Sending messages
    # ------------------------------------------------------------------ #

    async def send_to_client(
        self,
        websocket: WebSocket,
        message: dict[str, Any],
    ) -> None:
        """
        Send a JSON message to a single WebSocket client.

        Args:
            websocket: Target WebSocket connection.
            message  : Payload dict (will be JSON-encoded).
        """
        try:
            await websocket.send_json(message)
        except Exception as exc:
            logger.warning("Failed to send WS message: %s", exc)

    async def broadcast_to_room(
        self,
        session_id: str,
        message: dict[str, Any],
        exclude: WebSocket | None = None,
    ) -> None:
        """
        Broadcast a JSON message to all clients in a session room.

        Args:
            session_id: Session room identifier.
            message   : Payload dict.
            exclude   : Optional WebSocket to exclude from broadcast.
        """
        room = self._rooms.get(session_id, [])
        disconnected: list[WebSocket] = []

        for ws in room:
            if ws is exclude:
                continue
            try:
                await ws.send_json(message)
            except Exception as exc:
                logger.warning("WS broadcast failed for one client: %s", exc)
                disconnected.append(ws)

        # Clean up any dead connections found during broadcast
        for ws in disconnected:
            self.disconnect(ws, session_id)

    async def send_partial_transcript(
        self,
        session_id: str,
        text: str,
        chunk_index: int,
        language: str = "en",
        confidence: float | None = None,
    ) -> None:
        """
        Broadcast a partial transcript result to all session observers.

        Args:
            session_id  : Session room identifier.
            text        : Partial transcript text from Whisper.
            chunk_index : Sequential chunk number.
            language    : Detected language code.
            confidence  : Whisper confidence score (optional).
        """
        message: dict[str, Any] = {
            "type": "partial_transcript",
            "text": text,
            "chunk_index": chunk_index,
            "language": language,
        }
        if confidence is not None:
            message["confidence"] = confidence
        await self.broadcast_to_room(session_id, message)

    async def send_processing(self, session_id: str, stage: str = "transcription") -> None:
        """
        Notify clients that background processing has begun.

        Args:
            session_id: Session room identifier.
            stage     : Processing stage name ("transcription" | "soap_generation").
        """
        messages = {
            "transcription": "Processing final transcript...",
            "soap_generation": "Generating SOAP note with AI...",
        }
        await self.broadcast_to_room(session_id, {
            "type": "processing",
            "stage": stage,
            "message": messages.get(stage, "Processing..."),
        })

    async def send_transcript_ready(
        self,
        session_id: str,
        transcript_id: str,
        word_count: int,
    ) -> None:
        """
        Notify clients that the final transcript is ready.

        Args:
            session_id   : Session room identifier.
            transcript_id: UUID of the created Transcript record.
            word_count   : Number of words in the transcript.
        """
        await self.broadcast_to_room(session_id, {
            "type": "transcript_ready",
            "session_id": session_id,
            "transcript_id": transcript_id,
            "word_count": word_count,
        })

    async def send_soap_ready(
        self,
        session_id: str,
        note_id: str,
    ) -> None:
        """
        Notify clients that the SOAP note generation is complete.

        Args:
            session_id: Session room identifier.
            note_id   : UUID of the created SOAPNote record.
        """
        await self.broadcast_to_room(session_id, {
            "type": "soap_ready",
            "session_id": session_id,
            "note_id": note_id,
        })

    async def send_error(
        self,
        session_id: str,
        code: str,
        message: str,
        websocket: WebSocket | None = None,
    ) -> None:
        """
        Send an error message to one client or broadcast to all.

        Args:
            session_id: Session room identifier.
            code      : Machine-readable error code.
            message   : Human-readable error description.
            websocket : Target single client (None = broadcast to all).
        """
        payload = {"type": "error", "code": code, "message": message}
        if websocket:
            await self.send_to_client(websocket, payload)
        else:
            await self.broadcast_to_room(session_id, payload)

    # ------------------------------------------------------------------ #
    # Monitoring
    # ------------------------------------------------------------------ #

    @property
    def active_sessions(self) -> list[str]:
        """Return list of session IDs with active connections."""
        return list(self._rooms.keys())

    @property
    def total_connections(self) -> int:
        """Return total count of active WebSocket connections."""
        return self._total_connections

    def session_connection_count(self, session_id: str) -> int:
        """Return number of active connections for a specific session."""
        return len(self._rooms.get(session_id, []))


# Singleton instance shared across the application
ws_manager = ConnectionManager()
