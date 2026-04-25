from __future__ import annotations

import asyncio
import base64
import json
import re
import uuid
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Set

import logging

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.db import get_db, init_db, make_session
from server.models import Message as MessageModel
from server.models import User
from server.models.interview_session import InterviewSession
import httpx

from server.config import settings, _cors_list_from
from server.openai_client import chat_completion, transcribe_audio
from server.services.auto_provision import ensure_interviewee, ensure_interview_session
from server.services.prompt_resolver import finalize_interview_instructions, resolve_prompt

# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------


def utc_iso() -> str:
    # Return current UTC timestamp as string
    return datetime.now(timezone.utc).isoformat()


# -----------------------------------------------------------------------------
# In-memory stores
# -----------------------------------------------------------------------------

MESSAGES: Dict[str, List[Dict[str, Any]]] = defaultdict(list)  # user_id -> list of messages
AUDIO_UPLOADS: Dict[str, Dict[str, Any]] = {}

# Allowed content types we accept from the UI
ALLOWED_AUDIO_CONTENT_TYPES = {
    "audio/webm",
    "audio/wav",
    "audio/mpeg",
    "audio/mpeg3",
    "audio/mp3",
}

# Validation constraints
MAX_MESSAGE_LENGTH = 2000


def resolved_chat_data_dir() -> Path:
    """Data directory (SQLite folder); same place as `avatar.jpg` for the login screen."""
    p = Path(settings.CHAT_DATA_DIR)
    return p if p.is_absolute() else (Path.cwd() / p)


def avatar_jpeg_path() -> Path:
    return resolved_chat_data_dir() / "avatar.jpg"


def sanitize_text(s: str) -> str:
    """Basic sanitization for incoming text.

    - Trim surrounding whitespace
    - Remove non-printable control characters (except common whitespace)
    - Collapse excessive whitespace
    """
    if s is None:
        return ""
    # Ensure string
    t = str(s).strip()
    # Remove control characters except for newlines/tabs
    t = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]+", "", t)
    # Collapse multiple whitespace into single space
    t = re.sub(r"\s+", " ", t)
    return t


