"""URL validation guard to prevent SSRF attacks.

Blocks requests to private, loopback, link-local, and other non-public networks.

The guard is applied at the HTTP chokepoints in :mod:`gmlst.database.download`
(``fetch_json`` and ``download_file*``) so every URL that originates from an
external API response (e.g. BIGSdb JSON) is validated before any network
access happens.

The check can be bypassed globally by setting the environment variable
``GMLST_ALLOW_PRIVATE_URLS=1`` (or ``true``/``yes``/``on``). This is intended
for the documented ``GMLST_PRIVATE_BIGSDB_URL`` use case (e.g. a local
BIGSdb instance on ``http://127.0.0.1:9000``). When bypassed, a warning is
logged so the security boundary remains explicit.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import socket
from urllib.parse import urlparse

logger = logging.getLogger("gmlst.database.url_guard")


class UrlGuardError(ValueError):
    """Raised when a URL points to a blocked (non-public) destination."""


# Read once at import time. Treating the value as immutable makes the
# security boundary predictable: a process must be restarted (or the env
# var set before launch) to bypass the guard.
_ALLOW_PRIVATE: bool = os.environ.get("GMLST_ALLOW_PRIVATE_URLS", "").lower() in (
    "1",
    "true",
    "yes",
    "on",
)


def _is_blocked_ip(ip: str) -> bool:
    """Return True if *ip* is in a non-public range.

    Blocks RFC 1918 private networks, loopback, link-local (including the
    cloud metadata endpoint 169.254.169.254), reserved, multicast and
    unspecified addresses.
    """
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        # If we cannot parse the literal, treat it as blocked (fail closed).
        return True
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def assert_public_url(url: str, *, allow: set[str] | None = None) -> None:
    """Raise :class:`UrlGuardError` if *url* points to a non-public network.

    Parameters
    ----------
    url:
        The URL to validate.
    allow:
        Optional set of hostnames (matched verbatim, case-insensitively) to
        always permit. Used for the documented private-BIGSdb workflow.

    The function performs the following checks in order:

    1. If ``GMLST_ALLOW_PRIVATE_URLS`` is set, log a warning and return early.
    2. Parse the URL; reject anything that is not ``http`` or ``https``.
    3. Require a hostname (reject URLs with no host).
    4. If the hostname is in *allow*, return early.
    5. Resolve the hostname via :func:`socket.getaddrinfo` and reject if
       every resolved IP is in a blocked range. Literal IP addresses are
       checked directly without DNS resolution. DNS failures fail closed.
    """
    if _ALLOW_PRIVATE:
        logger.warning(
            "SSRF guard bypassed by GMLST_ALLOW_PRIVATE_URLS for URL: %s",
            url,
        )
        return

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UrlGuardError(
            f"Refusing non-http(s) URL (scheme={parsed.scheme!r}): {url}"
        )

    hostname = parsed.hostname
    if not hostname:
        raise UrlGuardError(f"Refusing URL without a hostname: {url}")

    allow_lower = {h.lower() for h in allow} if allow else set()
    if hostname.lower() in allow_lower:
        return

    # Try to interpret the hostname as a literal IP first; this avoids
    # unnecessary DNS lookups and also handles bracketed IPv6 in URLs.
    try:
        literal_ip = ipaddress.ip_address(hostname)
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        if _is_blocked_ip(str(literal_ip)):
            raise UrlGuardError(
                f"Refusing URL pointing at non-public IP {literal_ip}: {url}"
            )
        return

    # Resolve the hostname and check every returned address. We fail if
    # *every* address is blocked — this permits dual-stack hosts that
    # return a public IPv4 alongside a blocked IPv6 (e.g. Teredo).
    try:
        infos = socket.getaddrinfo(hostname, None)
    except OSError as exc:
        # Fail closed: a hostname we cannot resolve is treated as unsafe.
        raise UrlGuardError(
            f"Could not resolve hostname {hostname!r} for URL {url}: {exc}"
        ) from exc

    ips: list[str] = []
    for family, _stype, _proto, _canon, sockaddr in infos:
        if family == socket.AF_INET:
            ips.append(sockaddr[0])
        elif family == socket.AF_INET6:
            # sockaddr = (host, port, flowinfo, scope_id); host may carry
            # a scope-id suffix (e.g. fe80::1%eth0). ip_address handles it.
            ips.append(sockaddr[0].split("%", 1)[0])

    if not ips:
        raise UrlGuardError(
            f"Hostname {hostname!r} resolved to no addresses for URL {url}"
        )

    blocked = [ip for ip in ips if _is_blocked_ip(ip)]
    if len(blocked) == len(ips):
        raise UrlGuardError(
            f"Refusing URL {hostname!r} resolves only to non-public IPs "
            f"({', '.join(blocked)}): {url}"
        )


__all__ = ["UrlGuardError", "assert_public_url"]
