from __future__ import annotations

import ssl
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.main import APISettings, create_app
from src.evidence_analyzer import EvidenceAnalyzer
from src.evidence_retrieval import build_search_query
from src.translation_service import TranslationService

HINDI_TEXT = "सरकार ने आज नई नीति की घोषणा की।"
ENGLISH_TRANSLATION = "The government announced a new policy today."


class FakeDetector:
    def __init__(self, code: str = "hi", status: str = "detected") -> None:
        self.code = code
        self.status = status

    def detect(self, text: str) -> dict[str, Any]:
        return {
            "language_code": self.code,
            "language_name": "Hindi" if self.code == "hi" else "Unknown",
            "detection_confidence": 0.99 if self.status == "detected" else None,
            "detection_status": self.status,
            **(
                {"warning": "Uncertain language."}
                if self.status != "detected"
                else {}
            ),
        }


class FakeClassifier:
    def __init__(self, prediction: str = "Real") -> None:
        self.inputs: list[str] = []
        self.prediction = prediction

    def predict(self, text: str) -> dict[str, Any]:
        self.inputs.append(text)
        return {
            "prediction": self.prediction,
            "label": 0 if self.prediction == "Fake" else 1,
        }


class UnavailableRetriever:
    def retrieve(self, claim: str, claim_id: int) -> dict[str, Any]:
        return {
            "claim_id": claim_id,
            "evidence": [],
            "retrieval_status": "unavailable",
        }


