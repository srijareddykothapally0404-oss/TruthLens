"""TF-IDF + LinearSVC classifier wrapper for TruthLens AI."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC

BASE_DIR = Path(__file__).resolve().parent.parent
VECTORIZER_PATH = BASE_DIR / "models" / "tfidf_vectorizer.joblib"
CLASSIFIER_PATH = BASE_DIR / "models" / "linear_svm_model.joblib"
MODEL_METADATA_PATH = BASE_DIR / "models" / "model_metadata.json"

DEFAULT_MODEL_VERSION = "1.0.0"


class NewsClassifier:
    """Load saved TF-IDF/LinearSVC artifacts once and classify news text."""

    def __init__(
        self,
        vectorizer_path: Path = VECTORIZER_PATH,
        classifier_path: Path = CLASSIFIER_PATH,
        metadata_path: Path = MODEL_METADATA_PATH,
    ) -> None:
        if not vectorizer_path.is_file():
            raise FileNotFoundError(f"TF-IDF vectorizer not found: {vectorizer_path}")
        if not classifier_path.is_file():
            raise FileNotFoundError(f"LinearSVC classifier not found: {classifier_path}")

        self.vectorizer: TfidfVectorizer = joblib.load(vectorizer_path)
        self.classifier: LinearSVC = joblib.load(classifier_path)
        self._model_version = self._load_model_version(metadata_path)

    def _load_model_version(self, metadata_path: Path) -> str:
        """Load model version from metadata file."""
        if metadata_path.is_file():
            try:
                import json

                with open(metadata_path) as f:
                    metadata = json.load(f)
                return metadata.get("version", DEFAULT_MODEL_VERSION)
            except Exception:
                pass
        return DEFAULT_MODEL_VERSION

    @property
    def model_version(self) -> str:
        """Return the model version."""
        return self._model_version

    @staticmethod
    def _validate_text(text: str) -> str:
        if not isinstance(text, str):
            raise TypeError("News text must be a string")
        normalized = text.strip()
        if not normalized:
            raise ValueError("News text must not be empty")
        return normalized

    def predict(self, text: str) -> dict[str, Any]:
        """Predict label with decision score (margin from decision boundary)."""
        normalized = self._validate_text(text)
        features = self.vectorizer.transform([normalized])
        label = int(self.classifier.predict(features)[0])
        decision_score = float(self.classifier.decision_function(features)[0])

        if label not in (0, 1):
            raise RuntimeError(f"Classifier returned unsupported label: {label}")

        return {
            "label": label,
            "prediction": "Real" if label == 1 else "Fake",
            "decision_score": decision_score,
            "model_version": self._model_version,
        }

    def predict_many(self, texts: Sequence[str]) -> list[dict[str, Any]]:
        if isinstance(texts, (str, bytes)):
            raise TypeError("texts must be a sequence of strings, not a single string")
        normalized_texts = [self._validate_text(text) for text in texts]
        if not normalized_texts:
            return []

        features = self.vectorizer.transform(normalized_texts)
        labels = self.classifier.predict(features)
        decision_scores = self.classifier.decision_function(features)

        results = []
        for label, score in zip(labels, decision_scores):
            normalized_label = int(label)
            if normalized_label not in (0, 1):
                raise RuntimeError(
                    f"Classifier returned unsupported label: {normalized_label}"
                )
            results.append(
                {
                    "label": normalized_label,
                    "prediction": "Real" if normalized_label == 1 else "Fake",
                    "decision_score": float(score),
                    "model_version": self._model_version,
                }
            )
        return results


@lru_cache(maxsize=1)
def get_classifier() -> NewsClassifier:
    """Return one loaded classifier instance for reuse by application requests."""
    return NewsClassifier()


def predict_news(text: str) -> dict[str, Any]:
    """Predict a dataset-style label; this does not verify claims or facts."""
    return get_classifier().predict(text)