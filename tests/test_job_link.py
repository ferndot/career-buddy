"""Fetching a job posting from a link: SSRF guards, limits and text extraction. Resolver and transport are always mocks."""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from career_buddy.adapters.sources.job_link import MAX_BYTES, JobLinkError, JobLinkFetcher
from career_buddy.web.app import create_app

PAGE = b"<html><head><title>x</title><style>p{}</style></head><body><h1>Engineer</h1>\n\n<p>Requirements:</p><ul><li>Python</li></ul></body></html>"
HOSTS = {"jobs.test": ["93.184.216.34"], "evil.test": ["10.0.0.1"], "mixed.test": ["93.184.216.34", "127.0.0.1"], "cdn.test": ["93.184.216.35"]}


def resolver(host: str) -> list[str]:
    return HOSTS.get(host) or [host.strip("[]")]  # IP literals resolve to themselves, like getaddrinfo


def html(body: bytes = PAGE, content_type: str = "text/html; charset=utf-8", **kw) -> httpx.Response:
    return httpx.Response(200, content=body, headers={"content-type": content_type}, **kw)


def fetcher(handler) -> JobLinkFetcher:
    return JobLinkFetcher(httpx.MockTransport(handler), resolver)


def fetch(handler, url: str = "https://jobs.test/p/1") -> str:
    return asyncio.run(fetcher(handler).fetch(url))


def refused(handler, url: str, status: int) -> str:
    with pytest.raises(JobLinkError) as info:
        fetch(handler, url)
    assert info.value.status == status
    return str(info.value)


def never(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"must not be requested: {request.url}")


def test_a_public_page_gives_its_text_without_blank_lines() -> None:
    assert fetch(lambda r: html()) == "Engineer\nRequirements:\nPython"


def test_plain_text_is_accepted() -> None:
    assert fetch(lambda r: html(b"Role\n\n\n- Python\n", "text/plain")) == "Role\n- Python"


@pytest.mark.parametrize("host", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "[::1]", "0.0.0.0", "224.0.0.1", "[::ffff:127.0.0.1]", "evil.test", "mixed.test"])
def test_private_loopback_and_link_local_addresses_are_rejected_before_any_request(host: str) -> None:
    with pytest.raises(JobLinkError) as info:
        asyncio.run(JobLinkFetcher(httpx.MockTransport(never), resolver).fetch(f"http://{host}/"))
    assert info.value.status == 400


def test_a_redirect_to_a_private_address_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "jobs.test":
            return httpx.Response(302, headers={"location": "http://evil.test/admin"})
        return never(request)

    refused(handler, "https://jobs.test/p/1", 400)


def test_a_redirect_to_another_public_host_is_followed_and_relative_ones_too() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/p/1":
            return httpx.Response(301, headers={"location": "/p/2"})
        if request.url.path == "/p/2":
            return httpx.Response(307, headers={"location": "https://cdn.test/p/3"})
        return html() if request.url.host == "cdn.test" else never(request)

    assert fetch(handler).startswith("Engineer")


def test_more_than_three_redirects_are_rejected() -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(302, headers={"location": f"/{len(seen)}"})

    refused(handler, "https://jobs.test/", 502)
    assert len(seen) == 4  # the first request and three redirects; the fourth redirect is not followed


@pytest.mark.parametrize("url", ["ftp://jobs.test/p", "file:///etc/passwd", "javascript:alert(1)", "jobs.test/p", "", "https://user:pw@jobs.test/p", "https://@jobs.test/p", "http:///p"])
def test_other_schemes_userinfo_and_junk_are_rejected(url: str) -> None:
    refused(never, url, 400)


def test_a_body_over_one_megabyte_is_rejected_and_reading_stops() -> None:
    chunks = []

    async def body():
        for _ in range(100):
            chunks.append(1)
            yield b"a" * (MAX_BYTES // 4)

    message = refused(lambda r: httpx.Response(200, content=body(), headers={"content-type": "text/html"}), "https://jobs.test/", 413)
    assert "1 MB" in message
    assert len(chunks) <= 5


def test_a_body_exactly_at_the_cap_is_fine() -> None:
    assert fetch(lambda r: html(b"a" * MAX_BYTES, "text/plain")) == "a" * MAX_BYTES


@pytest.mark.parametrize("content_type", ["application/pdf", "application/json", "image/png", ""])
def test_other_content_types_are_rejected(content_type: str) -> None:
    refused(lambda r: html(b"%PDF", content_type), "https://jobs.test/", 415)


def test_a_page_with_no_readable_text_is_rejected() -> None:
    refused(lambda r: html(b"<html><body><script>var a=1</script></body></html>"), "https://jobs.test/", 422)


def test_a_site_error_is_a_bad_gateway() -> None:
    refused(lambda r: httpx.Response(404), "https://jobs.test/", 502)

    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    refused(broken, "https://jobs.test/", 502)


def test_a_timeout_is_a_gateway_timeout() -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    refused(slow, "https://jobs.test/", 504)


def test_the_whole_fetch_has_a_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("career_buddy.adapters.sources.job_link.TIMEOUT", 0.05)

    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(1)
        return html()

    refused(handler, "https://jobs.test/", 504)


def test_an_unknown_host_is_a_bad_url() -> None:
    def nowhere(host: str) -> list[str]:
        raise OSError("no such host")

    with pytest.raises(JobLinkError) as info:
        asyncio.run(JobLinkFetcher(httpx.MockTransport(never), nowhere).fetch("https://nowhere.test/"))
    assert info.value.status == 400


def api(tmp_path, handler) -> TestClient:
    return TestClient(create_app(tmp_path, job_fetcher=fetcher(handler)))


def test_api_returns_the_posting_text(tmp_path) -> None:
    with api(tmp_path, lambda r: html()) as client:
        res = client.post("/api/job/fetch", json={"url": "https://jobs.test/p/1"})
    assert res.status_code == 200
    assert res.json() == {"text": "Engineer\nRequirements:\nPython"}


def test_api_reports_errors_in_plain_english(tmp_path) -> None:
    with api(tmp_path, never) as client:
        res = client.post("/api/job/fetch", json={"url": "http://127.0.0.1/"})
    assert res.status_code == 400
    assert "private" in res.json()["detail"]
