from typing import Any
import ssl

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.main import APISettings, create_app
from src.evidence_retrieval import (
    DEFAULT_MAX_RESPONSE_BYTES,
    GdeltDocSource,
    EvidenceInputError,
    EvidenceRetriever,
    ResponseTooLargeError,
    build_search_query,
    classify_source,
)

CLAIM = "India launched a new satellite on Monday."


class MockSource:
    name = "Mock public source"

    def __init__(
        self,
        results: list[dict[str, Any]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.results = results or []
        self.error = error
        self.queries: list[tuple[str, int]] = []

    def search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        self.queries.append((query, max_results))
        if self.error is not None:
            raise self.error
        return self.results


def article(
    url: str = "https://pib.gov.in/example",
    title: str | None = "India satellite launch Monday",
    **metadata: Any,
) -> dict[str, Any]:
    result: dict[str, Any] = {"url": url}
    if title is not None:
        result["title"] = title
    result.update(metadata)
    return result


def test_valid_claim_builds_query_and_retrieves_public_result() -> None:
    source = MockSource([article()])
    retriever = EvidenceRetriever([source])

    result = retriever.retrieve(CLAIM, claim_id=7)

    assert result["claim_id"] == 7
    assert result["query"] == "India launched new satellite Monday"
    assert result["retrieval_status"] == "completed"
    assert result["total_results"] == 1
    assert result["evidence"][0]["source_name"] == "Press Information Bureau"
    assert result["evidence"][0]["source_type"] == "official"
    assert result["evidence"][0]["claim_id"] == 7
    assert source.queries == [(result["query"], 5)]


def test_search_query_deduplicates_and_prioritizes_names_and_numbers() -> None:
    query = build_search_query(
        "The Prime Minister announced in 2024 a major agreement with Brazil "
        "during an official visit after the summit, following a second meeting."
    )
    terms = query.split()

    assert len(terms) <= 12
    assert len({term.casefold() for term in terms}) == len(terms)
    assert {"Prime", "Minister", "2024", "Brazil"} <= set(terms)


@pytest.mark.parametrize(
    ("claim", "error"),
    [
        ("", EvidenceInputError),
        (" \n ", EvidenceInputError),
        (None, TypeError),
    ],
)
def test_invalid_claims_are_rejected(claim: Any, error: type[Exception]) -> None:
    with pytest.raises(error):
        EvidenceRetriever([]).retrieve(claim)


def test_evidence_has_structured_metadata_without_inventing_missing_fields() -> None:
    result = EvidenceRetriever(
        [
            MockSource(
                [
                    article(
                        url="https://unknown.example/story",
                        title=None,
                        seendate="20261103T120000Z",
                    )
                ]
            )
        ]
    ).retrieve(CLAIM)
    evidence = result["evidence"][0]

    # New format includes connector and connector_status
    assert set(evidence) == {
        "evidence_id",
        "claim_id",
        "source_name",
        "source_domain",
        "source_url",
        "title",
        "snippet",
        "page_content",
        "page_content_status",
        "published_date",
        "retrieved_at",
        "source_type",
        "relevance_score",
        "retrieval_status",
        "connector",
        "connector_status",
    }
    assert evidence["source_domain"] == "unknown.example"
    assert evidence["source_type"] == "unknown"
    assert evidence["title"] is None
    assert evidence["snippet"] is None
    assert evidence["page_content"] is None
    assert evidence["page_content_status"] == "not_attempted"
    assert evidence["published_date"] is None
    assert evidence["relevance_score"] == 0.0
    assert evidence["retrieval_status"] == "retrieved"
    assert evidence["connector"] == "gdelt"
    assert evidence["connector_status"] == "success"


def test_removes_duplicate_urls_and_normalized_titles() -> None:
    source = MockSource(
        [
            article(url="https://pib.gov.in/story#section"),
            article(
                url="https://pib.gov.in/story",
                title="A Different Title",
            ),
            article(
                url="https://who.int/story",
                title="INDIA satellite launch Monday!",
            ),
        ]
    )

    result = EvidenceRetriever([source]).retrieve(CLAIM)

    assert result["total_results"] == 1
    assert result["evidence"][0]["source_url"] == "https://pib.gov.in/story"


def test_prioritizes_known_official_sources_without_dropping_other_evidence() -> None:
    source = MockSource(
        [
            article(
                url="https://reuters.com/story",
                title="Satellite launch reported",
            ),
            article(
                url="https://pib.gov.in/story",
                title="India satellite launch Monday",
            ),
        ]
    )

    result = EvidenceRetriever([source], max_results=2).retrieve(CLAIM)

    assert result["total_results"] == 2
    assert result["evidence"][0]["source_type"] == "official"
    assert result["evidence"][1]["source_type"] == "news"


def test_preserves_other_distinct_results_and_computes_relevance() -> None:
    source = MockSource(
        [
            article(title="India satellite launch Monday"),
            article(
                url="https://who.int/weather",
                title="Weather satellite support",
                snippet="The new satellite supports forecasting.",
            ),
        ]
    )

    result = EvidenceRetriever([source], max_results=3).retrieve(CLAIM)

    assert result["total_results"] == 2
    assert result["evidence"][0]["relevance_score"] > 0
    assert result["evidence"][1]["snippet"] == "The new satellite supports forecasting."
    assert result["evidence"][1]["source_type"] == "official"


def test_relevant_page_text_is_ranked_and_exposed_as_a_verbatim_snippet() -> None:
    page_text = (
        "Unrelated background about astronomy. "
        "India launched a new satellite on Monday, the space agency confirmed."
    )
    result = EvidenceRetriever(
        [
            MockSource(
                [
                    article(
                        url="https://pib.gov.in/satellite",
                        title="Satellite mission",
                        page_content=page_text,
                        page_content_status="retrieved",
                    )
                ]
            )
        ]
    ).retrieve(CLAIM)

    evidence = result["evidence"][0]
    assert evidence["page_content"] == page_text
    assert evidence["snippet"].startswith("India launched a new satellite")
    assert evidence["relevance_score"] == 1


def test_timeout_is_reported_without_crashing() -> None:
    source = MockSource(error=httpx.TimeoutException("private timeout detail"))

    result = EvidenceRetriever([source]).retrieve(CLAIM)

    assert result["success"] is False
    assert result["evidence"] == []
    assert result["retrieval_status"] == "unavailable"
    assert result["source_errors"] == [
        {"source": source.name, "error": "timeout"}
    ]
    assert "private timeout detail" not in str(result)


def test_tls_failure_is_reported_separately_from_a_generic_network_error() -> None:
    error = httpx.ConnectError("TLS handshake failed")
    error.__cause__ = ssl.SSLError("certificate verify failed")
    source = MockSource(error=error)

    result = EvidenceRetriever([source]).retrieve(CLAIM)

    assert result["success"] is False
    assert result["evidence"] == []
    assert result["retrieval_status"] == "unavailable"
    assert result["source_errors"] == [
        {"source": source.name, "error": "tls_error"}
    ]


def test_http_error_is_reported_without_crashing() -> None:
    request = httpx.Request("GET", "https://api.example.test/search")
    response = httpx.Response(503, request=request)
    source = MockSource(
        error=httpx.HTTPStatusError("internal detail", request=request, response=response)
    )

    result = EvidenceRetriever([source]).retrieve(CLAIM)

    assert result["retrieval_status"] == "unavailable"
    assert result["source_errors"][0]["error"] == "http_error"


def test_rate_limit_is_reported_separately() -> None:
    request = httpx.Request("GET", "https://api.example.test/search")
    response = httpx.Response(429, request=request)
    source = MockSource(
        error=httpx.HTTPStatusError("rate limited", request=request, response=response)
    )

    result = EvidenceRetriever([source]).retrieve(CLAIM)

    assert result["source_errors"][0]["error"] == "rate_limited"


def test_unavailable_source_does_not_prevent_other_sources() -> None:
    unavailable = MockSource(error=RuntimeError("do not expose"))
    working = MockSource([article()])

    result = EvidenceRetriever([unavailable, working]).retrieve(CLAIM)

    assert result["success"] is True
    assert result["retrieval_status"] == "partial"
    assert result["total_results"] == 1
    assert result["source_errors"] == [
        {"source": unavailable.name, "error": "source_unavailable"}
    ]


def test_empty_search_results_are_not_reported_as_retrieval_failure() -> None:
    result = EvidenceRetriever([MockSource()]).retrieve(CLAIM)

    assert result["success"] is True
    assert result["retrieval_status"] == "no_results"
    assert result["total_results"] == 0
    assert result["evidence"] == []


def test_malformed_search_response_is_reported_as_unavailable() -> None:
    class MalformedSource:
        name = "Malformed source"

        def search(self, query: str, max_results: int) -> list[dict[str, Any]]:
            return None  # type: ignore[return-value]

    result = EvidenceRetriever([MalformedSource()]).retrieve(CLAIM)

    assert result["evidence"] == []
    assert result["retrieval_status"] == "unavailable"
    assert result["source_errors"] == [
        {"source": "Malformed source", "error": "malformed_response"}
    ]


@pytest.mark.parametrize(
    ("domain", "expected_type"),
    [
        ("pib.gov.in", "official"),
        ("subdomain.who.int", "official"),
        ("www.gov.uk", "official"),
        ("altnews.in", "fact_checker"),
        ("reuters.com", "news"),
        ("unknown.example", "unknown"),
        (None, "unknown"),
    ],
)
def test_source_classification_uses_known_domains(
    domain: str | None,
    expected_type: str,
) -> None:
    _, source_type = classify_source(domain)

    assert source_type == expected_type


def test_result_limit_is_applied_and_sent_to_source() -> None:
    source = MockSource(
        [
            article(title="India satellite launch Monday"),
            article(
                url="https://who.int/second",
                title="WHO forecasts weather trends",
            ),
            article(
                url="https://reuters.com/third",
                title="India launch report",
            ),
        ]
    )

    result = EvidenceRetriever([source], max_results=2).retrieve(CLAIM)

    assert result["total_results"] == 2
    assert source.queries[0][1] == 2


def test_claim_and_configured_response_size_limits() -> None:
    with pytest.raises(EvidenceInputError, match="maximum length"):
        build_search_query("x" * 5_001)

    source = GdeltDocSource(max_response_bytes=1)
    assert source.max_response_bytes == 1
    assert DEFAULT_MAX_RESPONSE_BYTES > source.max_response_bytes
    with pytest.raises(ValueError, match="retry_limit"):
        GdeltDocSource(retry_limit=-1)


def test_gdelt_adapter_handles_oversized_content(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        status_code = 200
        headers = {"content-length": "2"}

        def raise_for_status(self) -> None:
            return None

    class FakeStream:
        def __enter__(self) -> FakeResponse:
            return FakeResponse()

        def __exit__(self, *_: object) -> None:
            return None

    class FakeClient:
        def __init__(self, **_: Any) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def stream(
            self,
            method: str,
            url: str,
            *,
            params: dict[str, str],
        ) -> FakeStream:
            assert method == "GET"
            assert url == "https://api.gdeltproject.org/api/v2/doc/doc"
            assert params["maxrecords"] == "1"
            return FakeStream()

    monkeypatch.setattr("src.evidence_retrieval.httpx.Client", FakeClient)
    source = GdeltDocSource(max_response_bytes=1)

    with pytest.raises(ResponseTooLargeError):
        source._fetch_json("India satellite", 1)


def test_gdelt_adapter_includes_public_page_text_in_retrieved_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response_body = (
        b'{"articles":[{"url":"https://pib.gov.in/satellite",'
        b'"title":"India satellite launch Monday"}]}'
    )
    fetched_urls: list[str] = []

    class FakeResponse:
        status_code = 200
        headers: dict[str, str] = {}

        def raise_for_status(self) -> None:
            return None

        def iter_bytes(self) -> list[bytes]:
            return [response_body]

    class FakeStream:
        def __enter__(self) -> FakeResponse:
            return FakeResponse()

        def __exit__(self, *_: object) -> None:
            return None

    class FakeClient:
        def __init__(self, **_: Any) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def stream(
            self,
            method: str,
            url: str,
            *,
            params: dict[str, str],
        ) -> FakeStream:
            assert method == "GET"
            assert params["query"] == "India launched new satellite Monday"
            return FakeStream()

    def fetch_article(url: str) -> dict[str, Any]:
        fetched_urls.append(url)
        return {
            "processing_status": "processed",
            "title": "India satellite launch Monday",
            "extracted_text": (
                "Unrelated background. India launched a new satellite on Monday."
            ),
        }

    monkeypatch.setattr("src.evidence_retrieval.httpx.Client", FakeClient)
    source = GdeltDocSource(article_fetcher=fetch_article)

    result = EvidenceRetriever([source]).retrieve(CLAIM)
    evidence = result["evidence"][0]

    assert fetched_urls == ["https://pib.gov.in/satellite"]
    assert evidence["page_content"].endswith(
        "India launched a new satellite on Monday."
    )
    assert evidence["snippet"] == "India launched a new satellite on Monday."
    assert evidence["source_url"] == "https://pib.gov.in/satellite"


def test_gdelt_adapter_retries_network_timeouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    class FakeClient:
        def __init__(self, **_: Any) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def stream(
            self,
            method: str,
            url: str,
            *,
            params: dict[str, str],
        ) -> None:
            nonlocal attempts
            assert method == "GET"
            assert url == "https://api.gdeltproject.org/api/v2/doc/doc"
            assert params["maxrecords"] == "1"
            attempts += 1
            raise httpx.TimeoutException("timeout")

    monkeypatch.setattr("src.evidence_retrieval.httpx.Client", FakeClient)
    monkeypatch.setattr("src.evidence_retrieval.time.sleep", lambda _: None)
    source = GdeltDocSource(retry_limit=1)

    with pytest.raises(httpx.TimeoutException):
        source._fetch_json("India satellite", 1)

    assert attempts == 2


def test_gdelt_adapter_does_not_retry_tls_handshake_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    class FakeClient:
        def __init__(self, **_: Any) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def stream(
            self,
            method: str,
            url: str,
            *,
            params: dict[str, str],
        ) -> None:
            nonlocal attempts
            attempts += 1
            error = httpx.ConnectError("TLS handshake failed")
            error.__cause__ = ssl.SSLError("certificate verify failed")
            raise error

    monkeypatch.setattr("src.evidence_retrieval.httpx.Client", FakeClient)
    source = GdeltDocSource(retry_limit=2)

    with pytest.raises(httpx.ConnectError):
        source._fetch_json("India satellite", 1)

    assert attempts == 1


def test_api_endpoint_returns_search_results() -> None:
    source = MockSource([article()])
    retriever = EvidenceRetriever([source])
    app = create_app(
        settings=APISettings(cors_origins=()),
        evidence_retriever=retriever,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/retrieve-evidence",
            json={"claim": CLAIM, "claim_id": 4},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["claim_id"] == 4
    assert body["query"] == "India launched new satellite Monday"
    assert body["total_results"] == 1
    assert body["evidence"][0]["source_domain"] == "pib.gov.in"
    assert body["retrieval_status"] == "completed"


@pytest.mark.parametrize(
    "payload",
    [
        {"claim": ""},
        {"claim": "  "},
        {"claim": 42},
        {"claim": "claim", "claim_id": 0},
        {"claim": CLAIM},
    ],
)
def test_api_rejects_invalid_claim(payload: dict[str, Any]) -> None:
    app = create_app(
        settings=APISettings(cors_origins=()),
        evidence_retriever=EvidenceRetriever([]),
    )
    with TestClient(app) as client:
        response = client.post("/api/retrieve-evidence", json=payload)

    assert response.status_code == 422


def test_api_returns_empty_results_when_source_is_unavailable() -> None:
    app = create_app(
        settings=APISettings(cors_origins=()),
        evidence_retriever=EvidenceRetriever(
            [MockSource(error=httpx.ConnectError("network detail"))]
        ),
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/retrieve-evidence",
            json={"claim": CLAIM, "claim_id": 2},
        )

    assert response.status_code == 200
    assert response.json()["evidence"] == []
    assert response.json()["retrieval_status"] == "unavailable"
    assert "network detail" not in response.text
