"""Public-source search for candidate evidence related to a claim.

Search results are leads for later review, not factual verification.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import ssl
import time
from datetime import datetime, timezone
from typing import Any, Callable, Protocol
from urllib.parse import urlsplit, urlunsplit

import httpx

from src.config import get_settings
from src.text_utils import tokenize_words

LOGGER = logging.getLogger(__name__)
GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"
GOOGLE_FACTCHECK_API = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_MAX_RESULTS = 5
DEFAULT_MAX_RESPONSE_BYTES = 1_000_000
DEFAULT_MAX_CLAIM_LENGTH = 5_000
DEFAULT_MAX_ARTICLE_FETCHES = 3
MAX_RESULTS_LIMIT = 20
MAX_SEARCH_TERMS = 12
MAX_PAGE_CONTENT_LENGTH = 20_000
MAX_SNIPPET_LENGTH = 500
DEFAULT_USER_AGENT = "TruthLensAI/1.0 (public evidence search)"

_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "for", "from",
    "has", "have", "in", "is", "it", "of", "on", "or", "that", "the", "this",
    "to", "was", "were", "will", "with", "about", "after", "also", "before",
    "between", "during", "into", "over", "said", "says", "according",
}

_OFFICIAL_DOMAINS = {
    "india.gov.in": "Government of India",
    "pib.gov.in": "Press Information Bureau",
    "factcheck.pib.gov.in": "PIB Fact Check",
    "eci.gov.in": "Election Commission of India",
    "who.int": "World Health Organization",
    "un.org": "United Nations",
}
_FACT_CHECKER_DOMAINS = {
    "altnews.in": "Alt News",
    "boomlive.in": "BOOM Live",
    "factly.in": "Factly",
    "snopes.com": "Snopes",
    "fullfact.org": "Full Fact",
}
_NEWS_DOMAINS = {
    "reuters.com": "Reuters",
    "apnews.com": "Associated Press",
    "bbc.com": "BBC",
    "bbc.co.uk": "BBC",
    "theguardian.com": "The Guardian",
    "indianexpress.com": "The Indian Express",
    "thehindu.com": "The Hindu",
    "ndtv.com": "NDTV",
}


class EvidenceInputError(ValueError):
    """Raised when a claim cannot be searched safely."""


class ResponseTooLargeError(Exception):
    """Raised when a source response exceeds its configured byte limit."""


def is_tls_error(error: BaseException) -> bool:
    pending: list[BaseException] = [error]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, ssl.SSLError):
            return True
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
        pending.extend(
            argument
            for argument in current.args
            if isinstance(argument, BaseException)
        )
    return False


class SearchSource(Protocol):
    """Interface implemented by public search-source adapters."""

    name: str

    def search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        """Return source-provided result metadata for a query."""


def _domain_matches(host: str, known_domain: str) -> bool:
    return host == known_domain or host.endswith(f".{known_domain}")


def classify_source(domain: str | None) -> tuple[str, str]:
    """Classify a recognized source domain without inferring claim truth."""
    host = (domain or "").strip().casefold().rstrip(".")
    if not host:
        return "Unknown source", "unknown"

    for known_domain, name in _OFFICIAL_DOMAINS.items():
        if _domain_matches(host, known_domain):
            return name, "official"
    for known_domain, name in _FACT_CHECKER_DOMAINS.items():
        if _domain_matches(host, known_domain):
            return name, "fact_checker"
    for known_domain, name in _NEWS_DOMAINS.items():
        if _domain_matches(host, known_domain):
            return name, "news"
    if host.endswith((".gov", ".gov.in", ".gov.uk", ".nic.in")):
        return host, "official"
    return host, "unknown"


def build_search_query(claim: str) -> str:
    """Build a bounded, de-duplicated keyword query from a factual claim."""
    if not isinstance(claim, str):
        raise TypeError("Claim must be a string.")
    normalized = claim.strip()
    if not normalized:
        raise EvidenceInputError("Claim must not be empty or whitespace.")
    if len(normalized) > DEFAULT_MAX_CLAIM_LENGTH:
        raise EvidenceInputError(
            f"Claim exceeds the maximum length of {DEFAULT_MAX_CLAIM_LENGTH} characters."
        )

    words: list[tuple[str, int]] = []
    seen_words: set[str] = set()
    for index, word in enumerate(tokenize_words(normalized)):
        normalized_word = word.casefold()
        if normalized_word in _STOP_WORDS or normalized_word in seen_words:
            continue
        words.append((word, index))
        seen_words.add(normalized_word)
    if not words:
        words = [
            (word, index)
            for index, word in enumerate(tokenize_words(normalized))
        ]

    if len(words) > MAX_SEARCH_TERMS:
        priority_terms = [
            word
            for word, index in words
            if any(character.isdigit() for character in word)
            or (index > 0 and word[:1].isupper())
        ]
        selected_words = {
            word.casefold() for word in priority_terms[:MAX_SEARCH_TERMS]
        }
        for word, _ in words:
            if len(selected_words) >= MAX_SEARCH_TERMS:
                break
            selected_words.add(word.casefold())
        words = [
            (word, index)
            for word, index in words
            if word.casefold() in selected_words
        ]
    return " ".join(word for word, _ in words[:MAX_SEARCH_TERMS])[:300]


def _canonicalize_url(value: Any) -> tuple[str, str] | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value.strip())
        host = (parsed.hostname or "").casefold().rstrip(".")
        if parsed.scheme.casefold() not in {"http", "https"} or not host:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        port = parsed.port
    except ValueError:
        return None

    netloc = host
    if port is not None and not (
        (parsed.scheme.casefold() == "http" and port == 80)
        or (parsed.scheme.casefold() == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"
    canonical = urlunsplit(
        (parsed.scheme.casefold(), netloc, parsed.path or "/", parsed.query, "")
    )
    return canonical, host


def _normalized_title(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(tokenize_words(value.casefold()))


def _relevance_score(
    claim: str,
    title: str,
    snippet: str | None,
    page_content: str | None = None,
) -> float:
    claim_tokens = {
        token.casefold()
        for token in tokenize_words(claim)
        if token.casefold() not in _STOP_WORDS
    }
    if not claim_tokens:
        return 0.0
    result_tokens = {
        token.casefold()
        for token in tokenize_words(
            f"{title} {snippet or ''} {page_content or ''}"
        )
        if token.casefold() not in _STOP_WORDS
    }
    return round(len(claim_tokens & result_tokens) / len(claim_tokens), 4)


def extract_relevant_snippet(claim: str, text: str) -> str | None:
    """Return a short verbatim excerpt from retrieved text, preferring claim overlap."""
    if not isinstance(text, str) or not text.strip():
        return None

    passages = [
        " ".join(part.split())
        for part in re.split(r"(?<=[.!?])\s+|[\r\n]+", text)
        if part.strip()
    ]
    if not passages:
        return None
    excerpt = max(
        enumerate(passages),
        key=lambda item: (_relevance_score(claim, item[1], None), -item[0]),
    )[1]
    return excerpt[:MAX_SNIPPET_LENGTH].strip() or None


def _published_date(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    for date_format in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S"):
        try:
            parsed = datetime.strptime(raw, date_format)
            return parsed.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def _fingerprint(result: dict[str, Any]) -> str:
    """Generate a stable fingerprint for deduplication across sources."""
    # Use title + snippet + domain for content-based fingerprint
    title = (result.get("title") or "").strip().casefold()
    snippet = (result.get("snippet") or "").strip().casefold()
    domain = (result.get("domain") or "").strip().casefold()
    content = f"{title}|{snippet}|{domain}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _filter_by_time_window(
    articles: list[dict[str, Any]],
    time_window_days: int,
) -> list[dict[str, Any]]:
    """Filter articles by publication date within time window."""
    if time_window_days <= 0:
        return articles

    cutoff = datetime.now(timezone.utc).timestamp() - (time_window_days * 86400)
    filtered = []
    for article in articles:
        pub_date = article.get("published_date")
        if pub_date:
            try:
                parsed = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                if parsed.timestamp() >= cutoff:
                    filtered.append(article)
            except (ValueError, AttributeError):
                # Keep articles with unparseable dates
                filtered.append(article)
        else:
            # Keep articles without dates (might be recent)
            filtered.append(article)
    return filtered


class GdeltDocSource:
    """Search the public GDELT DOC API for indexed news article metadata."""

    name = "GDELT DOC API"

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        user_agent: str = DEFAULT_USER_AGENT,
        retry_limit: int = 1,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        article_fetcher: Callable[[str], dict[str, Any]] | None = None,
        time_window_days: int = 7,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive.")
        if retry_limit < 0:
            raise ValueError("retry_limit cannot be negative.")
        if max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive.")
        if time_window_days < 0:
            raise ValueError("time_window_days cannot be negative.")
        self.timeout = timeout
        self.user_agent = user_agent
        self.retry_limit = retry_limit
        self.max_response_bytes = max_response_bytes
        self.article_fetcher = article_fetcher
        self.time_window_days = time_window_days

    def _fetch_article(self, url: str) -> dict[str, Any]:
        if self.article_fetcher is not None:
            return self.article_fetcher(url)

        from src.input_processor import InputProcessor

        processor = InputProcessor(
            timeout=min(self.timeout, 4.0),
            max_response_bytes=self.max_response_bytes,
            max_input_length=MAX_PAGE_CONTENT_LENGTH,
            user_agent=self.user_agent,
        )
        return processor.process_url(url)

    def _fetch_json(self, query: str, max_results: int) -> dict[str, Any]:
        params = {
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": str(max_results),
            "sort": "HybridRel",
        }
        for attempt in range(self.retry_limit + 1):
            try:
                chunks: list[bytes] = []
                response_size = 0
                with httpx.Client(
                    timeout=self.timeout,
                    headers={"User-Agent": self.user_agent},
                    follow_redirects=True,
                ) as client:
                    with client.stream("GET", GDELT_DOC_API, params=params) as response:
                        if response.status_code == 429 or response.status_code >= 500:
                            response.raise_for_status()
                        response.raise_for_status()
                        content_length = response.headers.get("content-length")
                        if content_length:
                            try:
                                if int(content_length) > self.max_response_bytes:
                                    raise ResponseTooLargeError(
                                        "Search response exceeded the configured size limit."
                                    )
                            except ValueError:
                                pass
                        for chunk in response.iter_bytes():
                            response_size += len(chunk)
                            if response_size > self.max_response_bytes:
                                raise ResponseTooLargeError(
                                    "Search response exceeded the configured size limit."
                                )
                            chunks.append(chunk)
                try:
                    result = httpx.Response(200, content=b"".join(chunks)).json()
                except ValueError as exc:
                    raise ValueError("Search source returned malformed JSON.") from exc
                if not isinstance(result, dict):
                    raise ValueError("Search source returned an invalid response.")
                return result
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                retryable = status_code == 429 or status_code >= 500
                if retryable and attempt < self.retry_limit:
                    time.sleep(min(0.25 * (attempt + 1), 1.0))
                    continue
                raise
            except httpx.RequestError as exc:
                if is_tls_error(exc):
                    raise
                if attempt < self.retry_limit:
                    time.sleep(min(0.25 * (attempt + 1), 1.0))
                    continue
                raise
        raise RuntimeError("Search request failed unexpectedly.")

    def search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        response = self._fetch_json(query, max_results)
        articles = response.get("articles")
        if not isinstance(articles, list):
            raise ValueError("Search source response did not contain an articles list.")
        if any(not isinstance(article, dict) for article in articles):
            raise ValueError("Search source response contained an invalid article.")

        normalized_articles = [dict(article) for article in articles]

        # Apply time window filtering
        normalized_articles = _filter_by_time_window(normalized_articles, self.time_window_days)

        fetch_count = 0
        fetched_urls: set[str] = set()
        for article in normalized_articles:
            canonical_url = _canonicalize_url(article.get("url"))
            if canonical_url is None:
                continue
            article_url = canonical_url[0]
            if article_url in fetched_urls or fetch_count >= min(
                max_results,
                DEFAULT_MAX_ARTICLE_FETCHES,
            ):
                continue
            fetched_urls.add(article_url)
            fetch_count += 1
            article["page_content_status"] = "unavailable"
            try:
                page = self._fetch_article(article_url)
            except httpx.TimeoutException:
                article["page_content_error"] = "timeout"
                continue
            except httpx.HTTPStatusError:
                article["page_content_error"] = "http_error"
                continue
            except (httpx.RequestError, OSError):
                article["page_content_error"] = "network_error"
                continue
            except Exception:
                LOGGER.exception("GDELT article content fetch failed")
                article["page_content_error"] = "content_unavailable"
                continue

            if not isinstance(page, dict):
                article["page_content_error"] = "malformed_response"
                continue
            if page.get("processing_status") != "processed":
                article["page_content_error"] = "content_unavailable"
                continue
            content = page.get("extracted_text")
            if not isinstance(content, str) or not content.strip():
                article["page_content_error"] = "content_unavailable"
                continue
            article["page_content"] = content[:MAX_PAGE_CONTENT_LENGTH]
            article["page_content_status"] = "retrieved"
            page_title = page.get("title")
            if not isinstance(article.get("title"), str) and isinstance(
                page_title,
                str,
            ):
                article["title"] = page_title
        return normalized_articles


class GoogleFactCheckSource:
    """Search the Google Fact Check Tools API for existing fact-checks."""

    name = "Google Fact Check Tools"

    def __init__(
        self,
        api_key: str,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        user_agent: str = DEFAULT_USER_AGENT,
        retry_limit: int = 1,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        language_codes: tuple[str, ...] = ("en",),
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required for Google Fact Check Tools API.")
        if timeout <= 0:
            raise ValueError("timeout must be positive.")
        if retry_limit < 0:
            raise ValueError("retry_limit cannot be negative.")
        if max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive.")
        self.api_key = api_key
        self.timeout = timeout
        self.user_agent = user_agent
        self.retry_limit = retry_limit
        self.max_response_bytes = max_response_bytes
        self.language_codes = language_codes

    def _fetch_json(self, query: str, max_results: int) -> dict[str, Any]:
        params = {
            "query": query,
            "key": self.api_key,
            "pageSize": str(min(max_results, 20)),
        }
        # Add language codes
        for lang in self.language_codes:
            params.setdefault("languageCode", lang)

        for attempt in range(self.retry_limit + 1):
            try:
                chunks: list[bytes] = []
                response_size = 0
                with httpx.Client(
                    timeout=self.timeout,
                    headers={"User-Agent": self.user_agent},
                    follow_redirects=True,
                ) as client:
                    with client.stream("GET", GOOGLE_FACTCHECK_API, params=params) as response:
                        if response.status_code == 429 or response.status_code >= 500:
                            response.raise_for_status()
                        response.raise_for_status()
                        content_length = response.headers.get("content-length")
                        if content_length:
                            try:
                                if int(content_length) > self.max_response_bytes:
                                    raise ResponseTooLargeError(
                                        "Search response exceeded the configured size limit."
                                    )
                            except ValueError:
                                pass
                        for chunk in response.iter_bytes():
                            response_size += len(chunk)
                            if response_size > self.max_response_bytes:
                                raise ResponseTooLargeError(
                                    "Search response exceeded the configured size limit."
                                )
                            chunks.append(chunk)
                try:
                    result = httpx.Response(200, content=b"".join(chunks)).json()
                except ValueError as exc:
                    raise ValueError("Search source returned malformed JSON.") from exc
                if not isinstance(result, dict):
                    raise ValueError("Search source returned an invalid response.")
                return result
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                retryable = status_code == 429 or status_code >= 500
                if retryable and attempt < self.retry_limit:
                    time.sleep(min(0.25 * (attempt + 1), 1.0))
                    continue
                raise
            except httpx.RequestError as exc:
                if is_tls_error(exc):
                    raise
                if attempt < self.retry_limit:
                    time.sleep(min(0.25 * (attempt + 1), 1.0))
                    continue
                raise
        raise RuntimeError("Search request failed unexpectedly.")

    def search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        response = self._fetch_json(query, max_results)
        claims = response.get("claims")
        if not isinstance(claims, list):
            raise ValueError("Search source response did not contain a claims list.")

        results = []
        for claim in claims:
            if not isinstance(claim, dict):
                continue

            claim_text = claim.get("text", "")
            claim_reviews = claim.get("claimReview", [])

            for review in claim_reviews:
                if not isinstance(review, dict):
                    continue

                publisher = review.get("publisher", {})
                publisher_name = publisher.get("name", "Unknown Publisher")
                publisher_site = publisher.get("site", "")

                url = review.get("url", "")
                title = review.get("title", "")
                review_date = review.get("reviewDate", "")
                rating = review.get("textualRating", "")

                canonical_url = _canonicalize_url(url)
                if canonical_url is None:
                    continue
                source_url, domain = canonical_url

                snippet = f"{publisher_name}: {rating} - {title}"

                results.append({
                    "source_url": source_url,
                    "source_domain": domain,
                    "title": title,
                    "snippet": snippet,
                    "published_date": _published_date(review_date),
                    "publisher": publisher_name,
                    "publisher_site": publisher_site,
                    "rating": rating,
                    "claim_text": claim_text,
                    "connector": "google_factcheck",
                    "connector_status": "success",
                    "relevance_score": 0.0,  # Will be computed later
                })

                if len(results) >= max_results:
                    break
            if len(results) >= max_results:
                break

        return results


class EvidenceRetriever:
    """Search configured public sources and return deduplicated evidence leads."""

    def __init__(
        self,
        sources: tuple[SearchSource, ...] | list[SearchSource] | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_results: int = DEFAULT_MAX_RESULTS,
        user_agent: str = DEFAULT_USER_AGENT,
        retry_limit: int = 1,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        gdelt_time_window_days: int = 7,
        google_factcheck_api_key: str | None = None,
        google_factcheck_language_codes: tuple[str, ...] = ("en",),
    ) -> None:
        if isinstance(max_results, bool) or not isinstance(max_results, int):
            raise TypeError("max_results must be an integer.")
        if max_results < 1:
            raise ValueError("max_results must be at least one.")
        if max_results > MAX_RESULTS_LIMIT:
            raise ValueError(f"max_results cannot exceed {MAX_RESULTS_LIMIT}.")

        self.max_results = max_results

        if sources is not None:
            self.sources: tuple[SearchSource, ...] = tuple(sources)
        else:
            # Build default sources from config
            settings = get_settings()
            default_sources: list[SearchSource] = [
                GdeltDocSource(
                    timeout=timeout,
                    user_agent=user_agent,
                    retry_limit=retry_limit,
                    max_response_bytes=max_response_bytes,
                    time_window_days=gdelt_time_window_days,
                ),
            ]

            # Add Google Fact Check if enabled and configured
            if settings.google_factcheck_enabled and google_factcheck_api_key:
                default_sources.append(
                    GoogleFactCheckSource(
                        api_key=google_factcheck_api_key,
                        timeout=timeout,
                        user_agent=user_agent,
                        retry_limit=retry_limit,
                        max_response_bytes=max_response_bytes,
                        language_codes=google_factcheck_language_codes,
                    )
                )

            self.sources = tuple(default_sources)

    def retrieve(self, claim: str, claim_id: int = 1) -> dict[str, Any]:
        if not isinstance(claim, str):
            raise TypeError("Claim must be a string.")
        query = build_search_query(claim)
        if isinstance(claim_id, bool) or not isinstance(claim_id, int):
            raise TypeError("claim_id must be an integer.")
        if claim_id < 1:
            raise ValueError("claim_id must be a positive integer.")

        collected: list[tuple[dict[str, Any], str]] = []
        source_errors: list[dict[str, str]] = []
        successful_sources = 0

        for source in self.sources:
            try:
                results = source.search(query, self.max_results)
                if not isinstance(results, list):
                    raise ValueError("Search source returned an invalid result list.")
                successful_sources += 1
                for result in results:
                    if isinstance(result, dict):
                        collected.append((result, source.name))
                    else:
                        source_errors.append(
                            {"source": source.name, "error": "malformed_response"}
                        )
            except httpx.TimeoutException:
                source_errors.append(
                    {"source": source.name, "error": "timeout"}
                )
            except httpx.HTTPStatusError as exc:
                error = "rate_limited" if exc.response.status_code == 429 else "http_error"
                source_errors.append({"source": source.name, "error": error})
            except ssl.SSLError:
                source_errors.append(
                    {"source": source.name, "error": "tls_error"}
                )
            except httpx.RequestError as exc:
                source_errors.append(
                    {
                        "source": source.name,
                        "error": (
                            "tls_error" if is_tls_error(exc) else "network_error"
                        ),
                    }
                )
            except ResponseTooLargeError:
                source_errors.append(
                    {"source": source.name, "error": "response_too_large"}
                )
            except (ValueError, TypeError):
                source_errors.append(
                    {"source": source.name, "error": "malformed_response"}
                )
            except Exception:
                LOGGER.exception("Evidence search source failed: %s", source.name)
                source_errors.append(
                    {"source": source.name, "error": "source_unavailable"}
                )

        # Fingerprint-based deduplication across ALL sources
        seen_fingerprints: set[str] = set()
        seen_urls: set[str] = set()
        seen_titles: set[str] = set()
        evidence: list[dict[str, Any]] = []
        retrieved_at = datetime.now(timezone.utc).isoformat()
        source_priority = {
            "official": 0,
            "fact_checker": 1,
            "news": 2,
            "other": 3,
            "unknown": 4,
        }

        def candidate_priority(
            item: tuple[dict[str, Any], str],
        ) -> tuple[float, int]:
            result = item[0]
            canonical_url = _canonicalize_url(result.get("url") or result.get("source_url"))
            domain = canonical_url[1] if canonical_url else None
            source_type = classify_source(domain)[1]
            title = result.get("title")
            snippet = result.get("snippet")
            page_content = result.get("page_content")
            return (
                -_relevance_score(
                    claim,
                    title if isinstance(title, str) else "",
                    snippet if isinstance(snippet, str) else None,
                    page_content if isinstance(page_content, str) else None,
                ),
                source_priority[source_type],
            )

        collected.sort(key=candidate_priority)

        for result, source_name in collected:
            if not isinstance(result, dict):
                continue

            # Get URL - handle both GDELT (url) and Google Fact Check (source_url)
            url = result.get("url") or result.get("source_url")
            canonical_url = _canonicalize_url(url)
            if canonical_url is None:
                continue
            source_url, domain = canonical_url

            title_value = result.get("title")
            title = title_value.strip() if isinstance(title_value, str) else ""
            normalized_title = _normalized_title(title)

            # Fingerprint deduplication
            fingerprint = _fingerprint({
                "title": title,
                "snippet": result.get("snippet", ""),
                "domain": domain,
            })
            if fingerprint in seen_fingerprints:
                continue

            if source_url in seen_urls or (normalized_title and normalized_title in seen_titles):
                continue

            seen_fingerprints.add(fingerprint)
            seen_urls.add(source_url)
            if normalized_title:
                seen_titles.add(normalized_title)

            snippet_value = result.get("snippet")
            if not isinstance(snippet_value, str) or not snippet_value.strip():
                snippet_value = result.get("description")
            snippet = (
                snippet_value.strip()
                if isinstance(snippet_value, str) and snippet_value.strip()
                else None
            )
            page_content_value = result.get("page_content")
            page_content = (
                page_content_value[:MAX_PAGE_CONTENT_LENGTH].strip()
                if isinstance(page_content_value, str)
                and page_content_value.strip()
                else None
            )
            if snippet is None:
                snippet = extract_relevant_snippet(claim, page_content or "")

            # Handle page_content_error from GDELT
            if result.get("page_content_error"):
                source_errors.append(
                    {
                        "source": domain,
                        "error": str(result["page_content_error"]),
                    }
                )

            classified_name, source_type = classify_source(domain)

            # Build evidence record
            evidence_record = {
                "evidence_id": f"EV{len(evidence) + 1:03d}",
                "claim_id": claim_id,
                "source_name": (
                    classified_name
                    if source_type != "unknown"
                    else (domain or source_name)
                ),
                "source_domain": domain,
                "source_url": source_url,
                "title": title or None,
                "snippet": snippet,
                "page_content": page_content,
                "page_content_status": result.get(
                    "page_content_status",
                    "not_attempted",
                ),
                "published_date": _published_date(result.get("published_date") or result.get("review_date")),
                "retrieved_at": retrieved_at,
                "source_type": source_type,
                "relevance_score": _relevance_score(
                    claim,
                    title,
                    snippet,
                    page_content,
                ),
                "retrieval_status": "retrieved",
                "connector": result.get("connector", "gdelt"),
                "connector_status": result.get("connector_status", "success"),
            }

            # Add fact-check specific fields if present
            if "publisher" in result:
                evidence_record["publisher"] = result["publisher"]
            if "rating" in result:
                evidence_record["rating"] = result["rating"]
            if "claim_text" in result:
                evidence_record["claim_text"] = result["claim_text"]

            evidence.append(evidence_record)

            if len(evidence) >= self.max_results:
                break

        if source_errors and evidence:
            retrieval_status = "partial"
        elif source_errors and successful_sources == 0:
            retrieval_status = "unavailable"
        elif source_errors:
            retrieval_status = "partial"
        elif evidence:
            retrieval_status = "completed"
        elif successful_sources:
            retrieval_status = "no_results"
        else:
            retrieval_status = "unavailable"

        return {
            "success": successful_sources > 0,
            "claim_id": claim_id,
            "query": query,
            "total_results": len(evidence),
            "evidence": evidence,
            "retrieval_status": retrieval_status,
            "source_errors": source_errors,
        }