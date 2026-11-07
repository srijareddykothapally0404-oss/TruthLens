import tempfile
import unittest
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC

from src.predictor import NewsClassifier
from src.train_tfidf import prepare_dataset, split_dataset


class DatasetPreparationTests(unittest.TestCase):
    def test_maps_labels_removes_empty_and_duplicate_text(self) -> None:
        dataframe = pd.DataFrame(
            {
                "content": [
                    "Fake article text",
                    "Fake article text",
                    "Real article text",
                    "   ",
                    None,
                ],
                "label": ["Fake", "Fake", "Real", "Fake", "Real"],
            }
        )

        prepared = prepare_dataset(dataframe)

        self.assertEqual(prepared["content"].tolist(), [
            "Fake article text",
            "Real article text",
        ])
        self.assertEqual(prepared["label"].tolist(), [0, 1])

    def test_rejects_conflicting_labels_for_duplicate_text(self) -> None:
        dataframe = pd.DataFrame(
            {"content": ["same text", "same text"], "label": [0, 1]}
        )

        with self.assertRaisesRegex(ValueError, "conflicting labels"):
            prepare_dataset(dataframe)

    def test_splits_are_stratified_and_have_no_text_overlap(self) -> None:
        dataframe = pd.DataFrame(
            {
                "content": [
                    f"unique article {label} {index}"
                    for label in (0, 1)
                    for index in range(50)
                ],
                "label": [label for label in (0, 1) for _ in range(50)],
            }
        )

        train_df, validation_df, test_df = split_dataset(dataframe)

        self.assertEqual(
            (len(train_df), len(validation_df), len(test_df)),
            (70, 15, 15),
        )
        self.assertEqual(set(train_df["label"]), {0, 1})
        self.assertEqual(set(validation_df["label"]), {0, 1})
        self.assertEqual(set(test_df["label"]), {0, 1})
        self.assertFalse(
            set(train_df["content"]) & set(validation_df["content"])
        )
        self.assertFalse(set(train_df["content"]) & set(test_df["content"]))
        self.assertFalse(set(validation_df["content"]) & set(test_df["content"]))


class NewsClassifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        model_dir = Path(self.temporary_directory.name)
        vectorizer_path = model_dir / "vectorizer.joblib"
        classifier_path = model_dir / "classifier.joblib"

        texts = [
            "government fake rumor fabricated claim",
            "false invented rumor about government",
            "official report confirmed verified statement",
            "reliable report confirmed facts from officials",
        ]
        labels = [0, 0, 1, 1]
        vectorizer = TfidfVectorizer()
        classifier = LinearSVC(random_state=42).fit(
            vectorizer.fit_transform(texts),
            labels,
        )
        joblib.dump(vectorizer, vectorizer_path)
        joblib.dump(classifier, classifier_path)
        self.predictor = NewsClassifier(vectorizer_path, classifier_path)

    def test_predicts_both_classes(self) -> None:
        fake_result = self.predictor.predict("fabricated fake rumor")
        real_result = self.predictor.predict("confirmed official report")

        self.assertEqual(fake_result["label"], 0)
        self.assertEqual(fake_result["prediction"], "Fake")
        self.assertIn("decision_score", fake_result)
        self.assertIn("model_version", fake_result)
        self.assertEqual(real_result["label"], 1)
        self.assertEqual(real_result["prediction"], "Real")
        self.assertIn("decision_score", real_result)
        self.assertIn("model_version", real_result)

    def test_rejects_empty_and_invalid_text(self) -> None:
        for text in ("", "   "):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    self.predictor.predict(text)

        with self.assertRaises(TypeError):
            self.predictor.predict(None)

    def test_predict_many_validates_all_inputs(self) -> None:
        results = self.predictor.predict_many(
            ["fabricated fake rumor", "confirmed official report"]
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["label"], 0)
        self.assertEqual(results[0]["prediction"], "Fake")
        self.assertIn("decision_score", results[0])
        self.assertIn("model_version", results[0])
        self.assertEqual(results[1]["label"], 1)
        self.assertEqual(results[1]["prediction"], "Real")
        self.assertIn("decision_score", results[1])
        self.assertIn("model_version", results[1])
        self.assertEqual(self.predictor.predict_many([]), [])
        with self.assertRaises(ValueError):
            self.predictor.predict_many(["valid text", ""])
        with self.assertRaises(TypeError):
            self.predictor.predict_many("not a sequence of news items")


if __name__ == "__main__":
    unittest.main()
