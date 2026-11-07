from __future__ import annotations

import socket
from io import BytesIO
from typing import Any

import httpx
import httpcore
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.main import APISettings, create_app
from src.input_processor import InputProcessor, _PinnedNetworkBackend


ARTICLE_HTML = b"""
<!doctype html>
<html><head><title>Regional council approves new plan</title></head>
<body>
<nav><p>This navigation text must not be extracted as article content.</p></nav>
<main><article><h1>Regional council approves new plan</h1>
<p>The regional council approved a new public transport plan after a recorded vote.
The plan will add several bus routes and publish its timetable next month.</p>
<p>Officials said the proposal was discussed at a public meeting.</p>
</article></main>
<script>document.write("This script must not be executed.");</script>
</body></html>
"""


def public_resolver(
    host: str,
    port: int,
    **_: Any,
) -> list[tuple[Any, ...]]:
    return [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("93.184.216.34", port),
        )
    ]


def response_transport(
    status_code: int = 200,
    *,
    content: bytes = ARTICLE_HTML,
    headers: dict[str, str] | None = None,
) -> httpx.MockTransport:
    response_headers = {"content-type": "text/html; charset=utf-8"}
    response_headers.update(headers or {})
    return httpx.MockTransport(
        lambda request: httpx.Response(
            status_code,
            headers=response_headers,
            content=content,
            request=request,
        )
    )


def png_image() -> bytes:
    image = Image.new("RGB", (20, 20), color="white")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_plain_text_is_trimmed_and_returned_in_consistent_shape() -> None:
    text = "  The council approved the public plan.  "

    result = InputProcessor().process(text)

    assert result["input_type"] == "text"
    assert result["original_input"] == text
    assert result["extracted_text"] == text.strip()
    assert result["source_url"] is None
    assert result["processing_status"] == "processed"
    assert result["warnings"] == []
    assert result["error"] is None


@pytest.mark.parametrize("text", ["", " \t\r\n"])
def test_empty_text_is_rejected(text: str) -> None:
    result = InputProcessor().process(text)

    assert result["processing_status"] == "rejected"
    assert "empty" in result["error"]


def test_article_url_extracts_title_and_visible_body_only() -> None:
    processor = InputProcessor(
        transport=response_transport(),
        dns_resolver=public_resolver,
    )

    result = processor.process("https://news.example/story")

    assert result["processing_status"] == "processed"
    assert result["input_type"] == "article_url"
    assert result["title"] == "Regional council approves new plan"
    assert "public transport plan" in result["extracted_text"]
    assert "navigation text" not in result["extracted_text"]
    assert "document.write" not in result["extracted_text"]
    assert result["source_url"] == "https://news.example/story"


def test_article_url_excludes_related_news_and_advertising_paragraphs() -> None:
    html = b"""
    <html><head><title>Page title</title></head><body>
      <header><h1>Actual article headline</h1></header>
      <main>
        <article>
          <p>The government announced a new policy after a cabinet meeting.</p>
          <p>The policy will begin next month and apply to public services.</p>
          <div class="related-news"><p>Unrelated story about a sports final.</p></div>
          <div id="advertisement"><p>Advertisement copy must not be included.</p></div>
        </article>
        <aside><p>More related news must not be included.</p></aside>
      </main>
      <div><p>Unrelated page text outside the article should not be included.</p></div>
    </body></html>
    """
    processor = InputProcessor(
        transport=response_transport(content=html),
        dns_resolver=public_resolver,
    )

    result = processor.process("https://news.example/story")

    assert result["title"] == "Actual article headline"
    assert "The government announced a new policy" in result["extracted_text"]
    assert "Unrelated story" not in result["extracted_text"]
    assert "Advertisement copy" not in result["extracted_text"]
    assert "More related news" not in result["extracted_text"]
    assert "Unrelated page text" not in result["extracted_text"]


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "http://localhost/private",
        "http://127.0.0.1/admin",
        "http://10.1.2.3/",
        "https://news.example:8443/story",
        "https://user:pass@news.example/story",
    ],
)
def test_malformed_and_non_public_urls_are_rejected(url: str) -> None:
    processor = InputProcessor(dns_resolver=public_resolver)

    result = processor.process_url(url)

    assert result["processing_status"] == "rejected"
    assert result["extracted_text"] == ""


