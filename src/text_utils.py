"""Unicode-aware text helpers shared by claim and evidence processing."""

from __future__ import annotations

import unicodedata


def tokenize_words(text: str) -> list[str]:
    """Split text into words while keeping combining marks with their letters."""
    words: list[str] = []
    current: list[str] = []

    def finish_word() -> None:
        if current:
            words.append("".join(current))
            current.clear()

    for index, character in enumerate(text):
        category = unicodedata.category(character)
        if category[0] in {"L", "N"} or (category[0] == "M" and current):
            current.append(character)
        elif (
            character in {"'", "’", "\u200c", "\u200d"}
            and current
            and index + 1 < len(text)
            and unicodedata.category(text[index + 1])[0] in {"L", "N"}
        ):
            current.append(character)
        else:
            finish_word()
    finish_word()
    return words