class Hub:
    """
    Hub manages realtime transports for the dummy server.

    Responsibilities:
    - Track WebSocket connections by user (`ws_by_user`) so messages can
      be broadcast to all sockets belonging to a given user.
    - Track WebSocket connections by room (`ws_rooms`) for simple
      WebRTC signaling relay between peers in the same room.
    - Maintain SSE subscriber queues (`sse_queues`) per user so HTTP
      Server-Sent-Events endpoints can receive broadcast messages.

    The Hub uses an asyncio.Lock for safe concurrent modification of the
    internal mappings when multiple coroutines add/remove connections.
    """

    def __init__(self) -> None:
        # Map: user_id -> set(WebSocket)
        self.ws_by_user: Dict[str, Set[WebSocket]] = defaultdict(set)
        # Map: room_id -> set(WebSocket)
        self.ws_rooms: Dict[str, Set[WebSocket]] = defaultdict(set)

        # Map: user_id -> list(asyncio.Queue) used by SSE consumers
        self.sse_queues: Dict[str, List[asyncio.Queue]] = defaultdict(list)

        # Lock protects concurrent modifications to the maps above
        self._lock = asyncio.Lock()

    # ---------------------- WebSocket (chat) ----------------------

    async def add_ws_user(self, user_id: str, ws: WebSocket) -> None:
        """Register a new WebSocket connection for `user_id`.

        This will add the socket to the user's set so future broadcasts
        target it. Uses an async lock to avoid races when multiple
        connections are added/removed concurrently.
        """
        async with self._lock:
            self.ws_by_user[user_id].add(ws)

    async def remove_ws_user(self, user_id: str, ws: WebSocket) -> None:
        """Remove a WebSocket from a user's set and clean up empty sets."""
        async with self._lock:
            self.ws_by_user[user_id].discard(ws)
            if not self.ws_by_user[user_id]:
                self.ws_by_user.pop(user_id, None)

    async def broadcast_to_user(self, user_id: str, payload: Dict[str, Any]) -> None:
        """Broadcast a payload to all transports belonging to `user_id`.

        Sends the payload as JSON to every registered WebSocket and
        enqueues it into each SSE subscriber queue. If sending to a
        WebSocket fails the socket is removed from the Hub.
        """
        # WebSocket send is awaited to preserve ordering per-socket
        for ws in list(self.ws_by_user.get(user_id, [])):
            try:
                await ws.send_text(json.dumps(payload, ensure_ascii=False))
            except Exception:
                # If a socket is dead/unresponsive, remove it.
                await self.remove_ws_user(user_id, ws)

        # Enqueue for SSE listeners; use put_nowait because SSE consumers
        # will read at their own pace and we don't want to block here.
        for q in list(self.sse_queues.get(user_id, [])):
            try:
                q.put_nowait(payload)
            except Exception:
                # If a queue is closed or full, ignore to keep broadcasts
                # best-effort and non-blocking.
                pass

    # ---------------------- WebRTC signaling ----------------------

    async def add_ws_room(self, room_id: str, ws: WebSocket) -> None:
        """Add a WebSocket to a signaling room (for simple relay)."""
        async with self._lock:
            self.ws_rooms[room_id].add(ws)

    async def remove_ws_room(self, room_id: str, ws: WebSocket) -> None:
        """Remove a WebSocket from a signaling room and clean up."""
        async with self._lock:
            self.ws_rooms[room_id].discard(ws)
            if not self.ws_rooms[room_id]:
                self.ws_rooms.pop(room_id, None)

    async def broadcast_room(self, room_id: str, payload: Dict[str, Any], sender: WebSocket) -> None:
        """Relay a signaling payload to all members of `room_id` except the sender.

        This is used by the `/signal/{room_id}` WebSocket endpoint to
        forward SDP/ICE messages between peers. If sending to a peer
        fails we remove that socket from the room.
        """
        for ws in list(self.ws_rooms.get(room_id, [])):
            if ws is sender:
                continue
            try:
                await ws.send_text(json.dumps(payload, ensure_ascii=False))
            except Exception:
                await self.remove_ws_room(room_id, ws)


# -----------------------------------------------------------------------------
# Database helpers
# -----------------------------------------------------------------------------

hub = Hub()


async def _ensure_user(session: AsyncSession, user_id: str) -> User:
    stmt = select(User).where(User.id == user_id)
    user = await session.scalar(stmt)
    if user:
        return user

    now = datetime.now(timezone.utc)
    user = User(id=user_id, created_at=now)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _create_message(
    session: AsyncSession,
    user_id: str,
    text: str,
    role: str = "assistant",
    session_id: str | None = None,
) -> Dict[str, Any]:
    await _ensure_user(session, user_id)
    timestamp = datetime.now(timezone.utc)
    message = MessageModel(
        id=str(uuid.uuid4()),
        user_id=user_id,
        role=role,
        text=text,
        session_id=session_id,
        created_at=timestamp,
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)

    payload = {
        "id": message.id,
        "ts": message.created_at.isoformat(),
        "user_id": message.user_id,
        "role": message.role,
        "text": message.text,
    }
    MESSAGES[user_id].append(payload)
    return payload


async def _mock_transcribe_audio(payload: bytes) -> str:
    # Simulate STT latency and deterministic failure trigger for testing
    await asyncio.sleep(0)
    if b"trigger-stt-error" in payload:
        raise RuntimeError("STT worker failed")
    return f"Transcribed audio ({len(payload)} bytes)"


