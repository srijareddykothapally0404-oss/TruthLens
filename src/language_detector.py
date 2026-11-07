"""Local language detection for English and supported Indian languages."""

from __future__ import annotations

import logging
import threading
from collections import Counter
from typing import Any, ClassVar

LOGGER = logging.getLogger(__name__)

SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "te": "Telugu",
    "hi": "Hindi",
    "ta": "Tamil",
    "kn": "Kannada",
    "ml": "Malayalam",
    "mr": "Marathi",
    "bn": "Bengali",
    "gu": "Gujarati",
    "pa": "Punjabi",
    "or": "Odia",
    "ur": "Urdu",
}

_SCRIPT_LANGUAGES = {
    "gurmukhi": "pa",
    "gujarati": "gu",
    "odia": "or",
    "tamil": "ta",
    "telugu": "te",
    "kannada": "kn",
    "malayalam": "ml",
}
_SCRIPTS = {
    "latin": ((0x0041, 0x005A), (0x0061, 0x007A), (0x00C0, 0x024F)),
    "arabic": ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF)),
    "devanagari": ((0x0900, 0x097F),),
    "bengali": ((0x0980, 0x09FF),),
    "gurmukhi": ((0x0A00, 0x0A7F),),
    "gujarati": ((0x0A80, 0x0AFF),),
    "odia": ((0x0B00, 0x0B7F),),
    "tamil": ((0x0B80, 0x0BFF),),
    "telugu": ((0x0C00, 0x0C7F),),
    "kannada": ((0x0C80, 0x0CFF),),
    "malayalam": ((0x0D00, 0x0D7F),),
}
_AMBIGUOUS_SCRIPTS = {
    "devanagari": {"hi", "mr"},
    "bengali": {"bn"},
    "arabic": {"ur"},
}
_MIN_SCRIPT_CHARACTERS = 4
_MIN_MODEL_CONFIDENCE = 0.65
_MIN_MODEL_MARGIN = 0.12


class LanguageDetector:
    """Detect supported languages with Unicode scripts and local langid."""

    _shared_identifier: ClassVar[Any | None] = None
    _identifier_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self) -> None:
        self._identifier: Any | None = None

    def detect(self, text: str) -> dict[str, Any]:
        if not isinstance(text, str):
            raise TypeError("Text must be a string.")
        normalized = text.strip()
        if not normalized:
            return self._result("unknown", None, "uncertain")

        script_counts = self._count_scripts(normalized)
        total_letters = sum(script_counts.values())
        if total_letters < _MIN_SCRIPT_CHARACTERS:
            return self._result(
                "unknown",
                None,
                "uncertain",
                warning="There is too little text for reliable language detection.",
            )

        ranked_scripts = script_counts.most_common()
        dominant_script, dominant_count = ranked_scripts[0]
        dominant_ratio = dominant_count / total_letters
        if len(ranked_scripts) > 1:
            _, second_count = ranked_scripts[1]
            if (
                second_count >= _MIN_SCRIPT_CHARACTERS
                and second_count / total_letters >= 0.2
            ):
                return self._result(
                    "mixed",
                    dominant_ratio,
                    "mixed",
                    warning="The text contains substantial content in multiple scripts.",
                )

        if dominant_script in _SCRIPT_LANGUAGES:
            code = _SCRIPT_LANGUAGES[dominant_script]
            return self._result(code, dominant_ratio, "detected")

        if dominant_script in _AMBIGUOUS_SCRIPTS:
            allowed = _AMBIGUOUS_SCRIPTS[dominant_script]
            model_result = self._classify(normalized, allowed)
            if model_result is None:
                return self._result(
                    "unknown",
                    None,
                    "uncertain",
                    warning="The language model could not confidently distinguish this script.",
                )
            code, confidence, margin = model_result
            if (
                code not in allowed
                or confidence < _MIN_MODEL_CONFIDENCE
                or margin < _MIN_MODEL_MARGIN
            ):
                return self._result(
                    "unknown",
                    confidence,
                    "uncertain",
                    warning="The language model could not confidently distinguish this script.",
                )
            return self._result(code, confidence, "detected")

        if dominant_script == "latin":
            model_result = self._classify(normalized, {"en"})
            if model_result is None:
                return self._result(
                    "unknown",
                    None,
                    "uncertain",
                    warning="The language model could not identify this text confidently.",
                )
            code, confidence, margin = model_result
            if code != "en" or confidence < _MIN_MODEL_CONFIDENCE or margin < 0.2:
                return self._result(
                    "unknown",
                    confidence,
                    "uncertain",
                    warning="The text is not confidently identifiable as English or a supported language.",
                )
            return self._result(code, confidence, "detected")

        if dominant_script == "arabic":
            model_result = self._classify(normalized, {"ur"})
            if model_result is not None:
                code, confidence, margin = model_result
                if (
                    code == "ur"
                    and confidence >= _MIN_MODEL_CONFIDENCE
                    and margin >= _MIN_MODEL_MARGIN
                ):
                    return self._result(code, confidence, "detected")
            return self._result(
                "unknown",
                model_result[1] if model_result else None,
                "uncertain",
                warning="Arabic-script text could not be confidently identified as Urdu.",
            )

        return self._result(
            "unknown",
            None,
            "uncertain",
            warning="The detected script is not supported.",
        )

    def _classify(
        self,
        text: str,
        expected_codes: set[str],
    ) -> tuple[str, float, float] | None:
        try:
            identifier = self._get_identifier()
            ranked = identifier.rank(text)
        except Exception:
            LOGGER.exception("Local language identification failed")
            return None

        candidate_scores = [
            (code, float(score))
            for code, score in ranked
            if code in expected_codes
        ]
        if not candidate_scores:
            return None
        candidate_scores.sort(key=lambda result: result[1], reverse=True)
        code, confidence = candidate_scores[0]
        other_scores = [float(score) for other, score in ranked if other != code]
        margin = confidence - max(other_scores, default=float("-inf"))
        return code, confidence, margin

    def _get_identifier(self) -> Any:
        if LanguageDetector._shared_identifier is None:
            with LanguageDetector._identifier_lock:
                if LanguageDetector._shared_identifier is None:
                    from langid.langid import LanguageIdentifier, model

                    LanguageDetector._shared_identifier = (
                        LanguageIdentifier.from_modelstring(
                            model,
                            norm_probs=True,
                        )
                    )
        return LanguageDetector._shared_identifier

    @staticmethod
    def _count_scripts(text: str) -> Counter[str]:
        counts: Counter[str] = Counter()
        for character in text:
            if not character.isalpha():
                continue
            codepoint = ord(character)
            for script, ranges in _SCRIPTS.items():
                if any(start <= codepoint <= end for start, end in ranges):
                    counts[script] += 1
                    break
        return counts

    @staticmethod
    def _result(
        language_code: str,
        confidence: float | None,
        status: str,
        *,
        warning: str | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "language_code": language_code,
            "language_name": SUPPORTED_LANGUAGES.get(
                language_code,
                "Mixed language" if language_code == "mixed" else "Unknown",
            ),
            "detection_confidence": (
                round(max(0.0, min(1.0, confidence)), 4)
                if confidence is not None
                else None
            ),
            "detection_status": status,
        }
        if warning:
            result["warning"] = warning
        return result
