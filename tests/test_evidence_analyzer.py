from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.main import APISettings, create_app
from src.evidence_analyzer import (
    EvidenceAnalysisInputError,
    EvidenceAnalyzer,
)

CLAIM = "The council approved the bill."


def evidence(
    *,
    evidence_id: str = "EV001",
    domain: str = "pib.gov.in",
    url: str | None = "https://pib.gov.in/bill",
    title: str = "The council approved the bill",
    snippet: str = "The council approved the bill.",
    published_date: str | None = "2026-10-12T00:00:00Z",
    **extra: Any,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "evidence_id": evidence_id,
        "source_name": domain,
        "source_domain": domain,
        "source_url": url,
        "title": title,
        "snippet": snippet,
        "published_date": published_date,
        "relevance_score": 1.0,
    }
    item.update(extra)
    return item


def two_sources(
    snippet: str,
    title: str = "The council approved the bill",
) -> list[dict[str, Any]]:
    second_snippet = (
        "The council did not approve the bill."
        if "rejected" in snippet.casefold()
        else "The council approved the bill, according to its published vote record."
    )
    second_title = (
        "Council decision rejected the bill"
        if "rejected" in snippet.casefold()
        else "Council approval followed a vote"
    )
    return [
        evidence(
            evidence_id="EV001",
            domain="pib.gov.in",
            url="https://pib.gov.in/first",
            title=title,
            snippet=snippet,
        ),
        evidence(
            evidence_id="EV002",
            domain="www.gov.uk",
            url="https://www.gov.uk/second",
            title=second_title,
            snippet=second_snippet,
        ),
    ]


def test_empty_evidence_returns_insufficient_evidence() -> None:
    result = EvidenceAnalyzer().analyze(CLAIM, [])

    assert result["verdict"] == "INSUFFICIENT EVIDENCE"
    assert result["confidence"] is None
    assert result["supporting_evidence"] == []
    assert result["contradicting_evidence"] == []
    assert "No evidence was supplied" in result["explanation"]


def test_retrieval_failure_never_produces_false() -> None:
    result = EvidenceAnalyzer().analyze(
        CLAIM,
        [],
        retrieval_status="unavailable",
    )

    assert result["verdict"] == "INSUFFICIENT EVIDENCE"
    assert result["confidence"] is None
    assert "retrieval was unavailable" in result["explanation"]


def test_multiple_independent_credible_sources_can_support_true() -> None:
    result = EvidenceAnalyzer().analyze(CLAIM, two_sources(CLAIM))

    assert result["verdict"] == "TRUE"
    assert result["confidence"] == 0.75
    assert "not a statistically calibrated probability" in result["confidence_type"]
    assert len(result["supporting_evidence"]) == 2
    assert result["supporting_evidence"][0]["source_url"] == "https://pib.gov.in/first"
    assert result["supporting_evidence"][0]["source_name"] == "pib.gov.in"
    assert len(result["sources_used"]) == 2


def test_multiple_independent_credible_sources_can_support_false() -> None:
    result = EvidenceAnalyzer().analyze(
        CLAIM,
        two_sources("The council rejected the bill."),
    )

    assert result["verdict"] == "FALSE"
    assert len(result["contradicting_evidence"]) == 2


def test_conflicting_support_and_contradiction_remain_insufficient() -> None:
    result = EvidenceAnalyzer().analyze(
        CLAIM,
        [
            evidence(
                evidence_id="EV001",
                domain="pib.gov.in",
                url="https://pib.gov.in/approved",
            ),
            evidence(
                evidence_id="EV002",
                domain="www.gov.uk",
                url="https://www.gov.uk/rejected",
                title="The council rejected the bill",
                snippet="The council rejected the bill.",
            ),
        ],
    )

    # New behavior: conflicting evidence from credible sources -> NEEDS HUMAN REVIEW
    assert result["verdict"] == "NEEDS HUMAN REVIEW"
    # Check that there are both supporting and contradicting evidence from credible sources
    assert len(result["supporting_evidence"]) >= 1
    assert len(result["contradicting_evidence"]) >= 1
    assert "conflict" in result["explanation"].lower()