async def _process_audio_ingest(ingest_id: str, user_id: str, audio_bytes: bytes) -> None:
    record = AUDIO_UPLOADS.get(ingest_id)
    if not record:
        return

    try:
        # Prefer real OpenAI transcription when API key is configured; fall back to mock
        try:
            transcript = await transcribe_audio(audio_bytes, filename=record.get("metadata", {}).get("filename") or "audio.webm")
        except Exception:
            transcript = await _mock_transcribe_audio(audio_bytes)
        await init_db()
        async with make_session() as session:
            assistant_msg = await _create_message(session, user_id, transcript, role="assistant")
        await hub.broadcast_to_user(user_id, {"type": "message", "data": assistant_msg})

        record.update(
            {
                "status": "completed",
                "transcript": transcript,
                "assistant_message": assistant_msg,
                "completed_at": utc_iso(),
            }
        )
    except Exception as exc:  # pragma: no cover - triggered in tests only via sentinel
        record.update(
            {
                "status": "failed",
                "error": str(exc),
                "completed_at": utc_iso(),
            }
        )


# -----------------------------------------------------------------------------
# FastAPI app
# -----------------------------------------------------------------------------

app = FastAPI(title="Realtime Interview Chat Bot")

# Configure simple logger for debug/info messages used during local development
logger = logging.getLogger("bkp-server")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


@app.on_event("startup")
async def startup_db() -> None:
    await init_db()
    logger.info("Waiting for application startup.")
    if getattr(settings, "ENABLE_AUTO_ASSESS", False):
        asyncio.create_task(_auto_assess_loop())


async def _auto_assess_loop() -> None:
    """Background loop: complete sessions idle >1 hour, trigger assessment."""
    from server.models.interview_session import InterviewSession as IS
    from server.models.invite_link import InviteLink
    from server.models.message import Message as MsgModel
    from server.services.assessment_service import assess_session as _assess

    while True:
        await asyncio.sleep(600)  # run every 10 minutes
        try:
            async with make_session() as db:
                now = datetime.now(timezone.utc)
                stale_cutoff = now - timedelta(hours=1)
                stale_sessions = list(
                    await db.scalars(
                        select(IS).where(IS.status == "in_progress")
                    )
                )
                for sess in stale_sessions:
                    last_msg = await db.scalar(
                        select(MsgModel)
                        .where(MsgModel.session_id == sess.id)
                        .order_by(MsgModel.created_at.desc())
                    )
                    ref_time = last_msg.created_at if last_msg else sess.started_at
                    if ref_time and ref_time < stale_cutoff:
                        user_msgs = list(
                            await db.scalars(
                                select(MsgModel).where(
                                    MsgModel.session_id == sess.id,
                                    MsgModel.role == "user",
                                )
                            )
                        )
                        if not user_msgs:
                            sess.status = "abandoned"
                            if sess.invite_token:
                                link = await db.scalar(
                                    select(InviteLink).where(
                                        InviteLink.token == sess.invite_token
                                    )
                                )
                                if link and link.used_attempts > 0:
                                    link.used_attempts -= 1
                                    if link.status == "exhausted" and link.used_attempts < link.max_attempts:
                                        link.status = "active"
                        else:
                            sess.status = "completed"
                        sess.ended_at = now
                        if sess.started_at:
                            sess.duration_seconds = int(
                                (now - sess.started_at).total_seconds()
                            )
                        await db.commit()
                        if sess.status == "completed":
                            try:
                                await _assess(db, sess.id)
                            except Exception as exc:
                                logger.warning(
                                    "Auto-assess failed for %s: %s", sess.id, exc
                                )
        except Exception as exc:
            logger.error("Auto-assess loop error: %s", exc)


try:
    from server.config import settings

    cors_allowed = _cors_list_from(settings)
except Exception:
    cors_allowed = ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from server.routes.assessments import public_router as assessments_public_router
from server.routes.invites import router as invites_router
from server.routes.auth import router as auth_router
from server.routes.knowledge import router as knowledge_router, public_router as knowledge_public_router
from server.routes.onboarding import router as onboarding_router, employee_router as onboarding_employee_router

app.include_router(assessments_public_router)
app.include_router(invites_router)
app.include_router(auth_router)
app.include_router(knowledge_router)
app.include_router(knowledge_public_router)
app.include_router(onboarding_router)
app.include_router(onboarding_employee_router)

# -----------------------------------------------------------------------------
# Health / basic routes
# -----------------------------------------------------------------------------


