"""Lightweight sentence-level extraction of candidate factual claims with compound splitting and offsets."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from src.text_utils import tokenize_words

DEFAULT_MAX_INPUT_LENGTH = 100_000

_ABBREVIATIONS = (
    "Mr", "Mrs", "Ms", "Dr", "Prof", "Sr", "Jr", "St",
    "vs", "etc", "e.g", "i.e", "U.S", "U.K",
)
_ABBREVIATION_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(item) for item in _ABBREVIATIONS) + r")\.",
    re.IGNORECASE,
)
_SENTENCE_BOUNDARY = re.compile(
    r"""[.!?।॥]+(?:["'”’)\]]*)(?=\s+|$)|[\r\n]+"""
)
_PREDICATE_WORDS = {
    "am", "are", "became", "become", "began", "begin", "believe",
    "built", "can", "caused", "confirmed", "could", "did", "do",
    "does", "found", "had", "has", "have", "is", "launched", "led",
    "made", "may", "might", "must", "occurred", "passed", "published",
    "said", "was", "were", "will", "would",
}
_PREDICATE_SUFFIX_S = {
    "adds", "announces", "causes", "claims", "confirms", "continues",
    "decreases", "describes", "finds", "gives", "grows", "increases",
    "indicates", "kills", "leads", "plans", "reports", "reveals",
    "says", "shows", "states", "suggests", "supports", "warns",
}
_IMPERATIVE_STARTS = {
    "check", "click", "discover", "follow", "find", "learn",
    "listen", "read", "see", "share", "subscribe", "watch",
}

# Compound claim splitting patterns
_COMPOUND_SPLIT_PATTERN = re.compile(
    r"\s+(?:and|but|or|while|whereas|however|although|though|because|since|as|when|after|before)\s+",
    re.IGNORECASE
)


class ArticleTooLongError(ValueError):
    """Raised when an article exceeds the configured character limit."""


@dataclass
class Claim:
    """Represents an extracted claim with position metadata."""
    claim_id: int
    claim_text: str
    claim_type: str = "factual"
    verification_status: str = "pending"
    start_offset: int = 0
    end_offset: int = 0
    parent_claim_id: int | None = None
    is_compound: bool = False
    compound_parts: list["Claim"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "claim_type": self.claim_type,
            "verification_status": self.verification_status,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "parent_claim_id": self.parent_claim_id,
            "is_compound": self.is_compound,
            "compound_parts": [part.to_dict() for part in self.compound_parts],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Claim":
        """Create Claim from dictionary (for manual editing)."""
        compound_parts = [
            cls.from_dict(part) for part in data.get("compound_parts", [])
        ]
        return cls(
            claim_id=data.get("claim_id", 0),
            claim_text=data.get("claim_text", ""),
            claim_type=data.get("claim_type", "factual"),
            verification_status=data.get("verification_status", "pending"),
            start_offset=data.get("start_offset", 0),
            end_offset=data.get("end_offset", 0),
            parent_claim_id=data.get("parent_claim_id"),
            is_compound=data.get("is_compound", False),
            compound_parts=compound_parts,
        )


def _sentences_with_offsets(text: str) -> list[tuple[str, int, int]]:
    """Extract sentences with their start/end character offsets in the original text."""
    protected_text = _ABBREVIATION_PATTERN.sub(
        lambda match: match.group(0).replace(".", ""),
        text,
    )
    sentences: list[tuple[str, int, int]] = []
    start = 0
    for boundary in _SENTENCE_BOUNDARY.finditer(protected_text):
        boundary_text = boundary.group(0)
        sentence_end = (
            boundary.start()
            if "\n" in boundary_text or "\r" in boundary_text
            else boundary.end()
        )
        candidate = protected_text[start:sentence_end].strip()
        if candidate:
            original_candidate = candidate.replace("", ".")
            # Find the actual start/end in original text
            actual_start = text.find(original_candidate, start)
            if actual_start >= 0:
                actual_end = actual_start + len(original_candidate)
                sentences.append((original_candidate, actual_start, actual_end))
        start = boundary.end()

    remainder = protected_text[start:].strip()
    if remainder:
        original_remainder = remainder.replace("", ".")
        actual_start = text.find(original_remainder, start)
        if actual_start >= 0:
            actual_end = actual_start + len(original_remainder)
            sentences.append((original_remainder, actual_start, actual_end))
    return sentences


def _has_predicate(sentence: str) -> bool:
    if re.search(r"\?[\s\"'”’)\]]*$", sentence):
        return False

    words = [word.casefold() for word in tokenize_words(sentence)]
    if len(words) < 3 or words[0] in _IMPERATIVE_STARTS:
        return False

    if any(
        character.isalpha()
        and not unicodedata.name(character, "").startswith("LATIN ")
        for character in sentence
    ):
        return True

    for word in words[1:]:
        if word in _PREDICATE_WORDS or word in _PREDICATE_SUFFIX_S:
            return True
        if len(word) > 4 and word.endswith("ed") and word != "united":
            return True
    return False


def _split_compound_claim(
    sentence: str,
    start_offset: int,
    claim_id: int,
) -> list[Claim]:
    """Split a compound claim into individual claims with offsets."""
    parts = _COMPOUND_SPLIT_PATTERN.split(sentence)
    if len(parts) <= 1:
        return [Claim(
            claim_id=claim_id,
            claim_text=sentence,
            start_offset=start_offset,
            end_offset=start_offset + len(sentence),
        )]

    claims = []
    current_offset = start_offset
    for idx, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        # Find the part in the original sentence to get accurate offsets
        part_start = sentence.find(part, current_offset - start_offset)
        if part_start >= 0:
            absolute_start = start_offset + part_start
            absolute_end = absolute_start + len(part)
        else:
            absolute_start = current_offset
            absolute_end = current_offset + len(part)

        sub_claim = Claim(
            claim_id=claim_id * 10 + idx + 1,  # Sub-claim IDs
            claim_text=part,
            start_offset=absolute_start,
            end_offset=absolute_end,
            parent_claim_id=claim_id,
        )
        claims.append(sub_claim)
        current_offset = absolute_end

    return claims


def extract_claims(
    text: str,
    max_length: int = DEFAULT_MAX_INPUT_LENGTH,
    split_compound: bool = True,
) -> dict[str, Any]:
    """Return unique, sentence-level candidate factual claims from article text.

    Args:
        text: Article text to extract claims from
        max_length: Maximum allowed text length
        split_compound: Whether to split compound claims on conjunctions

    Returns:
        Dictionary with success status, total claims, and list of claims
        Each claim includes claim_id, claim_text, claim_type, verification_status,
        start_offset, end_offset, parent_claim_id, is_compound, compound_parts
    """
    if not isinstance(text, str):
        raise TypeError("Article text must be a string.")
    if isinstance(max_length, bool) or not isinstance(max_length, int):
        raise TypeError("max_length must be a positive integer.")
    if max_length <= 0:
        raise ValueError("max_length must be a positive integer.")
    if not text.strip():
        raise ValueError("Article text must not be empty or whitespace.")
    if len(text) > max_length:
        raise ArticleTooLongError(
            f"Article exceeds the maximum length of {max_length} characters."
        )

    claims: list[Claim] = []
    seen: set[str] = set()
    claim_counter = 0

    for sentence, start_offset, end_offset in _sentences_with_offsets(text):
        normalized = " ".join(sentence.split()).casefold()
        if normalized in seen or not _has_predicate(sentence):
            continue

        claim_counter += 1

        if split_compound:
            sub_claims = _split_compound_claim(sentence, start_offset, claim_counter)
            if len(sub_claims) > 1:
                # This is a compound claim
                parent_claim = Claim(
                    claim_id=claim_counter,
                    claim_text=sentence,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    is_compound=True,
                    compound_parts=sub_claims,
                )
                claims.append(parent_claim)
                # Also add sub-claims individually for verification
                for sub in sub_claims:
                    claims.append(sub)
            else:
                claims.append(sub_claims[0])
        else:
            claims.append(Claim(
                claim_id=claim_counter,
                claim_text=sentence,
                start_offset=start_offset,
                end_offset=end_offset,
            ))

        seen.add(normalized)

    return {
        "success": True,
        "total_claims": len(claims),
        "claims": [claim.to_dict() for claim in claims],
    }


def update_claim(
    claims: list[dict[str, Any]],
    claim_id: int,
    new_text: str,
    new_type: str | None = None,
) -> list[dict[str, Any]]:
    """Update a claim's text and/or type (for manual editing).

    Args:
        claims: List of claim dictionaries
        claim_id: ID of claim to update
        new_text: New claim text
        new_type: Optional new claim type

    Returns:
        Updated list of claim dictionaries
    """
    if not isinstance(new_text, str) or not new_text.strip():
        raise ValueError("New claim text must not be empty.")

    updated = []
    for claim_data in claims:
        claim = Claim.from_dict(claim_data)
        if claim.claim_id == claim_id:
            claim.claim_text = new_text.strip()
            if new_type:
                claim.claim_type = new_type
            claim.verification_status = "pending"  # Reset verification status
        updated.append(claim.to_dict())
    return updated


def add_claim(
    claims: list[dict[str, Any]],
    claim_text: str,
    claim_type: str = "factual",
    start_offset: int = -1,
    end_offset: int = -1,
) -> list[dict[str, Any]]:
    """Add a new claim manually.

    Args:
        claims: Existing list of claims
        claim_text: Text of the new claim
        claim_type: Type of claim
        start_offset: Character offset in source text (-1 if unknown)
        end_offset: End character offset (-1 if unknown)

    Returns:
        Updated list of claim dictionaries
    """
    if not isinstance(claim_text, str) or not claim_text.strip():
        raise ValueError("Claim text must not be empty.")

    # Find max claim_id
    max_id = max((c.get("claim_id", 0) for c in claims), default=0)
    new_id = max_id + 1

    new_claim = Claim(
        claim_id=new_id,
        claim_text=claim_text.strip(),
        claim_type=claim_type,
        start_offset=start_offset if start_offset >= 0 else 0,
        end_offset=end_offset if end_offset >= 0 else len(claim_text),
    )

    return claims + [new_claim.to_dict()]


def delete_claim(
    claims: list[dict[str, Any]],
    claim_id: int,
) -> list[dict[str, Any]]:
    """Delete a claim by ID.

    Args:
        claims: List of claims
        claim_id: ID of claim to delete

    Returns:
        Updated list without the deleted claim
    """
    return [c for c in claims if c.get("claim_id") != claim_id]


__all__ = [
    "extract_claims",
    "update_claim",
    "add_claim",
    "delete_claim",
    "Claim",
    "ArticleTooLongError",
]