def test_one_weak_source_never_suffices_for_true_or_false() -> None:
    result = EvidenceAnalyzer().analyze(
        CLAIM,
        [evidence(domain="unknown.example", url="https://unknown.example/bill")],
    )

    assert result["verdict"] == "INSUFFICIENT EVIDENCE"
    assert result["confidence"] is None


def test_irrelevant_evidence_is_neutral() -> None:
    result = EvidenceAnalyzer().analyze(
        CLAIM,
        [
            evidence(
                domain="who.int",
                url="https://who.int/health",
                title="Global health report",
                snippet="A global report describes trends in seasonal illness.",
            )
        ],
    )

    assert result["verdict"] == "INSUFFICIENT EVIDENCE"
    assert len(result["neutral_evidence"]) == 1
    assert result["sources_used"] == []


def test_missing_source_metadata_and_publication_date_are_safe() -> None:
    item = {
        "evidence_id": "EV001",
        "title": "The council approved the bill",
        "snippet": "The council approved the bill.",
    }

    result = EvidenceAnalyzer().analyze(CLAIM, [item])

    assert result["verdict"] == "INSUFFICIENT EVIDENCE"
    assert result["supporting_evidence"][0]["source_name"] is None
    assert result["supporting_evidence"][0]["source_domain"] is None
    assert result["supporting_evidence"][0]["source_url"] is None
    assert result["supporting_evidence"][0]["published_date"] is None
    assert any("Publication dates were missing" in item for item in result["limitations"])
    assert any("Source domains were missing" in item for item in result["limitations"])


def test_explanation_uses_assessment_not_invented_facts() -> None:
    result = EvidenceAnalyzer().analyze(
        CLAIM,
        [
            evidence(
                title="A supplied title",
                snippet="The council approved the bill.",
            )
        ],
    )

    assert "A supplied title" not in result["explanation"]
    assert result["explanation"] == (
        "Some supplied text matches the claim, but there are not enough independent recognized credible sources for a decisive verdict."
    )


def test_duplicate_evidence_does_not_increase_confidence() -> None:
    duplicate = evidence()
    result = EvidenceAnalyzer().analyze(CLAIM, [duplicate, dict(duplicate)])

    assert result["verdict"] == "INSUFFICIENT EVIDENCE"
    assert result["confidence"] is None
    assert len(result["supporting_evidence"]) == 1


def test_cross_domain_copies_of_same_evidence_do_not_inflate_confidence() -> None:
    items = [
        evidence(
            evidence_id="EV001",
            domain="pib.gov.in",
            url="https://pib.gov.in/original",
        ),
        evidence(
            evidence_id="EV002",
            domain="www.gov.uk",
            url="https://www.gov.uk/copy",
        ),
    ]

    result = EvidenceAnalyzer().analyze(CLAIM, items)

    assert result["verdict"] == "INSUFFICIENT EVIDENCE"
    assert result["confidence"] is None
    assert len(result["supporting_evidence"]) == 1


def test_explicit_context_warning_can_be_labeled_misleading() -> None:
    items = [
        evidence(
            evidence_id="EV001",
            domain="altnews.in",
            url="https://altnews.in/context",
            title="Alt News context review",
            snippet=(
                "The council approved bill claim is misleading and out of context."
            ),
        ),
        evidence(
            evidence_id="EV002",
            domain="factly.in",
            url="https://factly.in/context",
            title="Factly context analysis",
            snippet=(
                "The council approved bill claim is misleading and out of context."
            ),
        ),
    ]

    result = EvidenceAnalyzer().analyze(CLAIM, items)

    assert result["verdict"] == "MISLEADING"
    assert result["confidence"] == 0.7