@app.get("/")
async def root():
    return {"ok": True, "service": "dummy-realtime", "time": utc_iso()}


@app.get("/api/health")
async def health_check():
    """Health check endpoint for monitoring and load balancers."""
    return {
        "ok": True,
        "status": "healthy",
        "service": "chat-realtime",
        "timestamp": utc_iso(),
        "version": "1.0.0",
    }


@app.get("/api/branding/avatar")
async def get_login_avatar():
    """JPEG shown on the email login screen. Place `avatar.jpg` in CHAT_DATA_DIR (e.g. chat_data/)."""
    path = avatar_jpeg_path()
    if not path.is_file():
        raise HTTPException(status_code=404, detail="avatar.jpg not found")
    return FileResponse(path, media_type="image/jpeg", filename="avatar.jpg")


# -----------------------------------------------------------------------------
# REST endpoints
# -----------------------------------------------------------------------------


@app.get("/api/history/{user_id}")
async def get_history(user_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(MessageModel).where(MessageModel.user_id == user_id).order_by(MessageModel.created_at.asc())
    results = await db.scalars(stmt)
    messages = [
        {
            "id": m.id,
            "ts": m.created_at.isoformat(),
            "user_id": m.user_id,
            "role": m.role,
            "text": m.text,
        }
        for m in results
    ]
    return {"user_id": user_id, "messages": messages[-200:]}


@app.patch("/api/user/{user_id}")
async def update_user(user_id: str, payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    user = await _ensure_user(db, user_id)
    display_name = payload.get("display_name")
    if display_name is not None:
        user.display_name = str(display_name).strip()[:128]
        await db.commit()
    return {"ok": True, "user_id": user.id, "display_name": user.display_name}


_chat_service: "ChatService | None" = None


def _get_chat_service():
    global _chat_service
    if _chat_service is None:
        from server.services.chat_service import ChatService
        _chat_service = ChatService()
    return _chat_service


@app.post("/api/message")
async def post_message(payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    user_id = str(payload.get("user_id", "")).strip()
    text = sanitize_text(payload.get("text", ""))

    if not user_id or not text:
        raise HTTPException(status_code=400, detail="user_id and text are required")

    if len(text) > MAX_MESSAGE_LENGTH:
        raise HTTPException(status_code=400, detail=f"text exceeds max length of {MAX_MESSAGE_LENGTH} characters")

    client_locale = str(payload.get("locale") or "").strip() or "ru"

    # no_reply: save user message only (used by voice transcripts)
    if payload.get("no_reply"):
        user_msg = await _create_message(db, user_id, text, role="user")
        return {"ok": True, "message": user_msg}

    svc = _get_chat_service()
    card = await svc.handle_message(db, user_id, text, locale=client_locale)
    logger.info(f"ChatService reply card_type={card.card_type} user={user_id}")

    return {
        "ok": True,
        "reply": card.text,
        "card_type": card.card_type,
        "metadata": card.metadata,
    }


@app.post("/api/chat")
async def api_chat(payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    """Handle chat-style requests from the UI.

    Expected payload shape: { "user_id": "<id>", "messages": [ {"role": "user|assistant", "content": "..."}, ... ] }

    Behavior:
    - Append provided messages to the in-memory `MESSAGES` store for `user_id`.
    - Generate a simple echo reply (assistant) and persist it.
    - Broadcast the assistant reply to connected transports via `Hub.broadcast_to_user`.
    - Return `{ "reply": "..." }` to the caller.
    """
    user_id = str(payload.get("user_id") or payload.get("userId") or "").strip()
    msgs = payload.get("messages") or []

    if not isinstance(msgs, list) or not msgs:
        raise HTTPException(status_code=400, detail="messages must be a non-empty list")

    # Try to infer user_id from first message if not provided
    if not user_id:
        first = msgs[0]
        if isinstance(first, dict):
            user_id = str(first.get("user_id") or first.get("userId") or "").strip() or "guest"
        else:
            user_id = "guest"

    stored = []
    for m in msgs:
        if isinstance(m, dict):
            role = m.get("role") or "user"
            text = sanitize_text(m.get("content") or m.get("text") or "")
        else:
            role = "user"
            text = str(m)

        if len(str(text)) > MAX_MESSAGE_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"message content exceeds max length of {MAX_MESSAGE_LENGTH} characters",
            )

        stored_msg = await _create_message(db, user_id, str(text), role=role)
        stored.append(stored_msg)

    # Simple echo reply: find last user message text
    last_user_text = ""
    for m in reversed(msgs):
        if isinstance(m, dict) and (m.get("role") == "user"):
            last_user_text = m.get("content") or m.get("text") or ""
            break

    reply_text = f"Echo: {last_user_text or 'ok'}"
    assistant_msg = await _create_message(db, user_id, reply_text, role="assistant")

    # Broadcast reply to connected clients (best-effort)
    try:
        await hub.broadcast_to_user(user_id, {"type": "message", "data": assistant_msg})
    except Exception:
        await asyncio.sleep(0)

    return {"ok": True, "reply": reply_text}


@app.post("/api/audio")
async def upload_audio(
    background_tasks: BackgroundTasks,
    user_id: str = Form(...),
    audio: UploadFile = File(...),
    duration: float | None = Form(None),
    metadata: str | None = Form(None),
):
    parsed_user_id = str(user_id or "").strip()
    if not parsed_user_id:
        logger.info(f"POST /api/audio 400 Bad Request - missing user_id")
        raise HTTPException(status_code=400, detail="user_id is required")

    raw_content_type = (audio.content_type or "")
    logger.info(f"POST /api/audio raw Content-Type: {raw_content_type}")
    # Strip any parameters (e.g., ;codecs=opus) so we match against allowed types
    content_type = raw_content_type.split(";", 1)[0].strip().lower()
    if content_type not in ALLOWED_AUDIO_CONTENT_TYPES:
        logger.info(f"POST /api/audio 400 Bad Request - unsupported content type: {raw_content_type}")
        raise HTTPException(status_code=400, detail=f"Unsupported content type: {raw_content_type}")

    payload = await audio.read()
    if not payload:
        logger.info("POST /api/audio 400 Bad Request - empty payload")
        raise HTTPException(status_code=400, detail="audio payload cannot be empty")

    ingest_id = str(uuid.uuid4())
    record = {
        "ingest_id": ingest_id,
        "user_id": parsed_user_id,
        "status": "processing",
        "ingest_at": utc_iso(),
        "metadata": {
            "filename": audio.filename,
            "content_type": content_type,
            "size": len(payload),
            "duration": duration,
            "notes": metadata,
        },
    }
    AUDIO_UPLOADS[ingest_id] = record

    background_tasks.add_task(_process_audio_ingest, ingest_id, parsed_user_id, payload)

    return JSONResponse(
        status_code=202,
        content={
            "ok": True,
            "ingest_id": ingest_id,
            "status": record["status"],
            "ingest_at": record["ingest_at"],
        },
    )


@app.get("/api/audio/{ingest_id}")
async def get_audio_status(ingest_id: str):
    record = AUDIO_UPLOADS.get(ingest_id)
    if not record:
        raise HTTPException(status_code=404, detail="audio ingest not found")
    return record


# -----------------------------------------------------------------------------
# Realtime voice (SDP proxy for OpenAI GA Realtime API)
# -----------------------------------------------------------------------------


@app.post("/api/realtime/session")
async def realtime_session(request: Request, user_id: str = "guest", locale: str = ""):
    """Proxy SDP offer to OpenAI Realtime API; return SDP answer + DB context.

    Query params:
        user_id — identifies the user so we can load chat history from DB.
        locale  — client UI locale (e.g. "en", "ru") to select interview language.

    The browser sends its SDP offer (Content-Type: application/sdp).
    Server loads conversation history from DB, forwards the SDP to OpenAI,
    and returns JSON ``{"sdp": "...", "context": [...]}`` so the client can
    inject prior turns via the data channel.
    """
    logger.info(f"POST /api/realtime/session called (user_id={user_id})")

    if not settings.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is not configured")
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured")

    body = await request.body()
    sdp_offer = body.decode("utf-8", errors="replace").strip()
    if not sdp_offer.endswith("\r\n"):
        sdp_offer += "\r\n"
    logger.info(f"Received SDP offer ({len(sdp_offer)} bytes)")

    if not sdp_offer or not sdp_offer.startswith("v="):
        logger.error("Invalid SDP offer")
        raise HTTPException(status_code=400, detail="Invalid SDP offer: must start with 'v='")

    client_locale = locale.strip() or None
    context: List[Dict[str, str]] = []
    instructions = finalize_interview_instructions(settings.OPENAI_REALTIME_INSTRUCTIONS, locale=client_locale)
    session_id: str | None = None
    try:
        await init_db()
        async with make_session() as db:
            stmt = (
                select(MessageModel)
                .where(MessageModel.user_id == user_id)
                .order_by(MessageModel.created_at.desc())
                .limit(20)
            )
            rows = list(await db.scalars(stmt))
            rows.reverse()
            context = [{"role": m.role, "text": m.text} for m in rows]

            # Resolve prompt via new priority chain
            instructions = await resolve_prompt(db, user_id=user_id, locale=client_locale)

            # Auto-provision interviewee + session
            interviewee = await ensure_interviewee(db, user_id)
            interview_session = await ensure_interview_session(
                db, interviewee, session_type="voice", prompt_used=instructions,
            )
            await db.commit()
            session_id = interview_session.id

        logger.info(f"Loaded {len(context)} history messages for user_id={user_id}")
    except Exception as exc:
        logger.warning(f"Failed to load history: {exc}")

    session_config = json.dumps({
        "type": "realtime",
        "model": settings.OPENAI_REALTIME_MODEL,
        "instructions": instructions,
        "audio": {
            "input": {
                "transcription": {
                    "model": "gpt-4o-mini-transcribe",
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": settings.REALTIME_VAD_THRESHOLD,
                    "prefix_padding_ms": settings.REALTIME_VAD_PREFIX_MS,
                    "silence_duration_ms": settings.REALTIME_VAD_SILENCE_MS,
                    "create_response": True,
                    "interrupt_response": settings.REALTIME_INTERRUPT_RESPONSE,
                },
            },
            "output": {
                "voice": settings.OPENAI_REALTIME_VOICE,
            },
        },
    })

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            boundary = uuid.uuid4().hex
            sdp_bytes = sdp_offer.encode("utf-8")
            session_bytes = session_config.encode("utf-8")

            body_parts = b"".join([
                f"--{boundary}\r\n".encode(),
                b'Content-Disposition: form-data; name="sdp"\r\n',
                b"Content-Type: text/plain;charset=UTF-8\r\n",
                b"\r\n",
                sdp_bytes,
                b"\r\n",
                f"--{boundary}\r\n".encode(),
                b'Content-Disposition: form-data; name="session"\r\n',
                b"Content-Type: text/plain;charset=UTF-8\r\n",
                b"\r\n",
                session_bytes,
                b"\r\n",
                f"--{boundary}--\r\n".encode(),
            ])

            resp = await client.post(
                settings.OPENAI_REALTIME_URL,
                headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                },
                content=body_parts,
            )
        logger.info(f"OpenAI response status: {resp.status_code}")
        if not resp.is_success:
            logger.error(f"OpenAI error response: {resp.text[:500]}")
    except httpx.TimeoutException:
        logger.error("OpenAI Realtime API timed out")
        raise HTTPException(status_code=504, detail="OpenAI Realtime API timed out")
    except Exception as exc:
        logger.error(f"Failed to reach OpenAI: {exc}")
        raise HTTPException(status_code=502, detail=f"Failed to reach OpenAI: {exc}")

    if not resp.is_success:
        logger.error(f"OpenAI returned error: {resp.status_code} - {resp.text[:200]}")
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    answer_sdp = resp.text
    logger.info(f"SDP answer received ({len(answer_sdp)} bytes)")

    return JSONResponse(content={"sdp": answer_sdp, "context": context, "session_id": session_id})


# -----------------------------------------------------------------------------
# SSE endpoint
# -----------------------------------------------------------------------------


@app.get("/sse/{user_id}")
async def sse(user_id: str, request: Request):
    q: asyncio.Queue = asyncio.Queue()
    hub.sse_queues[user_id].append(q)

    async def event_gen():
        # Send a "hello" event
        await q.put({"type": "sse_hello", "data": {"ts": utc_iso(), "note": "connected"}})

        try:
            while True:
                # If no data within 25s, send a keepalive comment
                try:
                    item = await asyncio.wait_for(q.get(), timeout=25)
                    yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive {utc_iso()}\n\n"

                if await request.is_disconnected():
                    break
        finally:
            try:
                hub.sse_queues[user_id].remove(q)
            except ValueError:
                pass

    headers = {
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_gen(), media_type="text/event-stream", headers=headers)


# -----------------------------------------------------------------------------
# WebSocket (chat) endpoint
# -----------------------------------------------------------------------------


@app.websocket("/ws/{user_id}")
async def ws_chat(websocket: WebSocket, user_id: str):
    await websocket.accept()
    logger.info(f"WebSocket /ws/{user_id} accepted")
    await hub.add_ws_user(user_id, websocket)
    logger.info("connection open")

    # Send a greeting
    await websocket.send_text(json.dumps({"type": "ws_hello", "data": {"ts": utc_iso(), "user_id": user_id}}))

    audio_buf = bytearray()
    try:
        while True:
            msg = await websocket.receive()
            # msg is a dict with keys like 'type' and either 'text' or 'bytes'
            if msg.get("type") == "websocket.receive":
                if "text" in msg and msg["text"] is not None:
                    raw = msg["text"]
                    logger.info(f"WS recv text from {user_id}: {raw}")
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        payload = {"type": "text", "data": {"text": raw}}

                    mtype = payload.get("type")

                    if mtype == "ping":
                        out = json.dumps({"type": "pong", "ts": utc_iso()})
                        logger.info(f"WS send to {user_id}: {out}")
                        await websocket.send_text(out)
                        continue

                    if mtype == "message":
                        # Echo back
                        out = json.dumps({"type": "echo", "data": payload.get("data")}, ensure_ascii=False)
                        logger.info(f"WS send to {user_id}: {out}")
                        await websocket.send_text(out)
                        # Also broadcast to the same user's channels
                        await hub.broadcast_to_user(
                            user_id,
                            {
                                "type": "message",
                                "data": {
                                    **(payload.get("data") or {}),
                                    "echoed": True,
                                    "ts": utc_iso(),
                                },
                            },
                        )
                        continue

                    if mtype == "audio_start":
                        # begin fresh buffer
                        audio_buf = bytearray()
                        out = json.dumps({"type": "ack", "data": {"msg": "audio_started"}, "ts": utc_iso()})
                        logger.info(f"WS send to {user_id}: {out}")
                        await websocket.send_text(out)
                        continue

                    if mtype == "audio_end":
                        # For testing: send a deterministic test transcript, persist an assistant
                        # message so the UI displays it, then send a special end-of-stream sign
                        # and close the WebSocket from the server side.
                        try:
                            # Return the requested test transcript string
                            transcript = "test1, test2, ...."

                            # Persist assistant message and broadcast so UI shows it in chat
                            try:
                                await init_db()
                                async with make_session() as session:
                                    assistant_msg = await _create_message(session, user_id, transcript, role="assistant")
                                # Broadcast assistant message to user's channels
                                await hub.broadcast_to_user(user_id, {"type": "message", "data": assistant_msg})
                            except Exception:
                                # If DB persistence fails, continue but still send the transcript
                                await asyncio.sleep(0)

                            out = json.dumps({"type": "audio_result", "data": {"transcript": transcript}}, ensure_ascii=False)
                            logger.info(f"WS send to {user_id}: {out}")
                            await websocket.send_text(out)

                            # Send a special end-of-stream message so client can detect the end
                            # of the current audio ingest. Keep the WebSocket connection open
                            # so the client and server can continue exchanging messages.
                            out2 = json.dumps({"type": "audio_stream_closed", "data": {"note": "server_sent_end"}}, ensure_ascii=False)
                            logger.info(f"WS send to {user_id}: {out2}")
                            await websocket.send_text(out2)
                        except Exception:
                            # Best-effort fallback: report failure then continue
                            try:
                                await websocket.send_text(
                                    json.dumps({"type": "audio_result", "data": {"transcript": None, "error": "transcription_failed"}})
                                )
                            except Exception:
                                pass
                        finally:
                            audio_buf = bytearray()
                        continue

                    # Unknown text message -> acknowledge
                    out = json.dumps({"type": "ack", "data": payload, "ts": utc_iso()}, ensure_ascii=False)
                    logger.info(f"WS send to {user_id}: {out}")
                    await websocket.send_text(out)

                elif "bytes" in msg and msg["bytes"] is not None:
                    # append binary audio chunk
                    chunk = msg["bytes"]
                    logger.info(f"WS recv binary from {user_id}: {len(chunk)} bytes")
                    audio_buf.extend(chunk)
                    # optionally ack receiving chunk
                    continue

            if msg.get("type") == "websocket.disconnect":
                break

    except WebSocketDisconnect:
        # Client closed connection
        await hub.remove_ws_user(user_id, websocket)
        logger.info("connection closed")
    except Exception:
        await hub.remove_ws_user(user_id, websocket)
        await asyncio.sleep(0)


# -----------------------------------------------------------------------------
# Minimal WebRTC signaling via WebSocket
# -----------------------------------------------------------------------------


@app.websocket("/signal/{room_id}")
async def ws_signal(websocket: WebSocket, room_id: str):
    await websocket.accept()
    await hub.add_ws_room(room_id, websocket)
    await websocket.send_text(json.dumps({"type": "signal_hello", "room": room_id, "ts": utc_iso()}))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"type": "raw", "data": raw}

            payload.setdefault("ts", utc_iso())
            await hub.broadcast_room(room_id, payload, sender=websocket)

    except WebSocketDisconnect:
        await hub.remove_ws_room(room_id, websocket)
    except Exception:
        await hub.remove_ws_room(room_id, websocket)
        await asyncio.sleep(0)


# -----------------------------------------------------------------------------
# Сlear everything
# -----------------------------------------------------------------------------


@app.post("/__dev__/reset")
async def dev_reset():
    await init_db()
    # Clear messages
    MESSAGES.clear()
    async with make_session() as session:
        await session.execute(delete(MessageModel))
        await session.execute(delete(User))
        await session.commit()
    return {"ok": True, "reset_at": utc_iso()}


# =============================================================================
# Main entry point
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    try:
        debug = settings.DEBUG
    except Exception:
        debug = True
    logger.info(f"Starting server in {'DEBUG' if debug else 'PRODUCTION'} mode")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=debug, log_level="debug" if debug else "info")


@app.get("/ws/{user_id}")
async def ws_http_fallback(user_id: str, request: Request):
    """Return a helpful JSON response for clients that requested the WebSocket
    path over plain HTTP (common when ws/wss is misconfigured). This prevents a
    404 and gives actionable guidance.
    """
    return JSONResponse(
        status_code=400,
        content={
            "ok": False,
            "error": "This endpoint expects a WebSocket (ws:// or wss://). Connect using a WebSocket client.",
            "hint": "If you intended to use Server-Sent Events, use /sse/{user_id}.",
        },
    )


@app.get("/signal/{room_id}")
async def signal_http_fallback(room_id: str, request: Request):
    return JSONResponse(
        status_code=400,
        content={
            "ok": False,
            "error": "This endpoint expects a WebSocket (ws:// or wss://) for signaling.",
            "hint": "Use a WebSocket client to connect to /signal/{room_id}.",
        },
    )
