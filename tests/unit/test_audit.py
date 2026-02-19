from __future__ import annotations

import logging
from unittest.mock import MagicMock

from graphmind.observability.audit import AuditEvent, AuditLogger


class TestAuditEvent:
    def test_default_values(self):
        event = AuditEvent()
        assert event.action == ""
        assert event.client_ip == ""
        assert event.user_id == ""
        assert event.request_id == ""
        assert event.status_code == 0
        assert event.response_time_ms == 0.0
        assert event.details == {}
        assert isinstance(event.timestamp, float)

    def test_custom_values(self):
        event = AuditEvent(
            action="query",
            client_ip="192.168.1.1",
            user_id="user-42",
            request_id="req-abc",
            status_code=200,
            response_time_ms=123.4,
            details={"question": "What is Neo4j?"},
        )
        assert event.action == "query"
        assert event.client_ip == "192.168.1.1"
        assert event.user_id == "user-42"
        assert event.request_id == "req-abc"
        assert event.status_code == 200
        assert event.response_time_ms == 123.4
        assert event.details["question"] == "What is Neo4j?"


class TestAuditLogger:
    def _make_logger_with_mock(self):
        """Create an AuditLogger and replace its internal logger with a mock."""
        audit_logger = AuditLogger()
        mock_internal = MagicMock(spec=logging.Logger)
        audit_logger._logger = mock_internal
        return audit_logger, mock_internal

    def test_log_query_creates_entry(self):
        audit_logger, mock_internal = self._make_logger_with_mock()
        audit_logger.log_query(
            request_id="req-1",
            client_ip="10.0.0.1",
            question="What is LangGraph?",
            status=200,
            elapsed_ms=42.5,
        )
        mock_internal.info.assert_called_once()
        logged_msg = mock_internal.info.call_args[0][0]
        assert "query" in logged_msg
        assert "req-1" in logged_msg
        assert "10.0.0.1" in logged_msg

    def test_log_ingest_creates_entry(self):
        audit_logger, mock_internal = self._make_logger_with_mock()
        audit_logger.log_ingest(
            request_id="req-2",
            client_ip="10.0.0.2",
            filename="document.pdf",
            status=201,
            elapsed_ms=150.0,
        )
        mock_internal.info.assert_called_once()
        logged_msg = mock_internal.info.call_args[0][0]
        assert "ingest" in logged_msg
        assert "req-2" in logged_msg
        assert "document.pdf" in logged_msg

    def test_log_auth_failure_creates_entry(self):
        audit_logger, mock_internal = self._make_logger_with_mock()
        audit_logger.log_auth_failure(
            client_ip="10.0.0.3",
            request_id="req-3",
        )
        mock_internal.info.assert_called_once()
        logged_msg = mock_internal.info.call_args[0][0]
        assert "auth_failure" in logged_msg
        assert "req-3" in logged_msg
        assert "401" in logged_msg

    def test_log_rate_limit_creates_entry(self):
        audit_logger, mock_internal = self._make_logger_with_mock()
        audit_logger.log_rate_limit(
            client_ip="10.0.0.4",
            request_id="req-4",
        )
        mock_internal.info.assert_called_once()
        logged_msg = mock_internal.info.call_args[0][0]
        assert "rate_limit_exceeded" in logged_msg
        assert "req-4" in logged_msg
        assert "429" in logged_msg

    def test_log_dispatches_to_underlying_logger(self):
        audit_logger, mock_internal = self._make_logger_with_mock()
        event = AuditEvent(
            action="custom_action",
            client_ip="127.0.0.1",
            request_id="req-99",
            status_code=200,
        )
        audit_logger.log(event)
        mock_internal.info.assert_called_once()

    def test_log_query_truncates_long_question(self):
        audit_logger, mock_internal = self._make_logger_with_mock()
        long_question = "x" * 500
        audit_logger.log_query(
            request_id="req-5",
            client_ip="10.0.0.5",
            question=long_question,
            status=200,
            elapsed_ms=10.0,
        )
        mock_internal.info.assert_called_once()
        logged_msg = mock_internal.info.call_args[0][0]
        # The log_query method truncates to 200 chars via question[:200]
        # Verify the full 500-char question is NOT in the log
        assert "x" * 500 not in logged_msg

    def test_multiple_log_calls_are_independent(self):
        audit_logger, mock_internal = self._make_logger_with_mock()
        audit_logger.log_query("r1", "1.1.1.1", "q1", 200, 10.0)
        audit_logger.log_query("r2", "2.2.2.2", "q2", 200, 20.0)
        assert mock_internal.info.call_count == 2
