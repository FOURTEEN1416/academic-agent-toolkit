"""SSRF validation for URLs fetched by the web layer."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


def _is_blocked_addr(addr: ipaddress._BaseAddress) -> bool:
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_unspecified
        or addr.is_multicast
    )


def check_url_ssrf(url: str) -> str | None:
    """Return an error message if *url* targets a private/internal host.

    Validates scheme (http/https only) and resolves the hostname to check
    *every* DNS record against the RFC 1918, loopback, link-local, reserved,
    unspecified, and multicast ranges. Blocking only the first record is
    insufficient: a malicious domain may return both a public and a private
    address, and the HTTP client may connect to any of them.

    Returns ``None`` if the URL is safe to fetch.
    """
    if "\\" in url:
        return "Blocked URL containing backslash (potential SSRF bypass)"
    if "@" in url.split("//", 1)[-1].split("/", 1)[0]:
        return "Blocked URL containing userinfo (potential SSRF bypass)"
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return f"Unsupported URL scheme: {parsed.scheme}"
    hostname = parsed.hostname or ""
    if not hostname:
        return "URL has no hostname"
    # Try parsing hostname as a literal IP address first
    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        # It's a domain name — resolve and check *all* records, since
        # getaddrinfo may return a mix of public and private addresses
        # and the HTTP client is free to connect to any of them.
        try:
            info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except (socket.gaierror, OSError):
            # Can't resolve — let the actual request fail naturally
            return None
        for record in info:
            try:
                resolved = ipaddress.ip_address(record[4][0])
            except (ValueError, IndexError):
                continue
            if _is_blocked_addr(resolved):
                return f"Blocked internal/private URL: {hostname} → {resolved}"
        return None
    if _is_blocked_addr(addr):
        return f"Blocked internal/private URL: {hostname}"
    return None
