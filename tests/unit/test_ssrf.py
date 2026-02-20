"""Tests for SSRF URL validation."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from graphmind.security.ssrf import SSRFError, validate_webhook_url


def _mock_getaddrinfo_public(*args, **kwargs):
    """Mock that returns a public IP address."""
    return [(2, 1, 6, "", ("93.184.216.34", 443))]


def _mock_getaddrinfo_private_10(*args, **kwargs):
    return [(2, 1, 6, "", ("10.0.0.1", 443))]


def _mock_getaddrinfo_private_172(*args, **kwargs):
    return [(2, 1, 6, "", ("172.16.0.1", 443))]


def _mock_getaddrinfo_private_192(*args, **kwargs):
    return [(2, 1, 6, "", ("192.168.1.1", 443))]


def _mock_getaddrinfo_loopback(*args, **kwargs):
    return [(2, 1, 6, "", ("127.0.0.1", 443))]


def _mock_getaddrinfo_ipv6_loopback(*args, **kwargs):
    return [(10, 1, 6, "", ("::1", 443, 0, 0))]


def _mock_getaddrinfo_link_local(*args, **kwargs):
    return [(2, 1, 6, "", ("169.254.1.1", 443))]


class TestValidPublicURL:
    @patch("graphmind.security.ssrf.socket.getaddrinfo", _mock_getaddrinfo_public)
    def test_valid_public_url_passes(self):
        """A URL resolving to a public IP should pass validation."""
        validate_webhook_url("https://hooks.example.com/webhook")


class TestPrivateIPBlocked:
    @patch("graphmind.security.ssrf.socket.getaddrinfo", _mock_getaddrinfo_private_10)
    def test_private_ip_10_blocked(self):
        """10.0.0.0/8 range should be blocked."""
        with pytest.raises(SSRFError, match="private/reserved"):
            validate_webhook_url("https://internal.example.com/hook")

    @patch("graphmind.security.ssrf.socket.getaddrinfo", _mock_getaddrinfo_private_172)
    def test_private_ip_172_blocked(self):
        """172.16.0.0/12 range should be blocked."""
        with pytest.raises(SSRFError, match="private/reserved"):
            validate_webhook_url("https://internal.example.com/hook")

    @patch("graphmind.security.ssrf.socket.getaddrinfo", _mock_getaddrinfo_private_192)
    def test_private_ip_192_blocked(self):
        """192.168.0.0/16 range should be blocked."""
        with pytest.raises(SSRFError, match="private/reserved"):
            validate_webhook_url("https://internal.example.com/hook")


class TestLocalhostBlocked:
    def test_localhost_blocked(self):
        """Hostname 'localhost' should be blocked before DNS resolution."""
        with pytest.raises(SSRFError, match="Blocked hostname"):
            validate_webhook_url("http://localhost:7687/hook")


class TestLoopbackBlocked:
    @patch("graphmind.security.ssrf.socket.getaddrinfo", _mock_getaddrinfo_loopback)
    def test_loopback_blocked(self):
        """127.0.0.1 should be blocked."""
        with pytest.raises(SSRFError, match="private/reserved"):
            validate_webhook_url("http://loopback.example.com/hook")


class TestIPv6LoopbackBlocked:
    @patch("graphmind.security.ssrf.socket.getaddrinfo", _mock_getaddrinfo_ipv6_loopback)
    def test_ipv6_loopback_blocked(self):
        """[::1] should be blocked."""
        with pytest.raises(SSRFError, match="private/reserved"):
            validate_webhook_url("http://ipv6loop.example.com/hook")


class TestLinkLocalBlocked:
    @patch("graphmind.security.ssrf.socket.getaddrinfo", _mock_getaddrinfo_link_local)
    def test_link_local_blocked(self):
        """169.254.x.x should be blocked."""
        with pytest.raises(SSRFError, match="private/reserved"):
            validate_webhook_url("http://linklocal.example.com/hook")


class TestNonHTTPScheme:
    def test_non_http_scheme_blocked(self):
        """Non-HTTP(S) schemes should be blocked."""
        with pytest.raises(SSRFError, match="Unsupported scheme"):
            validate_webhook_url("ftp://example.com/files")


class TestMetadataEndpoint:
    def test_metadata_endpoint_blocked(self):
        """Cloud metadata endpoints should be blocked."""
        with pytest.raises(SSRFError, match="Blocked hostname"):
            validate_webhook_url("http://metadata.google.internal/computeMetadata/v1/")