class StaticRetriever:
    def __init__(
        self,
        evidence: list[dict[str, Any]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.evidence = evidence or []
        self.error = error

    def retrieve(self, claim: str, claim_id: int) -> dict[str, Any]:
        if self.error is not None:
            raise self.error
        return {
            "claim_id": claim_id,
            "query": "council approved public plan",
            "evidence": self.evidence,
            "retrieval_status": "completed",
            "source_errors": [],
        }


class RecordingRetriever:
    def __init__(self, evidence: list[dict[str, Any]] | None = None) -> None:
        self.claims: list[str] = []
        self.evidence = evidence or []

    def retrieve(self, claim: str, claim_id: int) -> dict[str, Any]:
        self.claims.append(claim)
        return {
            "claim_id": claim_id,
            "query": build_search_query(claim),
            "evidence": self.evidence,
            "retrieval_status": "completed",
            "source_errors": [],
        }


class UnavailableTranslationService:
    def translate(self, text: str, source: str, target: str) -> dict[str, Any]:
        return {
            "original_text": text,
            "translated_text": None,
            "source_language": source,
            "target_language": target,
            "translation_status": "unavailable",
            "warnings": ["No local translation model is installed."],
            "error": "Translation model unavailable.",
        }


class CapturingAnalyzer:
    def __init__(self) -> None:
        self.evidence: list[dict[str, Any]] = []
        self.delegate = EvidenceAnalyzer()

    def analyze(
        self,
        claim: str,
        evidence: list[dict[str, Any]],
        claim_id: int,
        retrieval_status: str,
    ) -> dict[str, Any]:
        self.evidence = evidence
        return self.delegate.analyze(
            claim,
            evidence,
            claim_id,
            retrieval_status,
        )


@pytest.fixture
def client_and_classifier() -> tuple[TestClient, FakeClassifier]:
    classifier = FakeClassifier()
    app = create_app(
        classifier=classifier,  # type: ignore[arg-type]
        evidence_retriever=UnavailableRetriever(),  # type: ignore[arg-type]
        language_detector=FakeDetector(),  # type: ignore[arg-type]
        translation_service=TranslationService(
            lambda text, source, target: ENGLISH_TRANSLATION
        ),
    )
    return TestClient(app), classifier


def test_language_detection_endpoint_returns_consistent_shape() -> None:
    client = TestClient(create_app(language_detector=FakeDetector()))  # type: ignore[arg-type]

    response = client.post("/api/detect-language", json={"text": HINDI_TEXT})

    assert response.status_code == 200
    assert response.json() == {
        "language_code": "hi",
        "language_name": "Hindi",
        "detection_confidence": 0.99,
        "detection_status": "detected",
    }


def test_language_detection_endpoint_uses_real_local_detector() -> None:
    client = TestClient(create_app(classifier=FakeClassifier()))  # type: ignore[arg-type]

    response = client.post(
        "/api/detect-language",
        json={"text": "ప్రభుత్వం ఈ రోజు కొత్త విధానాన్ని ప్రకటించింది."},
    )

    assert response.status_code == 200
    assert response.json()["language_code"] == "te"
    assert response.json()["detection_status"] == "detected"


@pytest.mark.parametrize("payload", [{}, {"text": ""}, {"text": "  "}])
def test_language_endpoints_reject_empty_or_missing_text(
    payload: dict[str, object],
) -> None:
    client = TestClient(create_app(language_detector=FakeDetector()))  # type: ignore[arg-type]

    detected = client.post("/api/detect-language", json=payload)
    translated = client.post("/api/translate", json=payload)
    verified = client.post("/api/verify/multilingual", json=payload)

    assert detected.status_code == 422
    assert translated.status_code == 422
    assert verified.status_code == 422


def test_translate_endpoint_preserves_source_and_translation() -> None:
    client = TestClient(
        create_app(
            language_detector=FakeDetector(),  # type: ignore[arg-type]
            translation_service=TranslationService(
                lambda text, source, target: ENGLISH_TRANSLATION
            ),
        )
    )

    response = client.post("/api/translate", json={"text": HINDI_TEXT})

    assert response.status_code == 200
    result = response.json()
    assert result["original_text"] == HINDI_TEXT
    assert result["translated_text"] == ENGLISH_TRANSLATION
    assert result["source_language"] == "hi"
    assert result["translation_status"] == "translated"
    assert result["language_detection"]["language_code"] == "hi"


def test_uncertain_language_is_not_translated() -> None:
    client = TestClient(
        create_app(
            language_detector=FakeDetector("unknown", "uncertain"),  # type: ignore[arg-type]
            translation_service=TranslationService(
                lambda *_: pytest.fail("Translation must not be attempted.")
            ),
        )
    )

    response = client.post("/api/translate", json={"text": HINDI_TEXT})

    assert response.status_code == 422
    assert response.json()["translation_status"] == "uncertain"
    assert response.json()["translated_text"] is None


def test_unsupported_translation_language_returns_422() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/translate",
        json={"text": HINDI_TEXT, "source_language": "xx"},
    )

    assert response.status_code == 422
    assert response.json()["translation_status"] == "unsupported"


def test_multilingual_pipeline_uses_translation_and_preserves_original(
    client_and_classifier: tuple[TestClient, FakeClassifier],
) -> None:
    client, classifier = client_and_classifier

    response = client.post(
        "/api/verify/multilingual",
        json={"text": HINDI_TEXT},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["original_text"] == HINDI_TEXT
    assert body["translated_text"] == ENGLISH_TRANSLATION
    assert body["language_detection"]["language_code"] == "hi"
    assert body["verification_status"] == "completed"
    assert classifier.inputs == [ENGLISH_TRANSLATION]
    assert "translation is not evidence" in body["warnings"][-1]
    assert body["pipeline"]["classifier"]["prediction"] == "Real"
    assert body["pipeline"]["classifier"]["interpretation"].endswith(
        "not a factual verdict."
    )
    assert body["pipeline"]["claim_assessments"][0]["analysis"]["verdict"] == (
        "INSUFFICIENT EVIDENCE"
    )


def test_multilingual_pipeline_with_real_detector_and_mocked_translation() -> None:
    classifier = FakeClassifier()
    translated = "The government announced a new policy today."
    client = TestClient(
        create_app(
            classifier=classifier,  # type: ignore[arg-type]
            evidence_retriever=UnavailableRetriever(),  # type: ignore[arg-type]
            translation_service=TranslationService(
                lambda text, source, target: translated
            ),
        )
    )

    response = client.post(
        "/api/verify/multilingual",
        json={"text": "ప్రభుత్వం ఈ రోజు కొత్త విధానాన్ని ప్రకటించింది."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["language_detection"]["language_code"] == "te"
    assert body["translated_text"] == translated
    assert classifier.inputs == [translated]
    assert body["pipeline"]["claim_assessments"][0]["analysis"]["verdict"] == (
        "INSUFFICIENT EVIDENCE"
    )


def test_multilingual_pipeline_continues_when_translation_is_unavailable() -> None:
    classifier = FakeClassifier()
    client = TestClient(
        create_app(
            classifier=classifier,  # type: ignore[arg-type]
            language_detector=FakeDetector(),  # type: ignore[arg-type]
            translation_service=UnavailableTranslationService(),  # type: ignore[arg-type]
            evidence_retriever=UnavailableRetriever(),  # type: ignore[arg-type]
        )
    )

    response = client.post(
        "/api/verify/multilingual",
        json={"text": HINDI_TEXT},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["translation_status"] == "unavailable"
    assert body["translated_text"] is None
    assert body["original_text"] == HINDI_TEXT
    assert body["verification_status"] == "completed"
    assert body["pipeline"]["final_verdict"] == "INSUFFICIENT EVIDENCE"
    assert body["pipeline"]["claim_assessments"][0]["analysis"]["verdict"] == (
        "INSUFFICIENT EVIDENCE"
    )
    assert classifier.inputs == [HINDI_TEXT]


def test_telugu_claim_is_searched_when_translation_is_unavailable() -> None:
    telugu_text = "ప్రభుత్వం ఈ రోజు కొత్త విధానాన్ని ప్రకటించింది."
    retriever = RecordingRetriever(
        [
            {
                "evidence_id": "EV1",
                "claim_id": 1,
                "source_name": "Press Information Bureau",
                "source_domain": "pib.gov.in",
                "source_url": "https://pib.gov.in/example",
                "title": telugu_text,
                "snippet": telugu_text,
                "source_type": "official",
                "relevance_score": 1.0,
            }
        ]
    )
    classifier = FakeClassifier("Fake")
    client = TestClient(
        create_app(
            classifier=classifier,  # type: ignore[arg-type]
            evidence_retriever=retriever,  # type: ignore[arg-type]
            translation_service=UnavailableTranslationService(),  # type: ignore[arg-type]
        )
    )

    response = client.post(
        "/api/verify/multilingual",
        json={"text": telugu_text},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["language_detection"]["language_code"] == "te"
    assert body["original_text"] == telugu_text
    assert body["translated_text"] is None
    assert body["pipeline"]["claims"][0]["claim_text"] == telugu_text
    assert retriever.claims == [telugu_text]
    assert "ప్రభుత్వం" in body["pipeline"]["claim_assessments"][0]["query"]
    # Non-Latin text is assessed as INSUFFICIENT (not NEUTRAL) by the analyzer
    assert body["pipeline"]["claim_assessments"][0]["analysis"]["insufficient_evidence"]
    assert body["pipeline"]["final_verdict"] == "INSUFFICIENT EVIDENCE"
    assert body["pipeline"]["classifier"]["prediction"] == "Fake"



@pytest.mark.parametrize(
    ("evidence_text", "prediction", "expected_verdict"),
    [
        ("The council approved a new public plan.", "Fake", "TRUE"),
        ("The council rejected a new public plan.", "Real", "FALSE"),
    ],
)
def test_retrieved_evidence_reaches_analyzer_and_classifier_does_not_set_verdict(
    evidence_text: str,
    prediction: str,
    expected_verdict: str,
) -> None:
    evidence = [
        {
            "evidence_id": f"EV{index}",
            "claim_id": 1,
            "source_name": domain,
            "source_domain": domain,
            "source_url": f"https://{domain}/story",
            "title": f"{domain} coverage: {evidence_text}",
            "snippet": f"{evidence_text} Source reporting from {domain}.",
            "published_date": None,
            "retrieved_at": "",
            "source_type": "news",
            "relevance_score": 1.0,
            "retrieval_status": "retrieved",
        }
        for index, domain in enumerate(("reuters.com", "apnews.com"), start=1)
    ]
    analyzer = CapturingAnalyzer()
    app = create_app(
        classifier=FakeClassifier(prediction),  # type: ignore[arg-type]
        evidence_retriever=StaticRetriever(evidence),  # type: ignore[arg-type]
        language_detector=FakeDetector("en"),  # type: ignore[arg-type]
        translation_service=TranslationService(),
    )
    app.state.evidence_analyzer = analyzer

    with TestClient(app) as client:
        response = client.post(
            "/api/verify/multilingual",
            json={"text": "The council approved a new public plan."},
        )

    assert response.status_code == 200
    pipeline = response.json()["pipeline"]
    assert pipeline["classifier"]["prediction"] == prediction
    assert pipeline["final_verdict"] == (
        "REAL" if expected_verdict == "TRUE" else "FAKE"
    )
    assert pipeline["claim_assessments"][0]["analysis"]["verdict"] == (
        expected_verdict
    )
    assert analyzer.evidence == evidence
    assert pipeline["claim_assessments"][0]["evidence"][0]["source_url"] == (
        "https://reuters.com/story"
    )


def test_conflicting_evidence_keeps_final_verdict_insufficient() -> None:
    evidence = [
        {
            "evidence_id": "EV1",
            "claim_id": 1,
            "source_name": "Reuters",
            "source_domain": "reuters.com",
            "source_url": "https://reuters.com/approved",
            "title": "Council approved a public plan",
            "snippet": "The council approved a new public plan.",
            "source_type": "news",
            "relevance_score": 1.0,
        },
        {
            "evidence_id": "EV2",
            "claim_id": 1,
            "source_name": "Associated Press",
            "source_domain": "apnews.com",
            "source_url": "https://apnews.com/rejected",
            "title": "Council rejected a public plan",
            "snippet": "The council rejected a new public plan.",
            "source_type": "news",
            "relevance_score": 1.0,
        },
    ]
    app = create_app(
        classifier=FakeClassifier("Real"),  # type: ignore[arg-type]
        evidence_retriever=StaticRetriever(evidence),  # type: ignore[arg-type]
        language_detector=FakeDetector("en"),  # type: ignore[arg-type]
        translation_service=TranslationService(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/verify/multilingual",
            json={"text": "The council approved a new public plan."},
        )

    assert response.status_code == 200
    pipeline = response.json()["pipeline"]
    # New behavior: conflicting evidence from credible sources -> NEEDS HUMAN REVIEW
    assert pipeline["claim_assessments"][0]["analysis"]["verdict"] == (
        "NEEDS HUMAN REVIEW"
    )
    # Check that there are both supporting and contradicting evidence from credible sources
    assert pipeline["claim_assessments"][0]["analysis"]["supporting_evidence"]
    assert pipeline["claim_assessments"][0]["analysis"]["contradicting_evidence"]
    assert pipeline["final_verdict"] == "NEEDS HUMAN REVIEW"


def test_irrelevant_results_remain_insufficient_evidence() -> None:
    evidence = [
        {
            "evidence_id": "EV1",
            "claim_id": 1,
            "source_name": "unknown.example",
            "source_domain": "unknown.example",
            "source_url": "https://unknown.example/weather",
            "title": "Coastal weather forecast",
            "snippet": "Heavy rain is expected near the coast.",
            "published_date": None,
            "retrieved_at": "",
            "source_type": "unknown",
            "relevance_score": 0.0,
            "retrieval_status": "retrieved",
        }
    ]
    app = create_app(
        classifier=FakeClassifier(),  # type: ignore[arg-type]
        evidence_retriever=StaticRetriever(evidence),  # type: ignore[arg-type]
        language_detector=FakeDetector("en"),  # type: ignore[arg-type]
        translation_service=TranslationService(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/verify/multilingual",
            json={"text": "The council approved a new public plan."},
        )

    assert response.status_code == 200
    assessment = response.json()["pipeline"]["claim_assessments"][0]
    assert assessment["analysis"]["verdict"] == "INSUFFICIENT EVIDENCE"
    assert response.json()["pipeline"]["final_verdict"] == "INSUFFICIENT EVIDENCE"
    assert assessment["analysis"]["neutral_evidence"][0]["source_url"] == (
        "https://unknown.example/weather"
    )


def test_retrieval_timeout_returns_insufficient_evidence() -> None:
    app = create_app(
        classifier=FakeClassifier("Real"),  # type: ignore[arg-type]
        evidence_retriever=StaticRetriever(error=httpx.TimeoutException("timeout")),  # type: ignore[arg-type]
        language_detector=FakeDetector("en"),  # type: ignore[arg-type]
        translation_service=TranslationService(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/verify/multilingual",
            json={"text": "The council approved a new public plan."},
        )

    assert response.status_code == 200
    pipeline = response.json()["pipeline"]
    assessment = pipeline["claim_assessments"][0]
    assert assessment["retrieval_status"] == "unavailable"
    assert assessment["source_errors"] == [
        {"source": "web evidence retrieval", "error": "timeout"}
    ]
    assert assessment["analysis"]["verdict"] == "INSUFFICIENT EVIDENCE"
    assert pipeline["final_verdict"] == "INSUFFICIENT EVIDENCE"


def test_tls_failure_returns_insufficient_evidence_with_clear_status() -> None:
    error = httpx.ConnectError("TLS handshake failed")
    error.__cause__ = ssl.SSLError("certificate verify failed")
    app = create_app(
        classifier=FakeClassifier("Real"),  # type: ignore[arg-type]
        evidence_retriever=StaticRetriever(error=error),  # type: ignore[arg-type]
        language_detector=FakeDetector("en"),  # type: ignore[arg-type]
        translation_service=TranslationService(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/verify/multilingual",
            json={"text": "The council approved a new public plan."},
        )

    assert response.status_code == 200
    assessment = response.json()["pipeline"]["claim_assessments"][0]
    assert assessment["retrieval_status"] == "unavailable"
    assert assessment["source_errors"] == [
        {"source": "web evidence retrieval", "error": "tls_error"}
    ]
    assert assessment["analysis"]["verdict"] == "INSUFFICIENT EVIDENCE"
    assert response.json()["pipeline"]["final_verdict"] == "INSUFFICIENT EVIDENCE"


def test_fake_classifier_prediction_cannot_create_a_false_verdict() -> None:
    app = create_app(
        classifier=FakeClassifier("Fake"),  # type: ignore[arg-type]
        evidence_retriever=UnavailableRetriever(),  # type: ignore[arg-type]
        language_detector=FakeDetector("en"),  # type: ignore[arg-type]
        translation_service=TranslationService(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/verify/multilingual",
            json={"text": "The council approved a new public plan."},
        )

    assert response.status_code == 200
    pipeline = response.json()["pipeline"]
    assert pipeline["classifier"]["prediction"] == "Fake"
    assessment = pipeline["claim_assessments"][0]
    assert assessment["retrieval_status"] == "unavailable"
    assert assessment["analysis"]["verdict"] == "INSUFFICIENT EVIDENCE"
    assert pipeline["final_verdict"] == "INSUFFICIENT EVIDENCE"


def test_public_article_url_text_is_added_as_direct_evidence() -> None:
    source_url = "https://news.example/article"

    class ProcessedArticleInput:
        def process(self, value: str, input_type: str) -> dict[str, Any]:
            assert value == source_url
            assert input_type == "url"
            return {
                "processing_status": "processed",
                "extracted_text": "The council approved a new public plan.",
                "source_url": source_url,
                "title": "Council approves public plan",
            }

    analyzer = CapturingAnalyzer()
    app = create_app(
        classifier=FakeClassifier(),  # type: ignore[arg-type]
        evidence_retriever=StaticRetriever(),  # type: ignore[arg-type]
        input_processor=ProcessedArticleInput(),  # type: ignore[arg-type]
        language_detector=FakeDetector("en"),  # type: ignore[arg-type]
        translation_service=TranslationService(),
    )
    app.state.evidence_analyzer = analyzer

    with TestClient(app) as client:
        response = client.post(
            "/api/verify/multilingual",
            json={
                "text": "The council approved a new public plan.",
                "source_url": source_url,
            },
        )

    assert response.status_code == 200
    assert len(analyzer.evidence) == 1
    assert analyzer.evidence[0]["source_url"] == source_url
    assert analyzer.evidence[0]["title"] == "Council approves public plan"
    assert analyzer.evidence[0]["snippet"] == (
        "The council approved a new public plan."
    )


def test_official_article_is_evidence_but_not_automatically_true() -> None:
    source_url = "https://pib.gov.in/article"
    article_text = (
        "The council approved a new public plan after a recorded vote."
    )

    class ProcessedOfficialArticle:
        def process(self, value: str, input_type: str) -> dict[str, Any]:
            return {
                "processing_status": "processed",
                "extracted_text": article_text,
                "source_url": source_url,
                "title": "Public plan approved",
            }

    analyzer = CapturingAnalyzer()
    app = create_app(
        classifier=FakeClassifier("Fake"),  # type: ignore[arg-type]
        evidence_retriever=UnavailableRetriever(),  # type: ignore[arg-type]
        input_processor=ProcessedOfficialArticle(),  # type: ignore[arg-type]
        language_detector=FakeDetector("en"),  # type: ignore[arg-type]
        translation_service=TranslationService(),
    )
    app.state.evidence_analyzer = analyzer

    with TestClient(app) as client:
        response = client.post(
            "/api/verify/multilingual",
            json={
                "text": "The council approved a new public plan.",
                "source_url": source_url,
            },
        )

    assert response.status_code == 200
    pipeline = response.json()["pipeline"]
    assessment = pipeline["claim_assessments"][0]
    assert pipeline["classifier"]["prediction"] == "Fake"
    assert len(analyzer.evidence) == 1
    assert analyzer.evidence[0]["source_type"] == "official"
    assert analyzer.evidence[0]["source_url"] == source_url
    assert assessment["analysis"]["verdict"] == "INSUFFICIENT EVIDENCE"


def test_missing_classifier_does_not_block_evidence_verification(
    tmp_path: Path,
) -> None:
    evidence = [
        {
            "evidence_id": f"EV{index}",
            "claim_id": 1,
            "source_name": domain,
            "source_domain": domain,
            "source_url": f"https://{domain}/story",
            "title": f"{domain} coverage of council plan",
            "snippet": (
                f"The council approved a new public plan, according to {domain}."
            ),
            "published_date": None,
            "retrieved_at": "",
            "source_type": "news",
            "relevance_score": 1.0,
            "retrieval_status": "retrieved",
        }
        for index, domain in enumerate(("reuters.com", "apnews.com"), start=1)
    ]
    app = create_app(
        settings=APISettings(model_dir=tmp_path / "missing-model"),
        evidence_retriever=StaticRetriever(evidence),  # type: ignore[arg-type]
        language_detector=FakeDetector("en"),  # type: ignore[arg-type]
        translation_service=TranslationService(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/verify/multilingual",
            json={"text": "The council approved a new public plan."},
        )

    assert response.status_code == 200
    assert response.json()["pipeline"]["classifier"] is None
    assert response.json()["pipeline"]["claim_assessments"][0]["analysis"][
        "verdict"
    ] == "TRUE"


def test_uncertain_or_mixed_input_continues_without_translation() -> None:
    client = TestClient(
        create_app(
            language_detector=FakeDetector("mixed", "mixed"),  # type: ignore[arg-type]
            translation_service=TranslationService(
                lambda *_: pytest.fail("Translation must not be attempted.")
            ),
        )
    )

    response = client.post(
        "/api/verify/multilingual",
        json={"text": "English and regional language"},
    )

    assert response.status_code == 200
    assert response.json()["verification_status"] == "completed"
    assert response.json()["translation_status"] == "uncertain"
    assert response.json()["pipeline"]["final_verdict"] == "INSUFFICIENT EVIDENCE"


def test_api_keeps_all_existing_and_adds_multilingual_routes() -> None:
    client = TestClient(create_app())
    paths = {route.path for route in client.app.routes}
    existing = {
        "/api/health",
        "/api/classify",
        "/api/verify/text",
        "/api/extract-claims",
        "/api/retrieve-evidence",
        "/api/analyze-evidence",
        "/api/process-input",
        "/api/process-image",
    }

    assert existing <= paths
    assert {
        "/api/detect-language",
        "/api/translate",
        "/api/verify/multilingual",
    } <= paths
