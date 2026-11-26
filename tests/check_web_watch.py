"""Offline tests for official-source parsing and evidence-only web watch."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
from urllib.error import HTTPError
from urllib.request import Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dof_diff_lab.web_watch import (
    SourceError,
    SourceResponse,
    WatchSource,
    _canonical_official_url,
    _OfficialRedirectHandler,
    fetch_source,
    parse_response,
    run_watch,
)

HTML_SOURCE = WatchSource(
    "test-page",
    "Test official page",
    "https://www.snice.gob.mx/notices.html",
    "html",
    "test coverage",
)
RSS_SOURCE = WatchSource(
    "test-feed",
    "Test official feed",
    "https://www.anam.gob.mx/feed/",
    "rss",
    "test coverage",
)
PDF_SOURCE = WatchSource(
    "test-pdf",
    "Test official PDF",
    "https://www.sat.gob.mx/file.pdf",
    "pdf",
    "test coverage",
)


def _html(title: str, links: str) -> SourceResponse:
    body = (
        "<!doctype html><html><head><title>Official notices</title></head><body>"
        f"<h1>{title}</h1><p>Official published information for trade monitoring.</p>"
        f"{links}</body></html>"
    ).encode("utf-8")
    return SourceResponse(200, "text/html", "utf-8", HTML_SOURCE.url, body)


def _feed(items: str = "") -> SourceResponse:
    body = (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<rss version='2.0'><channel><title>ANAM</title>"
        "<description>Agencia Nacional de Aduanas de México</description>"
        f"{items}</channel></rss>"
    ).encode("utf-8")
    return SourceResponse(200, "application/rss+xml", "utf-8", RSS_SOURCE.url, body)


def main() -> None:
    assert _canonical_official_url("../aviso?id=1#section", HTML_SOURCE.url) == (
        "https://www.snice.gob.mx/aviso?id=1"
    )
    for bad_url in (
        "https://snice.gob.mx.evil.invalid/aviso",
        "https://user@snice.gob.mx/aviso",
        "https://snice.gob.mx:8443/aviso",
        "javascript:alert(1)",
    ):
        assert _canonical_official_url(bad_url, HTML_SOURCE.url) is None

    redirect_handler = _OfficialRedirectHandler()
    allowed_redirect = redirect_handler.redirect_request(
        Request(HTML_SOURCE.url),
        None,
        302,
        "Found",
        {},
        "https://www.snice.gob.mx/notices-v2.html",
    )
    assert allowed_redirect is not None
    assert allowed_redirect.full_url == "https://www.snice.gob.mx/notices-v2.html"
    try:
        redirect_handler.redirect_request(
            Request(HTML_SOURCE.url),
            None,
            302,
            "Found",
            {},
            "https://external.example/redirected",
        )
    except SourceError as exc:
        assert "non-official or insecure" in str(exc)
    else:
        raise AssertionError("an off-domain HTTP redirect must be rejected")

    class Headers:
        def get_content_type(self) -> str:
            return "text/html"

        def get_content_charset(self) -> str:
            return "utf-8"

    class Response:
        status = 200

        def __init__(self, final_url: str = HTML_SOURCE.url, body: bytes | None = None):
            self.final_url = final_url
            self.body = body or _html("Retry succeeded", "").body
            self.headers = Headers()

        def geturl(self) -> str:
            return self.final_url

        def read(self, _limit: int) -> bytes:
            return self.body

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    attempts: list[int] = []
    sleeps: list[float] = []

    def retrying_opener(_request: object, timeout: int) -> Response:
        attempts.append(timeout)
        if len(attempts) == 1:
            raise HTTPError(HTML_SOURCE.url, 503, "Unavailable", None, None)
        return Response()

    fetched = fetch_source(
        HTML_SOURCE,
        timeout=12,
        attempts=2,
        opener=retrying_opener,
        sleeper=sleeps.append,
    )
    assert fetched.status == 200 and attempts == [12, 12] and sleeps == [1.0]

    for invalid_timeout in (0, 121, True):
        try:
            fetch_source(HTML_SOURCE, timeout=invalid_timeout)
        except ValueError as exc:
            assert "timeout" in str(exc)
        else:
            raise AssertionError(f"invalid timeout was accepted: {invalid_timeout}")

    unsafe_source_calls = 0

    def unsafe_source_opener(_request: object, timeout: int) -> Response:
        nonlocal unsafe_source_calls
        unsafe_source_calls += 1
        return Response()

    try:
        fetch_source(
            WatchSource(
                "external-source",
                "Untrusted source",
                "https://external.example/page",
                "html",
                "test coverage",
            ),
            opener=unsafe_source_opener,
        )
    except SourceError as exc:
        assert "HTTPS and an official host" in str(exc)
    else:
        raise AssertionError("an off-domain source URL must be rejected")
    assert unsafe_source_calls == 0

    sat_index_url = "https://www.sat.gob.mx/minisitio/NormatividadRMFyRGCE/"
    sat_landing_url = sat_index_url + "normatividad_rmf_rgce2026.html"
    sat_index = WatchSource(
        "test-sat-index",
        "Test SAT index",
        sat_index_url,
        "html",
        "test coverage",
        ("rgce", "clasificacion arancelaria", "nico"),
    )
    request_urls: list[str] = []

    def meta_refresh_opener(request: Request, timeout: int) -> Response:
        request_url = request.full_url
        request_urls.append(request_url)
        if request_url == sat_index_url:
            body = b'<meta http-equiv="Refresh" content="1;url=normatividad_rmf_rgce2026.html">'
            return Response(sat_index_url, body)
        return Response(
            sat_landing_url,
            _html(
                "RGCE 2026",
                '<a href="documentos2026/rmf/rmf/current.pdf">RMF 2026</a>'
                '<a href="documentos2026/rmf/anexos/anexo22.pdf">Anexo 22 de la RMF 2026</a>'
                '<a href="documentos2026/rgce/rgce/current.pdf">RGCE 2026</a>'
                '<a href="documentos2026/rgce/compiladas/anexo22.pdf">Anexo 22 RGCE 2026</a>',
            ).body,
        )

    sat_response = fetch_source(
        sat_index,
        attempts=1,
        opener=meta_refresh_opener,
        sleeper=lambda _seconds: None,
    )
    assert request_urls == [sat_index_url, sat_landing_url]
    assert sat_response.final_url == sat_landing_url
    sat_listing = parse_response(sat_index, sat_response)
    assert [record["title"] for record in sat_listing["records"]] == [
        "Anexo 22 RGCE 2026",
        "RGCE 2026",
    ]
    assert sat_listing["records"] == [
        {
            "title": "Anexo 22 RGCE 2026",
            "url": sat_landing_url.replace(
                "normatividad_rmf_rgce2026.html",
                "documentos2026/rgce/compiladas/anexo22.pdf",
            ),
        },
        {
            "title": "RGCE 2026",
            "url": sat_landing_url.replace(
                "normatividad_rmf_rgce2026.html",
                "documentos2026/rgce/rgce/current.pdf",
            ),
        }
    ]

    def unsafe_meta_refresh_opener(_request: Request, timeout: int) -> Response:
        return Response(
            sat_index_url,
            b'<meta http-equiv="refresh" content="0;url=https://external.example/page">',
        )

    try:
        fetch_source(
            sat_index,
            attempts=1,
            opener=unsafe_meta_refresh_opener,
            sleeper=lambda _seconds: None,
        )
    except SourceError as exc:
        assert "non-official" in str(exc)
    else:
        raise AssertionError("an off-domain meta-refresh must not be fetched")

    not_found_calls = 0

    def not_found_opener(_request: Request, timeout: int) -> Response:
        nonlocal not_found_calls
        not_found_calls += 1
        raise HTTPError(HTML_SOURCE.url, 404, "Not Found", None, None)

    try:
        fetch_source(
            HTML_SOURCE,
            attempts=3,
            opener=not_found_opener,
            sleeper=lambda _seconds: None,
        )
    except SourceError as exc:
        assert "HTTP 404" in str(exc)
    else:
        raise AssertionError("permanent HTTP failures should not be retried as success")
    assert not_found_calls == 1

    parsed_html = parse_response(
        HTML_SOURCE,
        _html(
            "Current notices",
            '<a href="/notice/1">Official notice one</a>'
            '<a href="https://external.example/item">Ignore external link</a>'
            '<script><a href="/hidden">Hidden link</a></script>',
        ),
    )
    assert parsed_html["records"] == [
        {"title": "Official notice one", "url": "https://www.snice.gob.mx/notice/1"}
    ]
    assert parsed_html["rejected_links"] == 1
    assert parse_response(RSS_SOURCE, _feed())["records"] == []
    try:
        parse_response(
            RSS_SOURCE,
            SourceResponse(
                200,
                "application/rss+xml",
                "utf-8",
                RSS_SOURCE.url,
                b"<!DOCTYPE rss [<!ENTITY x 'expanded'>]><rss><channel/></rss>",
            ),
        )
    except SourceError as exc:
        assert "entities" in str(exc)
    else:
        raise AssertionError("RSS document types must be rejected")
    rss_record = parse_response(
        RSS_SOURCE,
        _feed(
            "<item><title>ANAM update</title>"
            "<link>https://www.anam.gob.mx/avisos/update/</link>"
            "<pubDate>Thu, 26 Nov 2026 00:56:01 +0000</pubDate>"
            "<description>Official update summary</description></item>"
        ),
    )["records"]
    assert rss_record == [
        {
            "title": "ANAM update",
            "url": "https://www.anam.gob.mx/avisos/update/",
            "summary": "Official update summary",
            "published_at": "Thu, 26 Nov 2026 00:56:01 +0000",
        }
    ]

    pdf_response = SourceResponse(
        200, "application/pdf", None, PDF_SOURCE.url, b"%PDF-1.7\nsample"
    )
    pdf = parse_response(PDF_SOURCE, pdf_response)
    assert pdf["document_bytes"] == len(pdf_response.body)
    assert len(pdf["document_sha256"]) == 64
    for response, source in (
        (
            SourceResponse(200, "text/html", "utf-8", HTML_SOURCE.url, b"<html>"),
            HTML_SOURCE,
        ),
        (
            SourceResponse(200, "application/pdf", None, PDF_SOURCE.url, b"not a PDF"),
            PDF_SOURCE,
        ),
        (
            SourceResponse(
                200, "text/html", "utf-8", "https://external.example/page", b""
            ),
            HTML_SOURCE,
        ),
        (
            SourceResponse(
                200,
                "application/pdf",
                None,
                "https://www.sat.gob.mx:8443/file.pdf",
                b"%PDF-1.7\nsample",
            ),
            PDF_SOURCE,
        ),
    ):
        try:
            parse_response(source, response)
        except SourceError:
            pass
        else:
            raise AssertionError(f"invalid source response was accepted: {source.source_id}")

    try:
        parse_response(
            WatchSource(
                "external-pdf",
                "Untrusted PDF",
                "https://external.example/file.pdf",
                "pdf",
                "test coverage",
            ),
            pdf_response,
        )
    except SourceError as exc:
        assert "HTTPS and an official host" in str(exc)
    else:
        raise AssertionError("a PDF source must not emit a non-official evidence URL")

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        fixed_now = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)
        responses = {
            HTML_SOURCE.source_id: _html(
                "Notices",
                '<a href="/notice/1">Original notice</a>',
            ),
            RSS_SOURCE.source_id: _feed(),
            PDF_SOURCE.source_id: pdf_response,
        }

        def fake_fetch(source: WatchSource, *, timeout: int) -> SourceResponse:
            assert timeout == 15
            return responses[source.source_id]

        sources = (HTML_SOURCE, RSS_SOURCE, PDF_SOURCE)
        baseline = run_watch(
            root, sources=sources, fetcher=fake_fetch, timeout=15, now=fixed_now
        )
        assert [item.status for item in baseline] == [
            "baseline_created", "baseline_created", "baseline_created"
        ]
        assert all(item.diff_path is None for item in baseline)
        html_snapshot = (
            root / "data" / "web-watch" / "snapshots" / "test-page.json"
        )
        original_bytes = html_snapshot.read_bytes()

        unchanged = run_watch(
            root,
            sources=sources,
            fetcher=fake_fetch,
            timeout=15,
            now=datetime(2026, 11, 26, 13, 0, tzinfo=timezone.utc),
        )
        assert [item.status for item in unchanged] == ["unchanged"] * 3
        assert html_snapshot.read_bytes() == original_bytes

        responses[HTML_SOURCE.source_id] = _html(
            "Updated notices",
            '<a href="/notice/1">Revised notice title</a>'
            '<a href="/notice/2">New official notice</a>',
        )
        responses[RSS_SOURCE.source_id] = _feed(
            "<item><title>ANAM update</title>"
            "<link>https://www.anam.gob.mx/avisos/update/</link>"
            "<description>New publication</description></item>"
        )
        responses[PDF_SOURCE.source_id] = SourceResponse(
            200, "application/pdf", None, PDF_SOURCE.url, b"%PDF-1.7\nrevised"
        )
        changed = run_watch(
            root,
            sources=sources,
            fetcher=fake_fetch,
            timeout=15,
            now=datetime(2026, 11, 26, 14, 0, tzinfo=timezone.utc),
        )
        assert [item.status for item in changed] == ["changed"] * 3
        event_path = root / changed[0].diff_path
        event = json.loads(event_path.read_text(encoding="utf-8"))
        assert [item["title"] for item in event["added"]] == ["New official notice"]
        assert event["removed"] == []
        assert event["modified"] == [
            {
                "before": {
                    "title": "Original notice",
                    "url": "https://www.snice.gob.mx/notice/1",
                },
                "after": {
                    "title": "Revised notice title",
                    "url": "https://www.snice.gob.mx/notice/1",
                },
            }
        ]
        assert event["visible_text_changed"] is True
        assert changed[2].content_sha256 != baseline[2].content_sha256

        def failing_fetch(source: WatchSource, *, timeout: int) -> SourceResponse:
            if source.source_id == RSS_SOURCE.source_id:
                raise SourceError("simulated source outage")
            if source.source_id == HTML_SOURCE.source_id:
                return _html(
                    "Another revision",
                    '<a href="/notice/1">Revised notice title</a>',
                )
            return responses[source.source_id]

        try:
            run_watch(
                root,
                sources=sources,
                fetcher=failing_fetch,
                now=datetime(2026, 11, 26, 15, 0, tzinfo=timezone.utc),
            )
        except SourceError as exc:
            assert "test-feed: simulated source outage" in str(exc)
            assert "test-page: changed" in str(exc)
        else:
            raise AssertionError("a failed source must make the run fail")
        persisted = json.loads(html_snapshot.read_text(encoding="utf-8"))
        assert persisted["records"][0]["title"] == "Revised notice title"

        invalid_source_calls = 0

        def invalid_source_fetcher(
            _source: WatchSource, *, timeout: int
        ) -> SourceResponse:
            nonlocal invalid_source_calls
            invalid_source_calls += 1
            return _html("Invalid source", "")

        try:
            run_watch(
                root,
                sources=(
                    WatchSource(
                        "../escape",
                        "Invalid identifier",
                        HTML_SOURCE.url,
                        "html",
                        "test coverage",
                    ),
                ),
                fetcher=invalid_source_fetcher,
            )
        except SourceError as exc:
            assert "source id" in str(exc)
        else:
            raise AssertionError("an unsafe source id must fail the run")
        assert invalid_source_calls == 0


if __name__ == "__main__":
    main()
