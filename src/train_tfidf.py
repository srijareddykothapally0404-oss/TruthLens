from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.svm import LinearSVC

if __package__:
    from .predictor import NewsClassifier
else:
    from predictor import NewsClassifier

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "cleaned_data.csv"
MODEL_DIR = BASE_DIR / "models"
VECTORIZER_PATH = MODEL_DIR / "tfidf_vectorizer.joblib"
CLASSIFIER_PATH = MODEL_DIR / "linear_svm_model.joblib"
RANDOM_STATE = 42


def _normalize_label(value: Any, row_number: int) -> int:
    if pd.isna(value) or isinstance(value, bool):
        raise ValueError(f"Invalid label at row {row_number}: {value!r}")

    if isinstance(value, str):
        normalized = value.strip().casefold()
        named_labels = {"fake": 0, "real": 1}
        if normalized in named_labels:
            return named_labels[normalized]
        if normalized in {"0", "0.0"}:
            return 0
        if normalized in {"1", "1.0"}:
            return 1
        raise ValueError(f"Invalid label at row {row_number}: {value!r}")

    if value == 0 or value == 1:
        return int(value)
    raise ValueError(f"Invalid label at row {row_number}: {value!r}")


def prepare_dataset(dataframe: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"content", "label"}
    missing_columns = required_columns.difference(dataframe.columns)
    if missing_columns:
        raise ValueError(
            "Dataset must contain 'content' and 'label' columns; "
            f"missing: {', '.join(sorted(missing_columns))}"
        )

    prepared = dataframe.loc[:, ["content", "label"]].copy()
    prepared["content"] = prepared["content"].fillna("").astype(str).str.strip()
    prepared = prepared.loc[prepared["content"].ne("")].copy()
    prepared["label"] = [
        _normalize_label(label, row_number)
        for row_number, label in enumerate(prepared["label"], start=1)
    ]

    conflicting_labels = (
        prepared.groupby("content", sort=False)["label"].nunique().gt(1)
    )
    if conflicting_labels.any():
        raise ValueError(
            f"Found {int(conflicting_labels.sum())} duplicate text(s) "
            "with conflicting labels"
        )

    prepared = prepared.drop_duplicates(subset="content", keep="first")
    if set(prepared["label"].unique()) != {0, 1}:
        raise ValueError("Dataset must contain both Fake (0) and Real (1) labels")
    return prepared.reset_index(drop=True)


def split_dataset(
    dataframe: pd.DataFrame,
    random_state: int = RANDOM_STATE,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    try:
        train_df, temporary_df = train_test_split(
            dataframe,
            test_size=0.30,
            random_state=random_state,
            stratify=dataframe["label"],
        )
        validation_df, test_df = train_test_split(
            temporary_df,
            test_size=0.50,
            random_state=random_state,
            stratify=temporary_df["label"],
        )
    except ValueError as exc:
        raise ValueError(
            "Unable to make stratified train/validation/test splits; "
            "ensure each class has enough examples"
        ) from exc

    return (
        train_df.reset_index(drop=True),
        validation_df.reset_index(drop=True),
        test_df.reset_index(drop=True),
    )


def evaluate_classifier(
    classifier: LinearSVC,
    vectorizer: TfidfVectorizer,
    dataframe: pd.DataFrame,
) -> dict[str, Any]:
    features = vectorizer.transform(dataframe["content"])
    predictions = classifier.predict(features)
    labels = dataframe["label"].to_numpy()
    return {
        "accuracy": float(accuracy_score(labels, predictions)),
        "precision": float(
            precision_score(labels, predictions, pos_label=1, zero_division=0)
        ),
        "recall": float(
            recall_score(labels, predictions, pos_label=1, zero_division=0)
        ),
        "f1_score": float(f1_score(labels, predictions, pos_label=1, zero_division=0)),
        "confusion_matrix": confusion_matrix(
            labels, predictions, labels=[0, 1]
        ).tolist(),
    }


def train_and_evaluate(
    dataset_path: Path = DATA_PATH,
    model_dir: Path = MODEL_DIR,
) -> dict[str, Any]:
    raw_dataframe = pd.read_csv(dataset_path)
    normalized_text = raw_dataframe["content"].fillna("").astype(str).str.strip()
    duplicates_removed = int(
        normalized_text.loc[normalized_text.ne("")].duplicated().sum()
    )
    dataframe = prepare_dataset(raw_dataframe)
    train_df, validation_df, test_df = split_dataset(dataframe)

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=2,
        max_features=100_000,
        sublinear_tf=True,
    )
    train_features = vectorizer.fit_transform(train_df["content"])
    classifier = LinearSVC(random_state=RANDOM_STATE)
    classifier.fit(train_features, train_df["label"])

    model_dir.mkdir(parents=True, exist_ok=True)
    vectorizer_path = model_dir / VECTORIZER_PATH.name
    classifier_path = model_dir / CLASSIFIER_PATH.name
    joblib.dump(vectorizer, vectorizer_path)
    joblib.dump(classifier, classifier_path)

    return {
        "rows": len(dataframe),
        "duplicates_removed": duplicates_removed,
        "split_sizes": {
            "train": len(train_df),
            "validation": len(validation_df),
            "test": len(test_df),
        },
        "label_counts": dataframe["label"].value_counts().sort_index().to_dict(),
        "validation": evaluate_classifier(classifier, vectorizer, validation_df),
        "test": evaluate_classifier(classifier, vectorizer, test_df),
        "test_samples": {
            "Fake": test_df.loc[test_df["label"].eq(0), "content"].iloc[0],
            "Real": test_df.loc[test_df["label"].eq(1), "content"].iloc[0],
        },
        "vectorizer_path": vectorizer_path,
        "classifier_path": classifier_path,
    }


def _print_metrics(name: str, metrics: dict[str, Any]) -> None:
    print(f"\n{name} metrics (Real is the positive class):")
    print(f"  Accuracy:          {metrics['accuracy']:.4f}")
    print(f"  Precision:         {metrics['precision']:.4f}")
    print(f"  Recall:            {metrics['recall']:.4f}")
    print(f"  F1-score:          {metrics['f1_score']:.4f}")
    print("  Confusion matrix [Fake, Real]:")
    for row in metrics["confusion_matrix"]:
        print(f"    {row}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train and evaluate the TruthLens TF-IDF/LinearSVC classifier."
    )
    parser.add_argument("--dataset", type=Path, default=DATA_PATH)
    parser.add_argument("--models-dir", type=Path, default=MODEL_DIR)
    args = parser.parse_args()

    result = train_and_evaluate(args.dataset, args.models_dir)
    print(f"Prepared rows: {result['rows']}")
    print(f"Duplicates removed: {result['duplicates_removed']}")
    print(f"Split sizes: {result['split_sizes']}")
    print(f"Label counts (Fake=0, Real=1): {result['label_counts']}")
    _print_metrics("Validation", result["validation"])
    _print_metrics("Test", result["test"])

    predictor = NewsClassifier(
        result["vectorizer_path"],
        result["classifier_path"],
    )
    for expected_label, text in result["test_samples"].items():
        prediction = predictor.predict(text)
        print(
            f"Sample from {expected_label} test class -> "
            f"classifier prediction: {prediction['prediction']} "
            f"(label={prediction['label']})"
        )
    print(f"Saved vectorizer: {result['vectorizer_path']}")
    print(f"Saved classifier: {result['classifier_path']}")
    print("Classifier labels are not factual verification.")


if __name__ == "__main__":
    main()
