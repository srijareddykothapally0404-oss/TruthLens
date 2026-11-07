"""Cautious rule-based assessment of retrieved evidence for a claim."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

from src.evidence_retrieval import classify_source
from src.text_utils import tokenize_words

MAX_CLAIM_LENGTH = 5_000
MAX_EVIDENCE_ITEMS = 100
MAX_EVIDENCE_TEXT_LENGTH = 20_000
MIN_RELEVANCE = 0.35
STRONG_RELEVANCE = 0.55
MIN_INDEPENDENT_CREDIBLE_SOURCES = 2

_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but",
    "by", "did", "do", "does", "for", "from", "had", "has", "have", "he",
    "her", "his", "in", "into", "is", "it", "its", "of", "on", "or",
    "our", "she", "that", "the", "their", "them", "they", "this", "to",
    "was", "we", "were", "will", "with", "would",
}
_NEGATIONS = {"no", "not", "never", "neither", "nor", "false", "denied"}
_OPPOSITES = {
    "approve": "reject",
    "approved": "rejected",
    "increase": "decrease",
    "increased": "decreased",
    "decrease": "increase",
    "decreased": "increased",
    "win": "lose",
    "won": "lost",
    "lose": "win",
    "lost": "won",
    "launch": "cancel",
    "launched": "cancelled",
    "pass": "fail",
    "passed": "failed",
    "rise": "fall",
    "rose": "fell",
    "fall": "rise",
    "fell": "rose",
    "safe": "unsafe",
    "unsafe": "safe",
    "true": "false",
    "false": "true",
}
_WORD_VARIANTS = {
    "approved": {"approved", "approve"},
    "approve": {"approve", "approved"},
    "rejected": {"rejected", "reject"},
    "reject": {"reject", "rejected"},
    "launched": {"launched", "launch"},
    "launch": {"launch", "launched"},
}
_MISLEADING_MARKERS = {
    "misleading",
    "out of context",
    "taken out of context",
    "old video",
    "old image",
    "recirculated",
    "from a different year",
    "incorrect context",
}

# New stance labels per design document
STANCE_SUPPORTS = "SUPPORTS"
STANCE_CONTRADICTS = "CONTRADICTS"
STANCE_MIXED = "MIXED"
STANCE_NEUTRAL = "NEUTRAL"
STANCE_INSUFFICIENT = "INSUFFICIENT"

_STANCE_LABELS = {
    STANCE_SUPPORTS,
    STANCE_CONTRADICTS,
    STANCE_MIXED,
    STANCE_NEUTRAL,
    STANCE_INSUFFICIENT,
}

# Verdict labels per design document
VERDICT_TRUE = "TRUE"
VERDICT_FALSE = "FALSE"
VERDICT_PARTIALLY_TRUE = "PARTIALLY TRUE"
VERDICT_MISLEADING = "MISLEADING"
VERDICT_INSUFFICIENT_EVIDENCE = "INSUFFICIENT EVIDENCE"
VERDICT_NEEDS_HUMAN_REVIEW = "NEEDS HUMAN REVIEW"

_VERDICTS = {
    VERDICT_TRUE,
    VERDICT_FALSE,
    VERDICT_PARTIALLY_TRUE,
    VERDICT_MISLEADING,
    VERDICT_INSUFFICIENT_EVIDENCE,
    VERDICT_NEEDS_HUMAN_REVIEW,
}


class EvidenceAnalysisInputError(ValueError):
    """Raised when a claim or supplied evidence record is invalid."""


def _tokens(text: str) -> set[str]:
    tokens = {token.casefold() for token in tokenize_words(text)}
    return {
        token
        for token in tokens
        if token not in _STOP_WORDS and len(token) > 1
    }


def _normalize_url(value: Any) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    if not isinstance(value, str):
        raise EvidenceAnalysisInputError("Evidence source_url must be a string or null.")
    if not value.strip():
        return None, None
    try:
        parsed = urlsplit(value.strip())
        host = (parsed.hostname or "").casefold().rstrip(".")
        if parsed.scheme.casefold() not in {"http", "https"} or not host:
            raise EvidenceAnalysisInputError(
                "Evidence source_url must be an absolute HTTP or HTTPS URL."
            )
        if parsed.username is not None or parsed.password is not None:
            raise EvidenceAnalysisInputError(
                "Evidence source_url must not contain credentials."
            )
        port = parsed.port
    except ValueError as exc:
        raise EvidenceAnalysisInputError("Evidence source_url is malformed.") from exc

    netloc = host
    if port is not None and not (
        (parsed.scheme.casefold() == "http" and port == 80)
        or (parsed.scheme.casefold() == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"
    normalized = parsed._replace(
        scheme=parsed.scheme.casefold(),
        netloc=netloc,
        fragment="",
    ).geturl()
    return normalized, host


def _validate_optional_text(
    item: Mapping[str, Any],
    field: str,
) -> str | None:
    value = item.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise EvidenceAnalysisInputError(f"Evidence {field} must be a string or null.")
    if len(value) > MAX_EVIDENCE_TEXT_LENGTH:
        raise EvidenceAnalysisInputError(
            f"Evidence {field} exceeds the maximum length."
        )
    normalized = value.strip()
    return normalized or None


def _evidence_key(record: Mapping[str, Any]) -> tuple[str, ...]:
    if record["source_url"]:
        return ("url", record["source_url"].casefold())
    return (
        "content",
        (record["source_domain"] or "").casefold(),
        " ".join((record["title"] or "").casefold().split()),
        " ".join((record["snippet"] or "").casefold().split()),
    )


def _secondary_evidence_key(record: Mapping[str, Any]) -> tuple[str, ...] | None:
    title = " ".join((record["title"] or "").casefold().split())
    snippet = " ".join((record["snippet"] or "").casefold().split())
    if not title or not snippet:
        return None
    return ("text", title, snippet)


def _prepare_evidence(
    evidence: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if isinstance(evidence, (str, bytes)) or not isinstance(evidence, Sequence):
        raise EvidenceAnalysisInputError("Evidence must be a list of evidence records.")
    if len(evidence) > MAX_EVIDENCE_ITEMS:
        raise EvidenceAnalysisInputError(
            f"Evidence cannot contain more than {MAX_EVIDENCE_ITEMS} records."
        )

    prepared: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for index, item in enumerate(evidence):
        if not isinstance(item, Mapping):
            raise EvidenceAnalysisInputError(
                f"Evidence item {index + 1} must be an object."
            )
        source_url, url_domain = _normalize_url(item.get("source_url"))
        source_domain = _validate_optional_text(item, "source_domain")
        if source_domain:
            source_domain = source_domain.casefold().rstrip(".")
            if "/" in source_domain or "://" in source_domain or "@" in source_domain:
                raise EvidenceAnalysisInputError(
                    f"Evidence item {index + 1} has an invalid source_domain."
                )
        if url_domain and source_domain and url_domain != source_domain:
            raise EvidenceAnalysisInputError(
                f"Evidence item {index + 1} source_domain does not match source_url."
            )
        domain = url_domain or source_domain

        title = _validate_optional_text(item, "title")
        snippet = _validate_optional_text(item, "snippet")
        page_content = _validate_optional_text(item, "page_content")
        page_content_status = _validate_optional_text(item, "page_content_status")
        source_name = _validate_optional_text(item, "source_name")
        evidence_id = _validate_optional_text(item, "evidence_id")
        published_date = _validate_optional_text(item, "published_date")
        content = " ".join(
            part for part in (snippet, page_content) if part
        )

        _, verified_source_type = classify_source(domain)
        provided_score = item.get("relevance_score")
        if provided_score is not None and (
            isinstance(provided_score, bool)
            or not isinstance(provided_score, (int, float))
        ):
            raise EvidenceAnalysisInputError(
                f"Evidence item {index + 1} relevance_score must be numeric or null."
            )
        if isinstance(provided_score, (int, float)) and not 0 <= provided_score <= 1:
            raise EvidenceAnalysisInputError(
                f"Evidence item {index + 1} relevance_score must be between 0 and 1."
            )

        record = {
            "evidence_id": evidence_id,
            "source_name": source_name,
            "source_domain": domain,
            "source_url": source_url,
            "title": title,
            "snippet": snippet,
            "page_content": page_content,
            "page_content_status": page_content_status,
            "published_date": published_date,
            "relevance_score": provided_score,
            "source_type": verified_source_type,
            "content": content,
        }
        key = _evidence_key(record)
        secondary_key = _secondary_evidence_key(record)
        if key in seen or (secondary_key is not None and secondary_key in seen):
            continue
        seen.add(key)
        if secondary_key is not None:
            seen.add(secondary_key)
        prepared.append(record)
    return prepared


def _relevance(claim_tokens: set[str], evidence_text: str) -> float:
    if not claim_tokens or not evidence_text:
        return 0.0
    evidence_tokens = _tokens(evidence_text)
    return round(len(claim_tokens & evidence_tokens) / len(claim_tokens), 4)


def _stance(claim: str, claim_tokens: set[str], evidence_text: str) -> str:
    """Determine stance: SUPPORTS, CONTRADICTS, MIXED, NEUTRAL, INSUFFICIENT."""
    if not evidence_text or not claim_tokens:
        return STANCE_INSUFFICIENT
    if any(
        character.isalpha()
        and not unicodedata.name(character, "").startswith("LATIN ")
        for character in claim
    ):
        return STANCE_INSUFFICIENT
    evidence_tokens = _tokens(evidence_text)
    overlap = len(claim_tokens & evidence_tokens) / len(claim_tokens)
    if overlap < MIN_RELEVANCE:
        return STANCE_NEUTRAL

    claim_word_list = [token.casefold() for token in tokenize_words(claim)]
    evidence_word_list = [token.casefold() for token in tokenize_words(evidence_text)]
    claim_negated = bool(set(claim_word_list) & _NEGATIONS)
    evidence_negated = bool(set(evidence_word_list) & _NEGATIONS)
    if claim_negated and not evidence_negated and claim_tokens.issubset(evidence_tokens):
        return STANCE_CONTRADICTS
    if evidence_negated and not claim_negated:
        for index, word in enumerate(evidence_word_list):
            preceding = evidence_word_list[max(0, index - 3) : index]
            variants = _WORD_VARIANTS.get(word, {word})
            if variants & claim_tokens and set(preceding) & _NEGATIONS:
                return STANCE_CONTRADICTS

    claim_opposites = {
        opposite
        for token in claim_tokens
        if (opposite := _OPPOSITES.get(token)) is not None
    }
    if claim_opposites & evidence_tokens:
        return STANCE_CONTRADICTS

    # Check for mixed signals within the same evidence
    has_support = overlap >= STRONG_RELEVANCE and claim_tokens.issubset(evidence_tokens)
    has_contradiction = claim_negated != evidence_negated or bool(claim_opposites & evidence_tokens)

    if has_support and has_contradiction:
        return STANCE_MIXED
    if has_support:
        return STANCE_SUPPORTS
    return STANCE_NEUTRAL


def _is_credible(record: Mapping[str, Any]) -> bool:
    return record["source_type"] in {"official", "fact_checker", "news"}


def _dated_context_warning(claim: str, record: Mapping[str, Any]) -> bool:
    if not record["published_date"]:
        return False
    temporal_words = {"current", "currently", "latest", "now", "today", "recently"}
    if not (_tokens(claim) & temporal_words):
        return False
    try:
        from datetime import datetime, timezone

        published = datetime.fromisoformat(
            str(record["published_date"]).replace("Z", "+00:00")
        )
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return (datetime.now(timezone.utc) - published).days > 365


def _claim_components(claim: str) -> list[str]:
    return [
        part.strip(" ,.;:")
        for part in re.split(r"\b(?:but|although|whereas|while|and)\b", claim, flags=re.I)
        if len(_tokens(part)) >= 2
    ]


def _has_partial_component_evidence(
    analyzed: Sequence[Mapping[str, Any]],
    components: Sequence[str],
) -> bool:
    if len(components) < 2:
        return False
    component_support_domains: dict[str, set[str]] = {
        component: set() for component in components
    }
    component_contradiction_domains: dict[str, set[str]] = {
        component: set() for component in components
    }
    for item in analyzed:
        if not item["credible_source"] or not item["source_domain"]:
            continue
        if item["date_context_warning"]:
            continue
        for component, stance in item["component_assessments"].items():
            if stance == STANCE_SUPPORTS:
                component_support_domains[component].add(item["source_domain"])
            elif stance == STANCE_CONTRADICTS:
                component_contradiction_domains[component].add(item["source_domain"])

    for supported_component, support_domains in component_support_domains.items():
        if not support_domains:
            continue
        for contradicted_component, contradiction_domains in (
            component_contradiction_domains.items()
        ):
            if (
                supported_component != contradicted_component
                and contradiction_domains
                and len(support_domains | contradiction_domains)
                >= MIN_INDEPENDENT_CREDIBLE_SOURCES
            ):
                return True
    return False


class EvidenceAnalyzer:
    """Assess evidence text with conservative, transparent lexical rules."""

    def analyze(
        self,
        claim: str,
        evidence: Sequence[Mapping[str, Any]],
        claim_id: int = 1,
        retrieval_status: str = "completed",
    ) -> dict[str, Any]:
        if not isinstance(claim, str):
            raise TypeError("Claim must be a string.")
        original_claim = claim.strip()
        if not original_claim:
            raise EvidenceAnalysisInputError("Claim must not be empty or whitespace.")
        if len(original_claim) > MAX_CLAIM_LENGTH:
            raise EvidenceAnalysisInputError(
                f"Claim exceeds the maximum length of {MAX_CLAIM_LENGTH} characters."
            )
        if isinstance(claim_id, bool) or not isinstance(claim_id, int) or claim_id < 1:
            raise EvidenceAnalysisInputError("claim_id must be a positive integer.")
        if not isinstance(retrieval_status, str):
            raise EvidenceAnalysisInputError("retrieval_status must be a string.")
        if retrieval_status not in {
            "completed",
            "partial",
            "no_results",
            "unavailable",
        }:
            raise EvidenceAnalysisInputError("retrieval_status is not recognized.")

        records = _prepare_evidence(evidence)
        claim_tokens = _tokens(original_claim)
        components = _claim_components(original_claim)
        analyzed: list[dict[str, Any]] = []
        for record in records:
            overlap = _relevance(claim_tokens, record["content"])
            stance = _stance(original_claim, claim_tokens, record["content"])
            component_assessments = {
                component: _stance(
                    component,
                    _tokens(component),
                    record["content"],
                )
                for component in components
            }
            stale_for_current_claim = _dated_context_warning(original_claim, record)
            if stale_for_current_claim:
                stance = STANCE_NEUTRAL
            analyzed.append(
                {
                    **{key: value for key, value in record.items() if key != "content"},
                    "claim_overlap": overlap,
                    "assessment": stance,
                    "credible_source": _is_credible(record),
                    "date_context_warning": stale_for_current_claim,
                    "component_assessments": component_assessments,
                }
            )

        # Categorize by new stance labels
        supports = [item for item in analyzed if item["assessment"] == STANCE_SUPPORTS]
        contradicts = [item for item in analyzed if item["assessment"] == STANCE_CONTRADICTS]
        mixed = [item for item in analyzed if item["assessment"] == STANCE_MIXED]
        neutral = [item for item in analyzed if item["assessment"] == STANCE_NEUTRAL]
        insufficient = [item for item in analyzed if item["assessment"] == STANCE_INSUFFICIENT]

        # For backward compatibility, supporting includes supports + mixed
        supporting = supports + mixed
        contradicting = contradicts + mixed

        relevant_credible_supports = [item for item in supports if item["credible_source"]]
        relevant_credible_contradicts = [item for item in contradicts if item["credible_source"]]

        support_domains = {
            item["source_domain"]
            for item in relevant_credible_supports
            if item["source_domain"]
        }
        contradiction_domains = {
            item["source_domain"]
            for item in relevant_credible_contradicts
            if item["source_domain"]
        }
        partial_components = _has_partial_component_evidence(analyzed, components)

        # Check for conflicting: both supports and contradicts from credible sources
        has_conflict = bool(relevant_credible_supports and relevant_credible_contradicts)
        conflicting = has_conflict and not partial_components

        misleading_items = [
            item
            for item in analyzed
            if item["credible_source"]
            and item["assessment"] != STANCE_INSUFFICIENT
            and item["assessment"] != STANCE_NEUTRAL
            and any(
                marker
                in (
                    f"{item['title'] or ''} {item['snippet'] or ''} "
                    f"{item['page_content'] or ''}"
                ).casefold()
                for marker in _MISLEADING_MARKERS
            )
        ]

        limitations: list[str] = [
            "This is a rule-based assessment of retrieved titles, snippets, and available webpage text, not a statistically calibrated fact-check."
        ]
        if any(
            character.isalpha()
            and not unicodedata.name(character, "").startswith("LATIN ")
            for character in original_claim
        ):
            limitations.append(
                "The original-language claim was not translated; automated stance analysis cannot reliably assess non-English evidence."
            )
        if neutral or insufficient:
            limitations.append(
                "Some supplied items were unrelated or had insufficient text to assess."
            )
        if mixed:
            limitations.append(
                "Some evidence contains both supporting and contradicting signals (MIXED stance)."
            )
        if any(not item["published_date"] for item in analyzed):
            limitations.append(
                "Publication dates were missing for one or more evidence items."
            )
        if any(not item["source_domain"] for item in analyzed):
            limitations.append(
                "Source domains were missing for one or more evidence items."
            )
        if any(item["date_context_warning"] for item in analyzed):
            limitations.append(
                "Some supplied sources predate a time-sensitive claim; their age is not proof of the claim's accuracy."
            )
        if retrieval_status != "completed":
            limitations.append(
                f"Evidence retrieval status was {retrieval_status}; retrieval availability is not evidence about the claim."
            )
        if conflicting:
            limitations.append(
                "Supplied evidence contains both supporting and contradicting signals from credible sources."
            )
        if analyzed:
            limitations.append(
                "A text match or source category alone does not establish that a claim is true or false."
            )

        verdict = VERDICT_INSUFFICIENT_EVIDENCE
        confidence: float | None = None
        rationale = "The supplied evidence does not justify a definitive verdict."

        if any(
            character.isalpha()
            and not unicodedata.name(character, "").startswith("LATIN ")
            for character in original_claim
        ):
            rationale = (
                "The claim was preserved and searched in its original language, but automatic evidence stance analysis requires an English translation."
            )

        misleading_domains = {
            item["source_domain"]
            for item in misleading_items
            if item["source_domain"]
        }

        # Decision logic per design document
        if retrieval_status == "unavailable":
            rationale = (
                "Web evidence could not be retrieved (retrieval was unavailable); that failure provides no basis to decide the claim."
            )
        elif (
            len(misleading_domains) >= MIN_INDEPENDENT_CREDIBLE_SOURCES
            and not conflicting
        ):
            verdict = VERDICT_MISLEADING
            rationale = (
                f"{len(misleading_domains)} distinct recognized credible source domains explicitly describe the relevant context as misleading or out of context."
            )
            confidence = 0.7
        elif partial_components and not conflicting:
            verdict = VERDICT_PARTIALLY_TRUE
            rationale = (
                "Supplied evidence supports one part of the claim and contradicts another; the claim is not wholly supported."
            )
            confidence = 0.65
        elif (
            retrieval_status != "unavailable"
            and not conflicting
            and len(support_domains) >= MIN_INDEPENDENT_CREDIBLE_SOURCES
            and len(relevant_credible_supports) >= MIN_INDEPENDENT_CREDIBLE_SOURCES
            and not relevant_credible_contradicts
        ):
            verdict = VERDICT_TRUE
            rationale = (
                f"{len(support_domains)} distinct recognized credible source domains provide closely matching supplied text, with no supplied contradictory signal."
            )
            confidence = 0.75
        elif (
            retrieval_status != "unavailable"
            and not conflicting
            and len(contradiction_domains) >= MIN_INDEPENDENT_CREDIBLE_SOURCES
            and len(relevant_credible_contradicts) >= MIN_INDEPENDENT_CREDIBLE_SOURCES
            and not relevant_credible_supports
        ):
            verdict = VERDICT_FALSE
            rationale = (
                f"{len(contradiction_domains)} distinct recognized credible source domains provide text that conflicts with the claim, with no supplied supporting signal."
            )
            confidence = 0.75
        elif conflicting:
            # Conflicting evidence from credible sources - needs human review for high-impact topics
            rationale = (
                "The supplied evidence includes both supporting and contradicting text from credible sources; the conflict cannot be resolved automatically."
            )
            verdict = VERDICT_NEEDS_HUMAN_REVIEW
        elif supporting:
            rationale = (
                "Some supplied text matches the claim, but there are not enough independent recognized credible sources for a decisive verdict."
            )
        elif contradicting:
            rationale = (
                "Some supplied text conflicts with the claim, but there are not enough independent recognized credible sources for a decisive verdict."
            )
        elif not records:
            rationale = "No evidence was supplied for this claim."

        sources_used = []
        seen_sources: set[tuple[str | None, str | None]] = set()
        for item in analyzed:
            if item["assessment"] in {STANCE_NEUTRAL, STANCE_INSUFFICIENT}:
                continue
            source_key = (item["source_name"], item["source_domain"])
            if source_key in seen_sources:
                continue
            seen_sources.add(source_key)
            sources_used.append(
                {
                    "source_name": item["source_name"],
                    "source_domain": item["source_domain"],
                    "source_url": item["source_url"],
                    "source_type": item["source_type"],
                }
            )

        if verdict not in _VERDICTS:
            raise RuntimeError("Evidence analysis produced an unsupported verdict.")

        return {
            "claim_id": claim_id,
            "original_claim": original_claim,
            "verdict": verdict,
            "confidence": confidence,
            "confidence_type": (
                "heuristic estimate; not a statistically calibrated probability"
                if confidence is not None
                else None
            ),
            "explanation": rationale,
            "supporting_evidence": supports,
            "contradicting_evidence": contradicts,
            "mixed_evidence": mixed,
            "neutral_evidence": neutral,
            "insufficient_evidence": insufficient,
            "sources_used": sources_used,
            "limitations": limitations,
            "verification_status": "analyzed",
        }


# Exported constants for API use
__all__ = [
    "EvidenceAnalyzer",
    "EvidenceAnalysisInputError",
    "STANCE_SUPPORTS",
    "STANCE_CONTRADICTS",
    "STANCE_MIXED",
    "STANCE_NEUTRAL",
    "STANCE_INSUFFICIENT",
    "VERDICT_TRUE",
    "VERDICT_FALSE",
    "VERDICT_PARTIALLY_TRUE",
    "VERDICT_MISLEADING",
    "VERDICT_INSUFFICIENT_EVIDENCE",
    "VERDICT_NEEDS_HUMAN_REVIEW",
]