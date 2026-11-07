from pathlib import Path

import joblib
import pytest
from fastapi.testclient import TestClient
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC

from backend.app.main import APISettings, CLASSIFIER_NAME, create_app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    texts = [
        "fabricated fake rumor story",
        "invented false report rumor",
        "confirmed official verified report",
        "reliable confirmed factual statement",
    ]
    labels = [0, 0, 1, 1]
    vectorizer = TfidfVectorizer()
    features = vectorizer.fit_transform(texts)
    classifier = LinearSVC(random_state=42).fit(features, labels)
    joblib.dump(vectorizer, model_dir / "tfidf_vectorizer.joblib")
    joblib.dump(classifier, model_dir / "linear_svm_model.joblib")

    app = create_app(
        settings=APISettings(
            version="test",
            model_dir=model_dir,
            cors_origins=(
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://127.0.0.1:4173",
            ),
        )
    )
    return TestClient(app)


def test_health_endpoint_reports_classifier_available(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "api_version": "test",
        "classifier_available": True,
    }


def test_cors_allows_configured_local_frontend(client: TestClient) -> None:
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_allows_vite_loopback_origin(client: TestClient) -> None:
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_cors_allows_vite_preview_origin(client: TestClient) -> None:
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://127.0.0.1:4173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:4173"


def test_classification_endpoint_uses_classifier(client: TestClient) -> None:
    response = client.post(
        "/api/classify",
        json={"text": "fabricated fake rumor"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "prediction": "Fake",
        "label": 0,
        "classifier": CLASSIFIER_NAME,
        "explanation": (
            "This is a pattern-based prediction from the classifier, not factual "
            "verification."
        ),
    }


@pytest.mark.parametrize("payload", [{"text": ""}, {"text": " \t "}, {}])
def test_classification_rejects_empty_or_missing_text(
    client: TestClient,
    payload: dict[str, str],
) -> None:
    response = client.post("/api/classify", json=payload)

    assert response.status_code == 422


def test_verification_endpoint_returns_pending_without_final_verdict(
    client: TestClient,
) -> None:
    text = "  confirmed official report  "
    response = client.post("/api/verify/text", json={"text": text})

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == text
    assert body["prediction"] == "Real"
    assert body["label"] == 1
    assert body["verification_status"] == "pending"
    assert body["final_verdict"] is None
    assert "/api/verify" in body["verification_notice"]


def test_missing_model_is_reported_by_health_and_classification(
    tmp_path: Path,
) -> None:
    app = create_app(
        settings=APISettings(
            version="test",
            model_dir=tmp_path / "missing-models",
            cors_origins=(),
        )
    )
    with TestClient(app) as client:
        health = client.get("/api/health")
        classification = client.post(
            "/api/classify",
            json={"text": "sample article"},
        )

    assert health.status_code == 200
    assert health.json()["status"] == "degraded"
    assert health.json()["classifier_available"] is False
    assert classification.status_code == 503
    assert "unavailable" in classification.json()["detail"]


def test_invalid_request_body_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/classify",
        content='{"text": 42}',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
