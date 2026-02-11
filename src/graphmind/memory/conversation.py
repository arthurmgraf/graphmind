"""Session-based conversation memory for multi-turn dialogue."""
from __future__ import annotations
import time
import structlog
from collections import OrderedDict
from dataclasses import dataclass, field

logger = structlog.get_logger(__name__)

_MAX_SESSIONS = 1000
_SESSION_TTL = 3600  # 1 hour

@dataclass
class Message:
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)

@dataclass
class Session:
    session_id: str
    messages: list[Message] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)

    def add_message(self, role: str, content: str) -> None:
        self.messages.append(Message(role=role, content=content))
        self.last_access = time.time()

    def get_context(self, max_messages: int = 10) -> list[dict]:
        recent = self.messages[-max_messages:]
        return [{"role": m.role, "content": m.content} for m in recent]

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.last_access) > _SESSION_TTL

class ConversationStore:
    def __init__(self, max_sessions: int = _MAX_SESSIONS, ttl: int = _SESSION_TTL) -> None:
        self._sessions: OrderedDict[str, Session] = OrderedDict()
        self._max_sessions = max_sessions
        self._ttl = ttl

    def get_or_create(self, session_id: str) -> Session:
        self._evict_expired()
        if session_id in self._sessions:
            self._sessions.move_to_end(session_id)
            return self._sessions[session_id]
        session = Session(session_id=session_id)
        self._sessions[session_id] = session
        while len(self._sessions) > self._max_sessions:
            self._sessions.popitem(last=False)
        return session

    def delete(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def _evict_expired(self) -> None:
        expired = [sid for sid, s in self._sessions.items() if s.is_expired]
        for sid in expired:
            del self._sessions[sid]

    @property
    def active_sessions(self) -> int:
        self._evict_expired()
        return len(self._sessions)

_store: ConversationStore | None = None

def get_conversation_store() -> ConversationStore:
    global _store
    if _store is None:
        _store = ConversationStore()
    return _store
