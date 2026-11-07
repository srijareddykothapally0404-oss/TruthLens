from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import APISettings, create_app
from src.claim_extractor import (
    DEFAULT_MAX_INPUT_LENGTH,
    ArticleTooLongError,
    extract_claims,
)
from src.evidence_retrieval import build_search_query


def test_extracts_multiple_factual_statements() -> None:
    result = extract_claims(
        "India launched a new satellite on Monday. "
        "The satellite will support weather forecasting."
    )

    assert result["success"] is True
    assert result["total_claims"] == 2
    assert len(result["claims"]) == 2
    # First claim
    claim1 = result["claims"][0]
    assert claim1["claim_id"] == 1
    assert claim1["claim_text"] == "India launched a new satellite on Monday."
    assert claim1["claim_type"] == "factual"
    assert claim1["verification_status"] == "pending"
    assert "start_offset" in claim1
    assert "end_offset" in claim1
    assert "parent_claim_id" in claim1
    assert "is_compound" in claim1
    assert "compound_parts" in claim1
    # Second claim
    claim2 = result["claims"][1]
    assert claim2["claim_id"] == 2
    assert claim2["claim_text"] == "The satellite will support weather forecasting."
    assert claim2["claim_type"] == "factual"
    assert claim2["verification_status"] == "pending"
    assert "start_offset" in claim2
    assert "end_offset" in claim2
    assert "parent_claim_id" in claim2
    assert "is_compound" in claim2
    assert "compound_parts" in claim2


def test_extracts_single_factual_statement() -> None:
    result = extract_claims("The council approved the proposal.")

    assert result["total_claims"] == 1
    assert result["claims"][0]["claim_text"] == "The council approved the proposal."


def test_extracts_telugu_claim_and_preserves_complete_unicode_words() -> None:
    text = "ప్రభుత్వం ఈ రోజు కొత్త విధానాన్ని ప్రకటించింది."

    result = extract_claims(text)
    query = build_search_query(result["claims"][0]["claim_text"])

    assert result["total_claims"] == 1
    assert result["claims"][0]["claim_text"] == text
    assert "ప్రభుత్వం" in query
    assert "విధానాన్ని" in query


@pytest.mark.parametrize("text", ["", " \t\r\n"])
def test_rejects_empty_and_whitespace_input(text: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        extract_claims(text)


def test_rejects_invalid_input_type() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        extract_claims(None)  # type: ignore[arg-type]


def test_removes_duplicate_sentences_and_keeps_first_wording() -> None:
    result = extract_claims(
        "The council approved the proposal. "
        "The council approved the proposal. "
        "THE COUNCIL APPROVED THE PROPOSAL."
    )

    assert result["total_claims"] == 1
    assert result["claims"][0]["claim_id"] == 1
    assert result["claims"][0]["claim_text"] == "The council approved the proposal."


def test_skips_headings_and_fragments_but_extracts_statement() -> None:
    result = extract_claims(
        "Breaking News\n"
        "A major announcement\n"
        "The government approved the measure."
    )

    assert [claim["claim_text"] for claim in result["claims"]] == [
        "The government approved the measure."
    ]


def test_rejects_oversized_article_and_supports_custom_limit() -> None:
    article = "The council approved the proposal."
    with pytest.raises(ArticleTooLongError, match="maximum length"):
        extract_claims(article, max_length=len(article) - 1)

    assert extract_claims(article, max_length=len(article))["total_claims"] == 1
    with pytest.raises(ArticleTooLongError):
        extract_claims("x" * (DEFAULT_MAX_INPUT_LENGTH + 1))


def test_returns_empty_claim_list_for_text_without_factual_statement() -> None:
    result = extract_claims(
        "Breaking news! What happens next? Did officials approve the bill? "
        "A major announcement about tomorrow"
    )

    assert result == {"success": True, "total_claims": 0, "claims": []}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(
        settings=APISettings(
            model_dir=tmp_path / "models",
            cors_origins=(),
        ),
        classifier=object(),  # Claim extraction does not use the classifier.
    )
    return TestClient(app)


def test_claim_extraction_api_response_format(client: TestClient) -> None:
    response = client.post(
        "/api/extract-claims",
        json={
            "text": (
                "India launched a new satellite on Monday. "
                "The satellite will support weather forecasting."
            )
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total_claims"] == 2
    assert len(data["claims"]) == 2
    # First claim
    claim1 = data["claims"][0]
    assert claim1["claim_id"] == 1
    assert claim1["claim_text"] == "India launched a new satellite on Monday."
    assert claim1["claim_type"] == "factual"
    assert claim1["verification_status"] == "pending"
    assert "start_offset" in claim1
    assert "end_offset" in claim1
    assert "parent_claim_id" in claim1
    assert "is_compound" in claim1
    assert "compound_parts" in claim1
    # Second claim
    claim2 = data["claims"][1]
    assert claim2["claim_id"] == 2
    assert claim2["claim_text"] == "The satellite will support weather forecasting."
    assert claim2["claim_type"] == "factual"
    assert claim2["verification_status"] == "pending"
    assert "start_offset" in claim2
    assert "end_offset" in claim2
    assert "parent_claim_id" in claim2
    assert "is_compound" in claim2
    assert "compound_parts" in claim2


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        ({"text": ""}, 422),
        ({"text": "   "}, 422),
        ({"text": 42}, 422),
        ({}, 422),
    ],
)
def test_claim_extraction_api_rejects_invalid_text(
    client: TestClient,
    payload: dict[str, object],
    expected_status: int,
) -> None:
    response = client.post("/api/extract-claims", json=payload)

    assert response.status_code == expected_status


def test_claim_extraction_api_rejects_oversized_article(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/extract-claims",
        json={"text": "x" * (DEFAULT_MAX_INPUT_LENGTH + 1)},
    )

    assert response.status_code == 413
    assert "maximum length" in response.json()["detail"]


def test_existing_api_endpoints_remain_registered(client: TestClient) -> None:
    paths = {route.path for route in client.app.routes}

    assert "/api/health" in paths
    assert "/api/classify" in paths
    assert "/api/verify/text" in paths
    assert "/api/extract-claims" in paths
