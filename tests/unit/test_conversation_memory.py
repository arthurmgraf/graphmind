from __future__ import annotations

from unittest.mock import patch

from graphmind.memory.conversation import ConversationStore, Message, Session


class TestSession:
    def test_add_message(self):
        session = Session(session_id="s1")
        session.add_message("user", "hello")
        assert len(session.messages) == 1
        assert session.messages[0].role == "user"
        assert session.messages[0].content == "hello"

    def test_add_multiple_messages(self):
        session = Session(session_id="s1")
        session.add_message("user", "question")
        session.add_message("assistant", "answer")
        session.add_message("user", "follow-up")
        assert len(session.messages) == 3

    def test_get_context_returns_messages_in_order(self):
        session = Session(session_id="s1")
        session.add_message("user", "first")
        session.add_message("assistant", "second")
        session.add_message("user", "third")
        context = session.get_context()
        assert context == [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "second"},
            {"role": "user", "content": "third"},
        ]

    def test_get_context_respects_max_messages(self):
        session = Session(session_id="s1")
        for i in range(15):
            session.add_message("user", f"msg-{i}")
        context = session.get_context(max_messages=5)
        assert len(context) == 5
        assert context[0]["content"] == "msg-10"
        assert context[-1]["content"] == "msg-14"

    def test_is_expired_false_for_fresh_session(self):
        session = Session(session_id="s1")
        assert session.is_expired is False

    def test_is_expired_true_after_ttl(self):
        session = Session(session_id="s1")
        # Simulate session created long ago
        with patch("graphmind.memory.conversation.time") as mock_time:
            mock_time.time.return_value = session.last_access + 3601
            assert session.is_expired is True


class TestConversationStore:
    def test_get_or_create_returns_session(self):
        store = ConversationStore()
        session = store.get_or_create("s1")
        assert isinstance(session, Session)
        assert session.session_id == "s1"

    def test_get_or_create_returns_same_session(self):
        store = ConversationStore()
        s1 = store.get_or_create("s1")
        s1.add_message("user", "hello")
        s2 = store.get_or_create("s1")
        assert s1 is s2
        assert len(s2.messages) == 1

    def test_adding_messages_to_session(self):
        store = ConversationStore()
        session = store.get_or_create("s1")
        session.add_message("user", "What is LangGraph?")
        session.add_message("assistant", "LangGraph is a framework.")
        context = session.get_context()
        assert len(context) == 2
        assert context[0]["role"] == "user"
        assert context[1]["role"] == "assistant"

    def test_active_sessions_count(self):
        store = ConversationStore()
        store.get_or_create("s1")
        store.get_or_create("s2")
        assert store.active_sessions == 2

    def test_delete_session(self):
        store = ConversationStore()
        store.get_or_create("s1")
        assert store.active_sessions == 1
        result = store.delete("s1")
        assert result is True
        assert store.active_sessions == 0

    def test_delete_nonexistent_session_returns_false(self):
        store = ConversationStore()
        result = store.delete("no-such-session")
        assert result is False

    def test_max_sessions_eviction(self):
        store = ConversationStore(max_sessions=2)
        store.get_or_create("s1")
        store.get_or_create("s2")
        assert store.active_sessions == 2

        # Adding a third session should evict the oldest (s1)
        store.get_or_create("s3")
        assert store.active_sessions == 2
        assert "s1" not in store._sessions
        assert "s2" in store._sessions
        assert "s3" in store._sessions

    def test_ttl_expiration_evicts_sessions(self):
        # Session.is_expired uses the module-level _SESSION_TTL (3600s),
        # so we patch it to a short value for testing.
        with patch("graphmind.memory.conversation._SESSION_TTL", 60):
            store = ConversationStore(ttl=60)
            s1 = store.get_or_create("s1")
            last_access = s1.last_access

            # Simulate time passing beyond the patched TTL
            with patch("graphmind.memory.conversation.time") as mock_time:
                mock_time.time.return_value = last_access + 61
                # get_or_create calls _evict_expired internally
                store.get_or_create("s2")
                assert "s1" not in store._sessions

    def test_accessing_session_moves_to_end(self):
        store = ConversationStore(max_sessions=2)
        store.get_or_create("s1")
        store.get_or_create("s2")

        # Access s1 again so it moves to the end (most recently used)
        store.get_or_create("s1")

        # Now adding s3 should evict s2 (the oldest), not s1
        store.get_or_create("s3")
        assert "s1" in store._sessions
        assert "s2" not in store._sessions
        assert "s3" in store._sessions


class TestMessage:
    def test_message_fields(self):
        msg = Message(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert isinstance(msg.timestamp, float)
