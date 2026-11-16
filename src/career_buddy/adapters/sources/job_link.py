"""Fetch a job posting from a link and return its text.

The server makes this request on the user's behalf, so every address it would connect to (the link and each redirect
target) is resolved first and refused unless it is a public one.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urljoin, urlsplit

import httpx

from career_buddy.adapters.readers.markup_text import HtmlTextReader

TIMEOUT = 10.0  # seconds, for the whole fetch including redirects
MAX_BYTES = 1024 * 1024
MAX_REDIRECTS = 3
REDIRECTS = {301, 302, 303, 307, 308}


class JobLinkError(Exception):
    """A fetch that cannot succeed. `status` is the HTTP status the caller should answer with; the message is for the user."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def resolve_host(host: str) -> list[str]:
    return [str(info[4][0]) for info in socket.getaddrinfo(host, None)]


def _public(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%")[0])  # drop an IPv6 zone such as fe80::1%eth0
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    internal = ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified
    return ip.is_global and not internal


class JobLinkFetcher:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, resolver: Callable[[str], list[str]] = resolve_host) -> None:
        self._transport = transport
        self._resolve = resolver

    async def fetch(self, url: str) -> str:
        try:
            async with asyncio.timeout(TIMEOUT):
                body, kind = await self._get(url)
        except (TimeoutError, httpx.TimeoutException) as error:
            raise JobLinkError(504, "The site took too long to answer.") from error
        except httpx.HTTPError as error:
            raise JobLinkError(502, "The site could not be reached.") from error
        if kind == "text/plain":
            lines = (line.strip() for line in body.decode("utf-8", "replace").splitlines())
        else:
            lines = iter(HtmlTextReader().read(body).lines)
        text = "\n".join(line for line in lines if line)
        if not text:
            raise JobLinkError(422, "No readable text was found on that page. Paste the posting into the box instead.")
        return text

    async def _check(self, url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise JobLinkError(400, "Enter a link that starts with http:// or https://.")
        if "@" in parts.netloc:
            raise JobLinkError(400, "Links with a user name or password in them are not accepted.")
        try:
            addresses = await asyncio.to_thread(self._resolve, parts.hostname)
        except OSError as error:
            raise JobLinkError(400, "That site's address could not be found. Check the link.") from error
        # shortcut: the connection resolves the name again, so a host that changes its answer between the two lookups
        # could slip through (DNS rebinding); pin the address on the connection if this is ever exposed beyond localhost.
        if not addresses or not all(_public(address) for address in addresses):
            raise JobLinkError(400, "That link points to a private or internal address, so it cannot be fetched.")

    async def _get(self, url: str) -> tuple[bytes, str]:
        async with httpx.AsyncClient(transport=self._transport, timeout=TIMEOUT, trust_env=False,
                                     headers={"User-Agent": "career-buddy", "Accept": "text/html,text/plain"}) as client:
            for _ in range(MAX_REDIRECTS + 1):
                await self._check(url)
                async with client.stream("GET", url) as response:
                    if response.status_code in REDIRECTS:
                        location = response.headers.get("location")
                        if not location:
                            raise JobLinkError(502, "The site sent you somewhere without saying where.")
                        url = urljoin(url, location)
                        continue
                    if not response.is_success:
                        raise JobLinkError(502, f"The site answered with an error ({response.status_code}).")
                    kind = response.headers.get("content-type", "").split(";")[0].strip().lower()
                    if kind not in ("text/html", "text/plain"):
                        raise JobLinkError(415, "That link is not a web page or plain text.")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body += chunk
                        if len(body) > MAX_BYTES:
                            raise JobLinkError(413, "That page is over 1 MB, which is too large to read.")
                    return bytes(body), kind
        raise JobLinkError(502, "The link redirected too many times.")
