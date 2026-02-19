from __future__ import annotations

import logging
from pathlib import Path

from graphmind.config import get_settings

logger = logging.getLogger(__name__)

_rails = None


async def get_rails():
    global _rails
    if _rails is not None:
        return _rails

    try:
        from nemoguardrails import LLMRails, RailsConfig

        import graphmind.safety.config  # noqa: F401 - registers groq provider

        settings = get_settings()
        config_path = Path(settings.safety.guardrails_path)
        config = RailsConfig.from_path(str(config_path))
        _rails = LLMRails(config)
        logger.info("NeMo Guardrails initialized from %s", config_path)
        return _rails
    except Exception as exc:
        logger.warning(
            "Failed to initialize NeMo Guardrails: %s. Running without safety layer.",
            exc,
        )
        return None


async def check_input(user_message: str) -> tuple[bool, str]:
    rails = await get_rails()
    if rails is None:
        return True, user_message

    try:
        response = await rails.generate_async(messages=[{"role": "user", "content": user_message}])
        bot_message = response.get("content", "")

        blocked_phrases = ["cannot comply", "will not process", "I'm designed to answer"]
        is_blocked = any(phrase in bot_message for phrase in blocked_phrases)

        if is_blocked:
            logger.warning("Input blocked by guardrails: %s", user_message[:100])
            return False, bot_message

        return True, user_message
    except Exception as exc:
        logger.error("Guardrails check_input error: %s", exc)
        return True, user_message


async def check_output(bot_message: str) -> tuple[bool, str]:
    rails = await get_rails()
    if rails is None:
        return True, bot_message

    try:
        response = await rails.generate_async(
            messages=[
                {"role": "user", "content": "respond"},
                {"role": "assistant", "content": bot_message},
            ]
        )
        return True, response.get("content", bot_message)
    except Exception as exc:
        logger.error("Guardrails check_output error: %s", exc)
        return True, bot_message
