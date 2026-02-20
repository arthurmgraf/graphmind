"""SSRF protection: validate webhook URLs against private IP ranges."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import structlog

logger = structlog.get_logger(__name__)

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
        "metadata.internal",
    }
)


class SSRFError(Exception):
    """Raised when a URL targets a private/internal resource."""


def validate_webhook_url(url: str) -> None:
    """Validate that a webhook URL does not target private/internal resources.

    Raises SSRFError if the URL is unsafe. Call at BOTH registration and dispatch
    time to defend against DNS rebinding.
    """
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise SSRFError(f"Unsupported scheme: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("Missing hostname in URL")

    if hostname.lower() in _BLOCKED_HOSTNAMES:
        raise SSRFError(f"Blocked hostname: {hostname}")

    try:
        addr_infos = socket.getaddrinfo(hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise SSRFError(f"DNS resolution failed for {hostname}: {exc}") from exc

    for _family, _type, _proto, _canonname, sockaddr in addr_infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local:
            raise SSRFError(f"URL resolves to private/reserved IP: {ip}")

    logger.debug("webhook_url_validated", url=url)