def test_dns_resolution_to_private_address_is_rejected() -> None:
    def private_resolver(host: str, port: int, **_: Any) -> list[tuple[Any, ...]]:
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("192.168.1.4", port),
            )
        ]

    result = InputProcessor(dns_resolver=private_resolver).process_url(
        "https://news.example/story"
    )

    assert result["processing_status"] == "rejected"
    assert "private or non-public" in result["error"]


def test_http_connection_uses_the_validated_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    connected_hosts: list[str] = []

    def connect_tcp(
        self: httpcore.SyncBackend,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> object:
        connected_hosts.append(host)
        return object()

    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", connect_tcp)
    backend = _PinnedNetworkBackend(
        "news.example",
        ("93.184.216.34",),
    )

    backend.connect_tcp("news.example", 443)

    assert connected_hosts == ["93.184.216.34"]


def test_redirect_to_private_destination_is_blocked_before_following() -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(
            302,
            headers={"location": "http://127.0.0.1/internal"},
            request=request,
        )

    processor = InputProcessor(
        transport=httpx.MockTransport(handler),
        dns_resolver=public_resolver,
    )

    result = processor.process_url("https://news.example/story")

    assert result["processing_status"] == "rejected"
    assert len(requested) == 1
    assert "private and non-public" in result["error"].casefold()


def test_redirect_destination_is_revalidated_by_dns() -> None:
    resolved: list[str] = []

    def resolver(host: str, port: int, **_: Any) -> list[tuple[Any, ...]]:
        resolved.append(host)
        address = "93.184.216.34" if host == "news.example" else "10.0.0.4"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]

    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            302,
            headers={"location": "https://redirect.example/story"},
            request=request,
        )
    )
    result = InputProcessor(
        transport=transport,
        dns_resolver=resolver,
    ).process_url("https://news.example/story")

    assert result["processing_status"] == "rejected"
    assert resolved == ["news.example", "news.example", "redirect.example"]


