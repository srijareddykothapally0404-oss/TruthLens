from __future__ import annotations

import pytest

from src.language_detector import LanguageDetector, SUPPORTED_LANGUAGES


LANGUAGE_SAMPLES = {
    "en": "The government announced a new public transport policy today.",
    "te": "ప్రభుత్వం ఈ రోజు నగరంలో ప్రజా రవాణా కోసం కొత్త విధానాన్ని ప్రకటించింది.",
    "hi": "सरकार ने आज शहर में सार्वजनिक परिवहन के लिए नई नीति की घोषणा की।",
    "ta": "அரசு இன்று நகரத்தில் பொது போக்குவரத்திற்கான புதிய கொள்கையை அறிவித்தது.",
    "kn": "ಸರ್ಕಾರವು ಇಂದು ನಗರದಲ್ಲಿ ಸಾರ್ವಜನಿಕ ಸಾರಿಗೆಗಾಗಿ ಹೊಸ ನೀತಿಯನ್ನು ಘೋಷಿಸಿತು.",
    "ml": "സർക്കാർ ഇന്ന് നഗരത്തിലെ പൊതുഗതാഗതത്തിനായി പുതിയ നയം പ്രഖ്യാപിച്ചു.",
    "mr": "सरकारने आज शहरातील सार्वजनिक वाहतुकीसाठी नवीन धोरण जाहीर केले.",
    "bn": "সরকার আজ শহরের গণপরিবহনের জন্য একটি নতুন নীতি ঘোষণা করেছে।",
    "gu": "સરકારે આજે શહેરમાં જાહેર પરિવહન માટે નવી નીતિ જાહેર કરી.",
    "pa": "ਸਰਕਾਰ ਨੇ ਅੱਜ ਸ਼ਹਿਰ ਵਿੱਚ ਜਨਤਕ ਆਵਾਜਾਈ ਲਈ ਨਵੀਂ ਨੀਤੀ ਦਾ ਐਲਾਨ ਕੀਤਾ।",
    "or": "ସରକାର ଆଜି ସହରରେ ସାର୍ବଜନୀନ ପରିବହନ ପାଇଁ ଏକ ନୂତନ ନୀତି ଘୋଷଣା କରିଛନ୍ତି।",
    "ur": "حکومت نے آج شہر میں عوامی نقل و حمل کے لیے نئی پالیسی کا اعلان کیا۔",
}


@pytest.mark.parametrize(
    ("expected_code", "text"),
    LANGUAGE_SAMPLES.items(),
)
def test_detects_each_supported_language(
    expected_code: str,
    text: str,
) -> None:
    result = LanguageDetector().detect(text)

    assert result["language_code"] == expected_code
    assert result["language_name"] == SUPPORTED_LANGUAGES[expected_code]
    assert result["detection_status"] == "detected"
    assert result["detection_confidence"] is not None
    assert 0.0 <= result["detection_confidence"] <= 1.0


@pytest.mark.parametrize("text", ["", "  \n"])
def test_empty_input_is_uncertain(text: str) -> None:
    result = LanguageDetector().detect(text)

    assert result["language_code"] == "unknown"
    assert result["language_name"] == "Unknown"
    assert result["detection_confidence"] is None
    assert result["detection_status"] == "uncertain"


@pytest.mark.parametrize("text", ["Hi", "OK", "आज", "అవును"])
def test_very_short_text_is_not_misclassified(text: str) -> None:
    result = LanguageDetector().detect(text)

    assert result["language_code"] == "unknown"
    assert result["detection_status"] == "uncertain"


def test_short_regional_headline_can_be_identified_by_distinct_script() -> None:
    result = LanguageDetector().detect("తెలంగాణలో భారీ వర్షాలు")

    assert result["language_code"] == "te"
    assert result["detection_status"] == "detected"


def test_short_english_headline_can_be_identified() -> None:
    result = LanguageDetector().detect("City council approves plan")

    assert result["language_code"] == "en"
    assert result["detection_status"] == "detected"


def test_mixed_script_content_is_reported_as_mixed() -> None:
    result = LanguageDetector().detect(
        "The council approved the bill. ప్రభుత్వం కొత్త విధానం ప్రకటించింది."
    )

    assert result["language_code"] == "mixed"
    assert result["language_name"] == "Mixed language"
    assert result["detection_status"] == "mixed"
    assert result["warning"]


def test_unsupported_cyrillic_text_is_not_reported_as_a_supported_language() -> None:
    result = LanguageDetector().detect(
        "Правительство объявило новую политику общественного транспорта."
    )

    assert result["language_code"] == "unknown"
    assert result["detection_status"] == "uncertain"


def test_non_string_input_is_rejected() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        LanguageDetector().detect(None)  # type: ignore[arg-type]
