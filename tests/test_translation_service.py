from __future__ import annotations

from typing import Any

import pytest

from src.translation_service import TranslationService


TELUGU_TEXT = "ప్రభుత్వం కొత్త విధానాన్ని ప్రకటించింది."


def test_translation_success_preserves_original_and_translated_text() -> None:
    calls: list[tuple[str, str, str]] = []

    def translator(text: str, source: str, target: str) -> str:
        calls.append((text, source, target))
        return "The government announced a new policy."

    result = TranslationService(translator).translate(TELUGU_TEXT, "te")

    assert result["original_text"] == TELUGU_TEXT
    assert result["translated_text"] == "The government announced a new policy."
    assert result["source_language"] == "te"
    assert result["target_language"] == "en"
    assert result["translation_status"] == "translated"
    assert result["warnings"]
    assert calls == [(TELUGU_TEXT, "te", "en")]


def test_english_text_is_returned_as_not_required() -> None:
    text = "The government announced a new policy."

    result = TranslationService().translate(text, "en")

    assert result["original_text"] == text
    assert result["translated_text"] == text
    assert result["translation_status"] == "not_required"


def test_missing_local_translation_package_is_unavailable_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import builtins

    real_import = builtins.__import__

    def missing_argos(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "argostranslate.translate":
            raise ModuleNotFoundError("optional package is not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_argos)
    result = TranslationService().translate(TELUGU_TEXT, "te")

    assert result["translation_status"] == "unavailable"
    assert result["translated_text"] is None
    assert result["original_text"] == TELUGU_TEXT
    assert result["error"]
    assert result["warnings"]


def test_missing_translation_pair_is_explicitly_unavailable() -> None:
    def missing_pair(_: str, __: str, ___: str) -> str:
        raise LookupError("translation model not installed")

    result = TranslationService(missing_pair).translate(TELUGU_TEXT, "te")

    assert result["translation_status"] == "unavailable"
    assert result["translated_text"] is None


def test_translation_failure_does_not_substitute_original_text() -> None:
    def fail(_: str, __: str, ___: str) -> str:
        raise RuntimeError("model error")

    result = TranslationService(fail).translate(TELUGU_TEXT, "te")

    assert result["translation_status"] == "failed"
    assert result["original_text"] == TELUGU_TEXT
    assert result["translated_text"] is None
    assert "not sent" in result["error"]


@pytest.mark.parametrize("output", ["", "  ", TELUGU_TEXT])
def test_empty_or_unchanged_translation_is_not_accepted(output: str) -> None:
    result = TranslationService(lambda *_: output).translate(TELUGU_TEXT, "te")

    assert result["translation_status"] == "failed"
    assert result["translated_text"] is None


def test_unknown_language_and_non_english_target_are_rejected() -> None:
    unknown = TranslationService(lambda *_: "ignored").translate(
        TELUGU_TEXT,
        "xx",
    )
    target = TranslationService(lambda *_: "ignored").translate(
        TELUGU_TEXT,
        "te",
        target_language="hi",
    )

    assert unknown["translation_status"] == "unsupported"
    assert target["translation_status"] == "unsupported"


@pytest.mark.parametrize("text", ["", "  \n"])
def test_empty_text_is_rejected(text: str) -> None:
    result = TranslationService().translate(text, "te")

    assert result["translation_status"] == "rejected"
    assert result["translated_text"] is None


def test_oversized_text_is_rejected() -> None:
    result = TranslationService(max_text_length=10).translate(
        "x" * 11,
        "te",
    )

    assert result["translation_status"] == "rejected"
    assert result["translated_text"] is None


def test_invalid_input_types_are_rejected() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        TranslationService().translate(None, "te")  # type: ignore[arg-type]