def test_timeout_and_network_errors_are_reported_without_raising() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("request timed out", request=request)

    result = InputProcessor(
        transport=httpx.MockTransport(timeout),
        dns_resolver=public_resolver,
    ).process_url("https://news.example/story")

    assert result["processing_status"] == "unavailable"
    assert "timed out" in result["error"]

    def network_error(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    failed = InputProcessor(
        transport=httpx.MockTransport(network_error),
        dns_resolver=public_resolver,
    ).process_url("https://news.example/story")
    assert failed["processing_status"] == "unavailable"
    assert "could not be reached" in failed["error"]


def test_inaccessible_public_article_url_is_unavailable() -> None:
    def not_found(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, request=request)

    result = InputProcessor(
        transport=httpx.MockTransport(not_found),
        dns_resolver=public_resolver,
    ).process_url("https://news.example/missing")

    assert result["processing_status"] == "unavailable"
    assert "HTTP 404" in result["error"]
    assert result["extracted_text"] == ""


def test_dns_failure_is_reported_as_unavailable() -> None:
    def failed_resolver(host: str, port: int, **_: Any) -> list[tuple[Any, ...]]:
        raise socket.gaierror("host not found")

    result = InputProcessor(dns_resolver=failed_resolver).process_url(
        "https://news.example/story"
    )

    assert result["processing_status"] == "unavailable"
    assert "could not be resolved" in result["error"]


def test_unsupported_content_type_and_metadata_only_page_are_not_article_text() -> None:
    processor = InputProcessor(
        transport=response_transport(
            content=b"%PDF",
            headers={"content-type": "application/pdf"},
        ),
        dns_resolver=public_resolver,
    )

    result = processor.process_url("https://news.example/document")

    assert result["processing_status"] == "unsupported"
    assert result["extracted_text"] == ""

    metadata_only = b'<html><head><title>A title only</title></head><body></body></html>'
    result = InputProcessor(
        transport=response_transport(content=metadata_only),
        dns_resolver=public_resolver,
    ).process_url("https://news.example/title-only")
    assert result["processing_status"] == "unsupported"
    assert result["title"] == "A title only"
    assert result["extracted_text"] == ""


def test_oversized_external_response_is_rejected() -> None:
    result = InputProcessor(
        max_response_bytes=20,
        transport=response_transport(),
        dns_resolver=public_resolver,
    ).process_url("https://news.example/story")

    assert result["processing_status"] == "rejected"
    assert "maximum response size" in result["error"]


@pytest.mark.parametrize(
    "message",
    [
        "Forwarded many times\nThe council approved the proposal last week.",
        "Forwarded\nThe council approved the proposal last week.",
        "Forwarded from a public channel\nThe meeting began at noon.",
        "----- Forwarded message -----\nThe meeting began at noon.",
    ],
)
def test_forwarded_messaging_text_is_preserved_and_flagged(message: str) -> None:
    result = InputProcessor().process(message)

    assert result["input_type"] == "forwarded_text"
    assert result["extracted_text"] == message.strip()
    assert "not been independently verified" in result["warnings"][0]


def test_explicit_telegram_forwarded_text_is_supported() -> None:
    result = InputProcessor().process(
        "The council approved the proposal.",
        input_type="forwarded",
    )

    assert result["input_type"] == "forwarded_text"
    assert result["processing_status"] == "processed"


def test_public_social_media_unavailable_response_is_explicit() -> None:
    result = InputProcessor(
        transport=response_transport(403),
        dns_resolver=public_resolver,
    ).process_url("https://www.facebook.com/public-post")

    assert result["input_type"] == "social_url"
    assert result["processing_status"] == "unsupported"
    assert result["extracted_text"] == ""
    assert "not directly accessible" in result["warnings"][0]


def test_static_public_social_post_text_can_be_extracted() -> None:
    social_html = b"""
    <html><body><article>
    <p>A public post says the city council approved a new water plan at its meeting.</p>
    </article></body></html>
    """
    result = InputProcessor(
        transport=response_transport(content=social_html),
        dns_resolver=public_resolver,
    ).process_url("https://x.com/public/status/123")

    assert result["input_type"] == "social_url"
    assert result["processing_status"] == "processed"
    assert "city council approved" in result["extracted_text"]


def test_image_ocr_uses_local_injected_engine() -> None:
    processor = InputProcessor(ocr_engine=lambda _: "The council approved the plan.")

    result = processor.process_image(png_image(), "screen.png")

    assert result["input_type"] == "image"
    assert result["processing_status"] == "processed"
    assert result["extracted_text"] == "The council approved the plan."


def test_corrupt_image_and_mismatched_extension_are_rejected() -> None:
    processor = InputProcessor()

    corrupt = processor.process_image(b"\x89PNG\r\n\x1a\nnot-an-image", "screen.png")
    mismatch = processor.process_image(png_image(), "screen.jpg")

    assert corrupt["processing_status"] == "rejected"
    assert mismatch["processing_status"] == "rejected"


def test_upload_size_limit_and_image_dimensions_are_enforced() -> None:
    size_limited = InputProcessor(max_upload_bytes=10).process_image(
        png_image(),
        "screen.png",
    )
    pixel_limited = InputProcessor(max_image_pixels=10).process_image(
        png_image(),
        "screen.png",
    )

    assert size_limited["processing_status"] == "rejected"
    assert "maximum upload size" in size_limited["error"]
    assert pixel_limited["processing_status"] == "rejected"
    assert "dimensions" in pixel_limited["error"]


def test_ocr_missing_is_reported_without_affecting_other_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processor = InputProcessor()

    def unavailable(_: Any) -> str:
        raise ModuleNotFoundError("pytesseract is optional")

    monkeypatch.setattr(processor, "_run_ocr", unavailable)
    result = processor.process_image(png_image(), "screen.png")

    assert result["processing_status"] == "unavailable"
    assert "optional OCR" in result["warnings"][0]
    assert InputProcessor().process("A plain headline.")["processing_status"] == "processed"


def test_ocr_without_usable_text_returns_warning() -> None:
    result = InputProcessor(ocr_engine=lambda _: " \n--- \n").process_image(
        png_image(),
        "screen.png",
    )

    assert result["processing_status"] == "no_text"
    assert result["extracted_text"] == ""
    assert "usable text" in result["warnings"][0]


class _Classifier:
    def predict(self, text: str) -> dict[str, Any]:
        return {"prediction": "Real", "label": 1}


class _UnavailableRetriever:
    def retrieve(self, claim: str, claim_id: int) -> dict[str, Any]:
        return {
            "claim_id": claim_id,
            "evidence": [],
            "retrieval_status": "unavailable",
        }


def test_api_returns_consistent_text_response_and_validates_empty_input() -> None:
    client = TestClient(create_app(classifier=_Classifier()))

    response = client.post(
        "/api/process-input",
        json={"input": "The council approved a new public plan."},
    )
    empty = client.post("/api/process-input", json={"input": "  "})

    assert response.status_code == 200
    assert response.json()["processing_status"] == "processed"
    assert response.json()["input_type"] == "text"
    assert "The council approved" in response.json()["extracted_text"]
    assert empty.status_code == 422


def test_api_reports_oversized_text_with_413() -> None:
    client = TestClient(create_app(classifier=_Classifier()))

    response = client.post(
        "/api/process-input",
        json={"input": "A" * 100_001},
    )

    assert response.status_code == 413
    assert response.json()["processing_status"] == "rejected"


def test_api_respects_configured_input_length_limit() -> None:
    client = TestClient(
        create_app(
            classifier=_Classifier(),
            settings=APISettings(model_dir="models", input_max_length=8),
        )
    )

    response = client.post(
        "/api/process-input",
        json={"input": "The council approved a plan."},
    )

    assert response.status_code == 413
    assert response.json()["processing_status"] == "rejected"


def test_api_image_endpoint_validates_upload() -> None:
    processor = InputProcessor(ocr_engine=lambda _: "A headline was published.")
    client = TestClient(
        create_app(classifier=_Classifier(), input_processor=processor)
    )

    response = client.post(
        "/api/process-image",
        files={"file": ("screen.png", png_image(), "image/png")},
    )

    assert response.status_code == 200
    assert response.json()["input_type"] == "image"
    assert response.json()["extracted_text"] == "A headline was published."


def test_opt_in_pipeline_calls_existing_stages_and_keeps_classifier_caveat() -> None:
    client = TestClient(
        create_app(
            classifier=_Classifier(),
            evidence_retriever=_UnavailableRetriever(),
            settings=APISettings(model_dir="models"),
        )
    )

    response = client.post(
        "/api/process-input",
        json={
            "input": "The council approved a new public plan.",
            "run_pipeline": True,
        },
    )

    assert response.status_code == 200
    pipeline = response.json()["pipeline"]
    assert pipeline["classifier"]["prediction"] == "Real"
    assert "not a factual verdict" in pipeline["classifier"]["interpretation"]
    assert len(pipeline["claim_assessments"]) == 1
    assert pipeline["claim_assessments"][0]["analysis"]["verdict"] == (
        "INSUFFICIENT EVIDENCE"
    )
