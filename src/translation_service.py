
"""Optional offline translation using locally installed Argos language models."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from src.language_detector import SUPPORTED_LANGUAGES

LOGGER = logging.getLogger(__name__)

DEFAULT_MAX_TEXT_LENGTH = 100_000

Translator = Callable[[str, str, str], str]


class TranslationService:
    """Translate supported text to English using local translation models."""

    def __init__(
        self,
        translator: Translator | None = None,
        *,
        max_text_length: int = DEFAULT_MAX_TEXT_LENGTH,
    ) -> None:
        if isinstance(max_text_length, bool) or not isinstance(
            max_text_length, int
        ):
            raise TypeError("max_text_length must be a positive integer.")

        if max_text_length <= 0:
            raise ValueError("max_text_length must be a positive integer.")

        if translator is not None and not callable(translator):
            raise TypeError("translator must be callable or None.")

        self.translator = translator
        self.max_text_length = max_text_length

    @staticmethod
    def _normalize_language_code(language_code: str) -> str:
        return language_code.strip().casefold()

    @staticmethod
    def _get_supported_codes() -> set[str]:
        if isinstance(SUPPORTED_LANGUAGES, Mapping):
            languages = SUPPORTED_LANGUAGES.keys()
        elif isinstance(SUPPORTED_LANGUAGES, (set, list, tuple)):
            languages = SUPPORTED_LANGUAGES
        else:
            languages = []

        return {
            language.strip().casefold()
            for language in languages
            if isinstance(language, str)
        }

    def translate(
        self,
        text: str,
        source_language: str,
        target_language: str = "en",
    ) -> dict[str, Any]:
        if not isinstance(text, str):
            raise TypeError("Text to translate must be a string.")

        if not isinstance(source_language, str) or not isinstance(
            target_language, str
        ):
            raise TypeError("Language codes must be strings.")

        original = text

        source_code = self._normalize_language_code(source_language)
        target_code = self._normalize_language_code(target_language)

        normalized = text.strip()

        if not normalized:
            return self._result(
                original,
                source_code,
                target_code,
                status="rejected",
                error="Text to translate must not be empty or whitespace.",
            )

        if len(normalized) > self.max_text_length:
            return self._result(
                original,
                source_code,
                target_code,
                status="rejected",
                error=(
                    f"Text exceeds the maximum length of "
                    f"{self.max_text_length} characters."
                ),
            )

        supported_codes = self._get_supported_codes()

        if (
            source_code not in supported_codes
            or target_code not in supported_codes
        ):
            return self._result(
                original,
                source_code,
                target_code,
                status="unsupported",
                error="The requested language is not supported.",
            )

        if source_code == target_code:
            return self._result(
                original,
                source_code,
                target_code,
                translated_text=normalized,
                status="not_required",
                warnings=[
                    "Source and target languages are the same."
                ],
            )

        if target_code != "en":
            return self._result(
                original,
                source_code,
                target_code,
                status="unsupported",
                error=(
                    "Translation targets other than English "
                    "are not enabled."
                ),
            )

        if self.translator is None:
            return self._translate_with_argos(
                original,
                normalized,
                source_code,
                target_code,
            )

        try:
            translated = self.translator(
                normalized,
                source_code,
                target_code,
            )

        except (ImportError, ModuleNotFoundError):
            return self._unavailable(
                original,
                source_code,
                target_code,
                "The local translation package or language model "
                "is not installed.",
            )

        except LookupError:
            return self._unavailable(
                original,
                source_code,
                target_code,
                "No local translation model is installed "
                "for this language pair.",
            )

        except Exception:
            LOGGER.exception("Local translation failed")

            return self._result(
                original,
                source_code,
                target_code,
                status="failed",
                warnings=[
                    "Translation is performed locally "
                    "and may be imperfect."
                ],
                error=(
                    "Translation failed; the original text "
                    "was not sent to the English pipeline."
                ),
            )

        return self._validate_translation(
            original,
            normalized,
            source_code,
            target_code,
            translated,
        )

    def _translate_with_argos(
        self,
        original: str,
        normalized: str,
        source_code: str,
        target_code: str,
    ) -> dict[str, Any]:
        try:
            import argostranslate.translate as argos_translate

        except ImportError:
            return self._unavailable(
                original,
                source_code,
                target_code,
                "Argos Translate is not installed. "
                "Install it and a local language model.",
            )

        try:
            installed_languages = (
                argos_translate.get_installed_languages()
            )

            source = next(
                (
                    language
                    for language in installed_languages
                    if language.code.casefold() == source_code
                ),
                None,
            )

            target = next(
                (
                    language
                    for language in installed_languages
                    if language.code.casefold() == target_code
                ),
                None,
            )

            if source is None or target is None:
                return self._unavailable(
                    original,
                    source_code,
                    target_code,
                    "No local translation model is installed "
                    "for this language pair.",
                )

            translation = source.get_translation(target)

        except (StopIteration, LookupError):
            return self._unavailable(
                original,
                source_code,
                target_code,
                "No local translation model is installed "
                "for this language pair.",
            )

        except Exception:
            LOGGER.exception("Argos Translate model lookup failed")

            return self._unavailable(
                original,
                source_code,
                target_code,
                "The local translation model is unavailable.",
            )

        if translation is None:
            return self._unavailable(
                original,
                source_code,
                target_code,
                "No local translation model is installed "
                "for this language pair.",
            )

        try:
            translated = translation.translate(normalized)

        except Exception:
            LOGGER.exception("Argos Translate execution failed")

            return self._result(
                original,
                source_code,
                target_code,
                status="failed",
                warnings=[
                    "Translation is performed locally "
                    "and may be imperfect."
                ],
                error=(
                    "Translation failed; the original text "
                    "was not sent to the English pipeline."
                ),
            )

        return self._validate_translation(
            original,
            normalized,
            source_code,
            target_code,
            translated,
        )

    def _validate_translation(
        self,
        original: str,
        normalized: str,
        source_code: str,
        target_code: str,
        translated: Any,
    ) -> dict[str, Any]:
        if not isinstance(translated, str) or not translated.strip():
            return self._result(
                original,
                source_code,
                target_code,
                status="failed",
                warnings=[
                    "Translation is performed locally "
                    "and may be imperfect."
                ],
                error="The translation model returned no usable text.",
            )

        output = translated.strip()

        if (
            output.casefold() == normalized.casefold()
            and source_code != "en"
        ):
            return self._result(
                original,
                source_code,
                target_code,
                status="failed",
                warnings=[
                    "Translation is performed locally "
                    "and may be imperfect."
                ],
                error=(
                    "The translation model returned "
                    "the unchanged source text."
                ),
            )

        return self._result(
            original,
            source_code,
            target_code,
            translated_text=output,
            status="translated",
            warnings=[
                "Translation may alter names, dates, nuance, "
                "or claim meaning. Review it before verification."
            ],
        )

    @staticmethod
    def _unavailable(
        original: str,
        source_code: str,
        target_code: str,
        message: str,
    ) -> dict[str, Any]:
        return TranslationService._result(
            original,
            source_code,
            target_code,
            status="unavailable",
            warnings=[
                "No original-language text is substituted "
                "for a failed translation."
            ],
            error=message,
        )

    @staticmethod
    def _result(
        original_text: str,
        source_language: str,
        target_language: str,
        *,
        status: str,
        translated_text: str | None = None,
        warnings: list[str] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        return {
            "original_text": original_text,
            "translated_text": translated_text,
            "source_language": source_language,
            "target_language": target_language,
            "translation_status": status,
            "warnings": warnings or [],
            "error": error,
        }
