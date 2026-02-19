"""Lightweight regex-based prompt injection detector.

Runs synchronously before NeMo guardrails (which requires an LLM call).
Patterns are configurable via YAML.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?above",
    r"you\s+are\s+now",
    r"act\s+as\s+(if|a|an)",
    r"pretend\s+(you|to\s+be)",
    r"system\s*prompt",
    r"reveal\s+(your|the)\s+(instructions|prompt|system)",
    r"disregard\s+(all|any|previous)",
    r"forget\s+(everything|all|your)",
    r"new\s+instructions?:?\s",
    r"override\s+(previous|all|safety)",
    r"<script[^>]*>",
    r"javascript:",
    r"\r\n|\r",  # CRLF injection
    r"UNION\s+SELECT",  # SQL injection
    r";\s*DROP\s+",  # SQL injection
    r"MERGE\s*\(.*\)\s*SET",  # Cypher injection attempt
]


@dataclass
class InjectionDetectionResult:
    is_suspicious: bool = False
    matched_patterns: list[str] = field(default_factory=list)
    input_text: str = ""


class InjectionDetector:
    def __init__(self, patterns: list[str] | None = None, config_path: Path | None = None) -> None:
        if config_path and config_path.exists():
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
            self._patterns = data.get("patterns", _DEFAULT_PATTERNS)
        else:
            self._patterns = patterns or _DEFAULT_PATTERNS
        self._compiled = [re.compile(p, re.IGNORECASE) for p in self._patterns]

    def detect(self, text: str) -> InjectionDetectionResult:
        matched: list[str] = []
        for pattern, compiled in zip(self._patterns, self._compiled, strict=False):
            if compiled.search(text):
                matched.append(pattern)
        result = InjectionDetectionResult(
            is_suspicious=len(matched) > 0,
            matched_patterns=matched,
            input_text=text[:200],
        )
        if result.is_suspicious:
            logger.warning(
                "Injection detected: %d pattern(s) matched in input",
                len(matched),
            )
        return result


_detector: InjectionDetector | None = None


def get_injection_detector() -> InjectionDetector:
    global _detector
    if _detector is None:
        _detector = InjectionDetector()
    return _detector
