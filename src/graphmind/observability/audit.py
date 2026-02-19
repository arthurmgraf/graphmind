"""Immutable audit log for security-sensitive operations."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field

import structlog

logger = structlog.get_logger("graphmind.audit")


@dataclass
class AuditEvent:
    timestamp: float = field(default_factory=time.time)
    action: str = ""
    client_ip: str = ""
    user_id: str = ""
    request_id: str = ""
    status_code: int = 0
    response_time_ms: float = 0.0
    details: dict = field(default_factory=dict)


class AuditLogger:
    def __init__(self) -> None:
        self._logger = logging.getLogger("graphmind.audit")
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter(
                    '{"timestamp":%(created)f,"level":"%(levelname)s","audit":true,%(message)s}'
                )
            )
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

    def log(self, event: AuditEvent) -> None:
        data = asdict(event)
        pairs = ",".join(f'"{k}":{repr(v)}' for k, v in data.items())
        self._logger.info(pairs)

    def log_query(
        self,
        request_id: str,
        client_ip: str,
        question: str,
        status: int,
        elapsed_ms: float,
    ) -> None:
        self.log(
            AuditEvent(
                action="query",
                client_ip=client_ip,
                request_id=request_id,
                status_code=status,
                response_time_ms=elapsed_ms,
                details={"question": question[:200]},
            )
        )

    def log_ingest(
        self,
        request_id: str,
        client_ip: str,
        filename: str,
        status: int,
        elapsed_ms: float,
    ) -> None:
        self.log(
            AuditEvent(
                action="ingest",
                client_ip=client_ip,
                request_id=request_id,
                status_code=status,
                response_time_ms=elapsed_ms,
                details={"filename": filename},
            )
        )

    def log_auth_failure(self, client_ip: str, request_id: str) -> None:
        self.log(
            AuditEvent(
                action="auth_failure",
                client_ip=client_ip,
                request_id=request_id,
                status_code=401,
            )
        )

    def log_rate_limit(self, client_ip: str, request_id: str) -> None:
        self.log(
            AuditEvent(
                action="rate_limit_exceeded",
                client_ip=client_ip,
                request_id=request_id,
                status_code=429,
            )
        )


_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