def test_distinct_parts_can_produce_partially_true_cautiously() -> None:
    claim = "The council approved the bill and the tax rate fell."
    items = [
        evidence(
            evidence_id="EV001",
            domain="pib.gov.in",
            url="https://pib.gov.in/approval",
            title="The council approved the bill",
            snippet="The council approved the bill.",
        ),
        evidence(
            evidence_id="EV002",
            domain="www.gov.uk",
            url="https://www.gov.uk/rate",
            title="The tax rate rose",
            snippet="The national tax rate rose.",
        ),
    ]

    result = EvidenceAnalyzer().analyze(claim, items)

    assert result["verdict"] == "PARTIALLY TRUE"
    # In new stance labels, evidence is categorized by overall stance
    # Component assessments show partial support/contradiction
    assert "partial" in result["explanation"].lower() or "part" in result["explanation"].lower()
    assert result["confidence"] == 0.65


@pytest.mark.parametrize(
    ("claim", "items", "claim_id"),
    [
        (" ", [], 1),
        (None, [], 1),
        (CLAIM, "not a list", 1),
        (CLAIM, [None], 1),
        (CLAIM, [evidence(url="javascript:alert(1)")], 1),
        (CLAIM, [evidence(url="https://other.example/x", domain="pib.gov.in")], 1),
        (CLAIM, [], 0),
        (CLAIM, [], True),
    ],
)
def test_invalid_analyzer_inputs_are_rejected_safely(
    claim: Any,
    items: Any,
    claim_id: Any,
) -> None:
    with pytest.raises((EvidenceAnalysisInputError, TypeError)):
        EvidenceAnalyzer().analyze(claim, items, claim_id=claim_id)


@pytest.fixture
def api_client() -> TestClient:
    app = create_app(settings=APISettings(cors_origins=()))
    return TestClient(app)


@pytest.mark.parametrize(
    ("items", "expected_verdict"),
    [
        (two_sources(CLAIM), "TRUE"),
        (two_sources("The council rejected the bill."), "FALSE"),
        ([], "INSUFFICIENT EVIDENCE"),
        (
            [
                evidence(
                    evidence_id="EV001",
                    domain="pib.gov.in",
                    url="https://pib.gov.in/approved",
                ),
                evidence(
                    evidence_id="EV002",
                    domain="www.gov.uk",
                    url="https://www.gov.uk/rejected",
                    title="The council rejected the bill",
                    snippet="The council rejected the bill.",
                ),
            ],
            "NEEDS HUMAN REVIEW",
        ),
    ],
)
def test_analyze_evidence_api_verdict_cases(
    api_client: TestClient,
    items: list[dict[str, Any]],
    expected_verdict: str,
) -> None:
    response = api_client.post(
        "/api/analyze-evidence",
        json={"claim": CLAIM, "claim_id": 3, "evidence": items},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["claim_id"] == 3
    assert body["original_claim"] == CLAIM
    assert body["verdict"] == expected_verdict
    # New response includes stance-based evidence categories
    assert "supporting_evidence" in body
    assert "contradicting_evidence" in body
    assert "mixed_evidence" in body
    assert "neutral_evidence" in body
    assert "insufficient_evidence" in body
    assert "limitations" in body


@pytest.mark.parametrize(
    "payload",
    [
        {"claim": "", "claim_id": 1, "evidence": []},
        {"claim": "  ", "claim_id": 1, "evidence": []},
        {"claim": CLAIM, "claim_id": 1, "evidence": "invalid"},
        {"claim": CLAIM, "claim_id": 1, "evidence": [{"source_url": "file://bad"}]},
    ],
)
def test_analyze_evidence_api_rejects_invalid_input(
    api_client: TestClient,
    payload: dict[str, Any],
) -> None:
    response = api_client.post("/api/analyze-evidence", json=payload)

    assert response.status_code == 422
