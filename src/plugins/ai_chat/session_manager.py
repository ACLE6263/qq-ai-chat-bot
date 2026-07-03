"""Conversation history management with sliding window and LRU eviction."""

import time
from collections import OrderedDict
from typing import Dict, List, Optional

from src.config import config


class SessionManager:
    """Manages per-user/group conversation history in memory.

    Session ID scheme:
    - Private chat: user_id
    - Group chat (shared context): group_id
    - Group chat (per-user context): f"{group_id}:{user_id}" (future)

    Features:
    - Sliding window: keeps at most max_history_turns * 2 messages
    - LRU eviction: drops oldest sessions when total exceeds max_sessions
    - Token estimation: rough ~1.5 chars/token heuristic for Chinese/English
    """

    def __init__(self) -> None:
        # session_id -> list of {"role", "content", "tokens", "timestamp"}
        self._sessions: Dict[str, list] = {}
        # Access order for LRU eviction
        self._access_order: OrderedDict[str, float] = OrderedDict()

        self.max_turns: int = config.max_history_turns
        self.max_sessions: int = 1000

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Append a message to the session and truncate if over max_turns."""
        history = self._get_or_create_session(session_id)

        estimated_tokens = max(1, len(content) // 2)  # ~2 chars/token

        history.append({
            "role": role,
            "content": content,
            "tokens": estimated_tokens,
            "timestamp": time.time(),
        })

        # Truncate to max_turns * 2 messages (each turn = user + assistant)
        max_messages = self.max_turns * 2
        while len(history) > max_messages:
            history.pop(0)

    def get_context(self, session_id: str) -> List[Dict[str, str]]:
        """Return the conversation context suitable for LLM API call.

        Only includes role and content fields (no internal metadata).
        """
        history = self._get_or_create_session(session_id)
        return [
            {"role": m["role"], "content": m["content"]}
            for m in history
        ]

    def reset_session(self, session_id: str) -> None:
        """Clear all history for a session."""
        self._sessions.pop(session_id, None)
        self._access_order.pop(session_id, None)

    def get_session_stats(self, session_id: str) -> dict:
        """Return token and message counts for a session."""
        history = self._sessions.get(session_id, [])
        total_tokens = sum(m.get("tokens", 0) for m in history)
        return {
            "message_count": len(history),
            "total_tokens": total_tokens,
            "turn_count": len(history) // 2,
        }

    def get_total_active_sessions(self) -> int:
        return len(self._sessions)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _get_or_create_session(self, session_id: str) -> list:
        """Get existing session or create a new one with LRU eviction."""
        if session_id not in self._sessions:
            # Evict oldest if at capacity
            if len(self._sessions) >= self.max_sessions:
                oldest_id, _ = self._access_order.popitem(last=False)
                self._sessions.pop(oldest_id, None)

            self._sessions[session_id] = []

        # Touch access order
        self._access_order.pop(session_id, None)
        self._access_order[session_id] = time.time()

        return self._sessions[session_id]


# Module-level singleton
session_manager = SessionManager()
