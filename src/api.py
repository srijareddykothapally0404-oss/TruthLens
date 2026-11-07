from __future__ import annotations

import asyncio
import logging
import os
import uuid
from pathlib import Path, PurePath
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.claim_extractor import (
    ArticleTooLongError,
    extract_claims,
    update_claim,
    add_claim,
    delete_claim,
)
from src.config import get_settings
from src.database import get_database
from src.evidence_analyzer import (
    EvidenceAnalysisInputError,
    EvidenceAnalyzer,
    MAX_EVIDENCE_ITEMS,
    STANCE_SUPPORTS,
    STANCE_CONTRADICTS,
    STANCE_MIXED,
    STANCE_NEUTRAL,
    STANCE_INSUFFICIENT,
    VERDICT_TRUE,
    VERDICT_FALSE,
    VERDICT_PARTIALLY_TRUE,
    VERDICT_MISLEADING,
    VERDICT_INSUFFICIENT_EVIDENCE,
    VERDICT_NEEDS_HUMAN_REVIEW,
)
from src.evidence_retrieval import (
    DEFAULT_MAX_RESULTS,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_USER_AGENT,
    EvidenceInputError,
    EvidenceRetriever,
    MAX_RESULTS_LIMIT,
    MAX_PAGE_CONTENT_LENGTH,
    classify_source,
    build_search_query,
    extract_relevant_snippet,
    is_tls_error,
)
from src.input_processor import (
    DEFAULT_MAX_IMAGE_PIXELS,
    DEFAULT_MAX_INPUT_LENGTH,
    DEFAULT_MAX_REDIRECTS,
    DEFAULT_MAX_RESPONSE_BYTES as DEFAULT_INPUT_MAX_RESPONSE_BYTES,
    DEFAULT_MAX_UPLOAD_BYTES,
    DEFAULT_TIMEOUT_SECONDS as DEFAULT_INPUT_TIMEOUT_SECONDS,
    DEFAULT_USER_AGENT as DEFAULT_INPUT_USER_AGENT,
    InputProcessor,
)
from src.language_detector import LanguageDetector, SUPPORTED_LANGUAGES
from src.predictor import NewsClassifier
from src.translation_service import TranslationService

LOGGER = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_DIR = BASE_DIR / "models"
CLASSIFIER_NAME = "TF-IDF + LinearSVC"
CLASSIFICATION_EXPLANATION = (
    "This is a pattern-based prediction from the classifier, not factual "
    "verification."
)
VERIFICATION_NOTICE = (
    "This endpoint reports only a classifier signal. Use /api/verify for claim extraction and evidence-based assessments."
)


# ============================================================
# Unified Verification Request/Response Models
# ============================================================

class VerificationOptions(BaseModel):
    """Options for the unified verification endpoint."""
    model_config = ConfigDict(extra="forbid")

    language: str | None = Field(default=None, description="ISO language code (e.g., 'en', 'hi')")
    claim_selection: Literal["auto", "manual", "all"] = Field(
        default="auto", description="How to select claims for verification"
    )
    evidence_sources: list[Literal["gdelt", "google_factcheck", "social"]] = Field(
        default_factory=lambda: ["gdelt", "google_factcheck"],
        description="Evidence sources to query"
    )
    time_window_days: int = Field(default=7, ge=1, le=365, description="Time window for evidence search")
    max_results: int = Field(default=10, ge=1, le=20, description="Max evidence items per claim")
    include_claim_offsets: bool = Field(default=False, description="Include character offsets for claims")
    include_raw_evidence: bool = Field(default=False, description="Include full evidence content")


class UnifiedVerifyRequest(BaseModel):
    """Unified verification request."""
    model_config = ConfigDict(extra="forbid")

    input: Annotated[str, Field(min_length=1, max_length=1_000_000)]
    input_type: Literal["text", "url", "image", "auto"] = "auto"
    options: VerificationOptions | None = None

    @field_validator("input")
    @classmethod
    def input_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Input must not be empty or whitespace.")
        return value


class LanguageDetectionResult(BaseModel):
    language_code: str
    language_name: str
    confidence: float
    status: str
    warning: str | None = None


class TranslationResult(BaseModel):
    original_text: str
    translated_text: str | None
    source_language: str
    target_language: str
    translation_status: str
    warnings: list[str] = []
    error: str | None = None


class ClaimAssessment(BaseModel):
    verdict: Literal[
        "TRUE", "FALSE", "PARTIALLY TRUE", "MISLEADING",
        "INSUFFICIENT EVIDENCE", "NEEDS HUMAN REVIEW"
    ]
    confidence: float | None = None
    confidence_type: str | None = "heuristic estimate; not a statistically calibrated probability"
    explanation: str
    limitations: list[str] = []


class EvidenceRecord(BaseModel):
    evidence_id: str
    claim_id: str
    source_type: Literal["official", "fact_checker", "news", "social", "unknown"]
    title: str
    publisher: str
    domain: str
    url: str
    published_at: str | None = None
    retrieved_at: str
    snippet: str
    content_status: Literal["retrieved", "not_attempted", "unavailable", "error"]
    query: str
    connector: Literal["gdelt", "google_factcheck", "social"]
    connector_status: Literal["success", "rate_limited", "error"]
    relevance_score: float
    stance: Literal["SUPPORTS", "CONTRADICTS", "MIXED", "NEUTRAL", "INSUFFICIENT"]


class ClaimResult(BaseModel):
    claim_id: str
    claim_text: str
    claim_type: Literal["factual", "opinion", "prediction"] = "factual"
    verification_status: Literal["completed", "pending", "failed"] = "completed"
    start_offset: int | None = None
    end_offset: int | None = None
    assessment: ClaimAssessment | None = None
    evidence: list[EvidenceRecord] = []


class UnifiedVerifyResponse(BaseModel):
    verification_id: str
    input_type: str
    original_input: str
    extracted_text: str
    language_detection: LanguageDetectionResult
    translation: TranslationResult | None = None
    claims: list[ClaimResult]
    overall_verdict: Literal[
        "TRUE", "FALSE", "PARTIALLY TRUE", "MISLEADING",
        "INSUFFICIENT EVIDENCE", "NEEDS HUMAN REVIEW"
    ]
    overall_confidence: float | None = None
    overall_explanation: str
    warnings: list[str] = []
    status: Literal["completed", "partial", "failed"] = "completed"


# ============================================================
# Legacy Models (kept for backward compatibility)
# ============================================================

class APISettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str = "1.0.0"
    model_dir: Path = DEFAULT_MODEL_DIR
    evidence_timeout: float = Field(default=DEFAULT_TIMEOUT_SECONDS, gt=0)
    evidence_max_results: int = Field(
        default=DEFAULT_MAX_RESULTS,
        ge=1,
        le=MAX_RESULTS_LIMIT,
    )
    evidence_user_agent: str = DEFAULT_USER_AGENT
    evidence_retry_limit: int = Field(default=1, ge=0)
    input_timeout: float = Field(default=DEFAULT_INPUT_TIMEOUT_SECONDS, gt=0)
    input_max_length: int = Field(default=DEFAULT_MAX_INPUT_LENGTH, ge=1, le=1_000_000)
    input_max_response_bytes: int = Field(
        default=DEFAULT_INPUT_MAX_RESPONSE_BYTES,
        ge=1,
    )
    input_max_upload_bytes: int = Field(default=DEFAULT_MAX_UPLOAD_BYTES, ge=1)
    input_max_image_pixels: int = Field(default=DEFAULT_MAX_IMAGE_PIXELS, ge=1)
    input_max_redirects: int = Field(default=DEFAULT_MAX_REDIRECTS, ge=0)
    input_user_agent: str = DEFAULT_INPUT_USER_AGENT
    cors_origins: tuple[str, ...] = (
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:4173",
        "http://127.0.0.1:5500",
    )

    @classmethod
    def from_environment(cls) -> APISettings:
        version = os.getenv("TRUTHLENS_API_VERSION", "1.0.0").strip()
        model_dir = Path(os.getenv("TRUTHLENS_MODEL_DIR", str(DEFAULT_MODEL_DIR)))
        evidence_timeout = float(os.getenv("TRUTHLENS_EVIDENCE_TIMEOUT", "5"))
        evidence_max_results = int(os.getenv("TRUTHLENS_EVIDENCE_MAX_RESULTS", "5"))
        evidence_user_agent = os.getenv(
            "TRUTHLENS_EVIDENCE_USER_AGENT",
            DEFAULT_USER_AGENT,
        )
        evidence_retry_limit = int(os.getenv("TRUTHLENS_EVIDENCE_RETRY_LIMIT", "1"))
        input_timeout = float(os.getenv("TRUTHLENS_INPUT_TIMEOUT", "8"))
        input_max_length = int(os.getenv("TRUTHLENS_INPUT_MAX_LENGTH", "100000"))
        input_max_response_bytes = int(
            os.getenv("TRUTHLENS_INPUT_MAX_RESPONSE_BYTES", "2000000")
        )
        input_max_upload_bytes = int(
            os.getenv("TRUTHLENS_INPUT_MAX_UPLOAD_BYTES", "8000000")
        )
        input_max_image_pixels = int(
            os.getenv("TRUTHLENS_INPUT_MAX_IMAGE_PIXELS", "20000000")
        )
        input_max_redirects = int(os.getenv("TRUTHLENS_INPUT_MAX_REDIRECTS", "5"))
        input_user_agent = os.getenv(
            "TRUTHLENS_INPUT_USER_AGENT",
            DEFAULT_INPUT_USER_AGENT,
        )
        origins_value = os.getenv(
            "TRUTHLENS_CORS_ORIGINS",
            "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173,http://127.0.0.1:4173,http://127.0.0.1:5500",
        )
        cors_origins = tuple(
            origin.strip() for origin in origins_value.split(",") if origin.strip()
        )
        return cls(
            version=version or "1.0.0",
            model_dir=model_dir,
            evidence_timeout=evidence_timeout,
            evidence_max_results=evidence_max_results,
            evidence_user_agent=evidence_user_agent,
            evidence_retry_limit=evidence_retry_limit,
            input_timeout=input_timeout,
            input_max_length=input_max_length,
            input_max_response_bytes=input_max_response_bytes,
            input_max_upload_bytes=input_max_upload_bytes,
            input_max_image_pixels=input_max_image_pixels,
            input_max_redirects=input_max_redirects,
            input_user_agent=input_user_agent,
            cors_origins=cors_origins,
        )


class TextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Annotated[str, Field(min_length=1)]

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text must not be empty or whitespace.")
        return value


class ClassificationResponse(BaseModel):
    prediction: str
    label: int
    classifier: str
    explanation: str


class VerificationResponse(ClassificationResponse):
    text: str
    verification_status: str
    final_verdict: None
    verification_notice: str


class ExtractedClaim(BaseModel):
    claim_id: int
    claim_text: str
    claim_type: str
    verification_status: str
    start_offset: int = 0
    end_offset: int = 0
    parent_claim_id: int | None = None
    is_compound: bool = False
    compound_parts: list["ExtractedClaim"] = []


class ClaimExtractionResponse(BaseModel):
    success: bool
    total_claims: int
    claims: list[ExtractedClaim]


class EvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: Annotated[str, Field(min_length=1, max_length=5_000)]
    claim_id: Annotated[int, Field(gt=0, strict=True)]

    @field_validator("claim")
    @classmethod
    def claim_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Claim must not be empty or whitespace.")
        return normalized


class EvidenceRecordLegacy(BaseModel):
    evidence_id: str
    claim_id: int
    source_name: str
    source_domain: str
    source_url: str
    title: str | None
    snippet: str | None
    page_content: str | None = None
    page_content_status: str | None = None
    published_date: str | None
    retrieved_at: str
    source_type: str
    relevance_score: float
    retrieval_status: str


class EvidenceResponse(BaseModel):
    success: bool
    claim_id: int
    query: str
    total_results: int
    evidence: list[EvidenceRecordLegacy]
    retrieval_status: str
    source_errors: list[dict[str, str]]


class EvidenceAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: Annotated[str, Field(min_length=1, max_length=5_000)]
    claim_id: Annotated[int, Field(gt=0, strict=True)]
    evidence: Annotated[
        list[dict[str, object]],
        Field(max_length=MAX_EVIDENCE_ITEMS),
    ] = Field(default_factory=list)
    retrieval_status: str = "completed"

    @field_validator("claim")
    @classmethod
    def claim_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Claim must not be empty or whitespace.")
        return normalized


class EvidenceAnalysisResponse(BaseModel):
    claim_id: int
    original_claim: str
    verdict: str
    confidence: float | None
    confidence_type: str | None
    explanation: str
    supporting_evidence: list[dict[str, object]]
    contradicting_evidence: list[dict[str, object]]
    mixed_evidence: list[dict[str, object]]
    neutral_evidence: list[dict[str, object]]
    insufficient_evidence: list[dict[str, object]]
    sources_used: list[dict[str, object]]
    limitations: list[str]
    verification_status: str


class InputRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input: Annotated[str, Field(min_length=1, max_length=1_000_000)]
    input_type: Literal["auto", "text", "url", "forwarded"] = "auto"
    run_pipeline: bool = False

    @field_validator("input")
    @classmethod
    def input_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Input must not be empty or whitespace.")
        return value


class InputProcessingResponse(BaseModel):
    input_type: str
    original_input: str
    extracted_text: str
    source_url: str | None
    processing_status: str
    warnings: list[str]
    error: str | None
    title: str | None = None
    pipeline: dict[str, object] | None = None


class LanguageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Annotated[str, Field(min_length=1, max_length=100_000)]

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text must not be empty or whitespace.")
        return value


class TranslationRequest(LanguageRequest):
    source_language: str | None = None
    target_language: str = "en"


class TranslationResponse(BaseModel):
    original_text: str
    translated_text: str | None
    source_language: str
    target_language: str
    translation_status: str
    warnings: list[str]
    error: str | None
    language_detection: dict[str, object] | None = None


class MultilingualVerificationResponse(BaseModel):
    original_text: str
    language_detection: dict[str, object]
    translated_text: str | None
    translation_status: str
    warnings: list[str]
    error: str | None
    verification_status: str
    pipeline: dict[str, object] | None


class MultilingualVerificationRequest(LanguageRequest):
    source_url: Annotated[str | None, Field(max_length=2_048)] = None

    @field_validator("source_url")
    @classmethod
    def blank_source_url_is_absent(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


def create_app(
    settings: APISettings | None = None,
    classifier: NewsClassifier | None = None,
    evidence_retriever: EvidenceRetriever | None = None,
    input_processor: InputProcessor | None = None,
    language_detector: LanguageDetector | None = None,
    translation_service: TranslationService | None = None,
) -> FastAPI:
    config = settings or APISettings.from_environment()
    app_settings = get_settings()

    application = FastAPI(
        title="TruthLens AI API",
        version=config.version,
        description="Pattern-based news classification; not factual verification.",
    )
    application.state.api_settings = config
    application.state.classifier = classifier
    application.state.classifier_error = None
    application.state.evidence_retriever = evidence_retriever or EvidenceRetriever(
        timeout=config.evidence_timeout,
        max_results=config.evidence_max_results,
        user_agent=config.evidence_user_agent,
        retry_limit=config.evidence_retry_limit,
        gdelt_time_window_days=app_settings.gdelt_time_window_days,
        google_factcheck_api_key=app_settings.google_factcheck_api_key,
        google_factcheck_language_codes=tuple(app_settings.google_factcheck_language_list),
    )
    application.state.evidence_analyzer = EvidenceAnalyzer()
    application.state.input_processor = input_processor or InputProcessor(
        timeout=config.input_timeout,
        max_input_length=config.input_max_length,
        max_response_bytes=config.input_max_response_bytes,
        max_upload_bytes=config.input_max_upload_bytes,
        max_image_pixels=config.input_max_image_pixels,
        max_redirects=config.input_max_redirects,
        user_agent=config.input_user_agent,
        ocr_preprocess=app_settings.tesseract_preprocess,
    )
    application.state.language_detector = language_detector or LanguageDetector()
    application.state.translation_service = (
        translation_service or TranslationService()
    )
    application.state.database = get_database()

    if classifier is None:
        try:
            application.state.classifier = NewsClassifier(
                config.model_dir / "tfidf_vectorizer.joblib",
                config.model_dir / "linear_svm_model.joblib",
            )
        except FileNotFoundError as exc:
            application.state.classifier_error = str(exc)
            LOGGER.warning("TruthLens classifier is unavailable: %s", exc)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    def get_loaded_classifier(request: Request) -> NewsClassifier:
        loaded_classifier = request.app.state.classifier
        if loaded_classifier is None:
            raise HTTPException(
                status_code=503,
                detail="Classifier model is unavailable. Check model configuration.",
            )
        return loaded_classifier

    # ============================================================
    # Unified Verification Pipeline
    # ============================================================

    def run_unified_pipeline(
        text: str,
        request: Request,
        source_url: str | None = None,
        options: VerificationOptions | None = None,
    ) -> dict[str, Any]:
        """Run the complete verification pipeline for unified endpoint."""
        opts = options or VerificationOptions()

        # Extract claims with offsets
        claims_result = extract_claims(text, split_compound=True)

        claim_assessments: list[dict[str, Any]] = []
        for claim_data in claims_result["claims"]:
            claim_text = claim_data["claim_text"]
            claim_id = str(claim_data["claim_id"])

            # Build evidence retriever with options
            retriever = EvidenceRetriever(
                timeout=config.evidence_timeout,
                max_results=opts.max_results,
                user_agent=config.evidence_user_agent,
                retry_limit=config.evidence_retry_limit,
                gdelt_time_window_days=opts.time_window_days,
                google_factcheck_api_key=app_settings.google_factcheck_api_key,
                google_factcheck_language_codes=tuple(app_settings.google_factcheck_language_list),
            )

            try:
                retrieval = retriever.retrieve(claim_text, 1)
                if not isinstance(retrieval, dict):
                    raise TypeError("Evidence retriever returned an invalid response.")
                retrieved_evidence = retrieval.get("evidence", [])
                if not isinstance(retrieved_evidence, list):
                    raise TypeError("Evidence retriever returned invalid evidence.")
                retrieval_status = str(retrieval.get("retrieval_status", "unavailable"))
                if retrieval_status not in {
                    "completed", "partial", "no_results", "unavailable"
                }:
                    raise ValueError("Evidence retriever returned an invalid status.")
            except Exception as exc:
                LOGGER.exception("Evidence retrieval failed for claim %s", claim_id)
                retrieval_error = "source_unavailable"
                if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
                    retrieval_error = "timeout"
                elif isinstance(exc, httpx.HTTPStatusError):
                    retrieval_error = (
                        "rate_limited" if exc.response.status_code == 429 else "http_error"
                    )
                elif is_tls_error(exc):
                    retrieval_error = "tls_error"
                elif isinstance(exc, httpx.RequestError):
                    retrieval_error = "network_error"
                elif isinstance(exc, (TypeError, ValueError)):
                    retrieval_error = "malformed_response"

                retrieval = {
                    "query": build_search_query(claim_text),
                    "evidence": [],
                    "retrieval_status": "unavailable",
                    "source_errors": [
                        {"source": "web evidence retrieval", "error": retrieval_error}
                    ],
                }
                retrieved_evidence = []

            # Add direct source if provided
            if source_url is not None:
                processed_source = request.app.state.input_processor.process(
                    source_url, "url"
                )
                if processed_source.get("processing_status") == "processed":
                    extracted_text = processed_source.get("extracted_text")
                    final_url = processed_source.get("source_url")
                    title = processed_source.get("title")
                    if (
                        isinstance(extracted_text, str)
                        and extracted_text.strip()
                        and isinstance(final_url, str)
                    ):
                        domain = (urlsplit(final_url).hostname or "").casefold().rstrip(".")
                        source_name, source_type = classify_source(domain)
                        direct_source = {
                            "evidence_id": "DIRECT-ARTICLE",
                            "claim_id": claim_id,
                            "source_name": (
                                source_name if source_type != "unknown" else domain
                            ),
                            "source_domain": domain,
                            "source_url": final_url,
                            "title": title if isinstance(title, str) else None,
                            "snippet": None,
                            "page_content": extracted_text[:MAX_PAGE_CONTENT_LENGTH],
                            "page_content_status": "retrieved",
                            "published_date": None,
                            "retrieved_at": "",
                            "source_type": source_type,
                            "relevance_score": None,
                            "retrieval_status": "retrieved",
                        }
                        retrieved_evidence.append(direct_source)

            # Analyze evidence
            analysis = request.app.state.evidence_analyzer.analyze(
                claim=claim_text,
                claim_id=int(claim_id),
                evidence=retrieved_evidence,
                retrieval_status=retrieval_status,
            )

            # Convert evidence to new format
            evidence_records: list[EvidenceRecord] = []
            for ev in retrieved_evidence:
                if not isinstance(ev, dict):
                    continue
                ev_domain = ev.get("source_domain", "")
                ev_type = ev.get("source_type", "unknown")
                ev_connector = ev.get("connector", "gdelt")

                evidence_records.append(EvidenceRecord(
                    evidence_id=ev.get("evidence_id", str(uuid.uuid4())),
                    claim_id=claim_id,
                    source_type=ev_type if ev_type in ["official", "fact_checker", "news", "social"] else "unknown",
                    title=ev.get("title") or "",
                    publisher=ev.get("source_name") or ev_domain,
                    domain=ev_domain,
                    url=ev.get("source_url") or "",
                    published_at=ev.get("published_date"),
                    retrieved_at=ev.get("retrieved_at", ""),
                    snippet=ev.get("snippet") or "",
                    content_status=ev.get("page_content_status", "not_attempted"),
                    query=ev.get("query", build_search_query(claim_text)),
                    connector=ev_connector if ev_connector in ["gdelt", "google_factcheck", "social"] else "gdelt",
                    connector_status="success",
                    relevance_score=ev.get("relevance_score", 0.0),
                    stance=ev.get("assessment", STANCE_INSUFFICIENT),
                ))

            # Map verdict to new format
            verdict = analysis.get("verdict", VERDICT_INSUFFICIENT_EVIDENCE)
            if verdict not in {
                VERDICT_TRUE, VERDICT_FALSE, VERDICT_PARTIALLY_TRUE,
                VERDICT_MISLEADING, VERDICT_INSUFFICIENT_EVIDENCE, VERDICT_NEEDS_HUMAN_REVIEW
            }:
                verdict = VERDICT_INSUFFICIENT_EVIDENCE

            assessment = ClaimAssessment(
                verdict=verdict,
                confidence=analysis.get("confidence"),
                confidence_type=analysis.get("confidence_type"),
                explanation=analysis.get("explanation", ""),
                limitations=analysis.get("limitations", []),
            )

            claim_result = ClaimResult(
                claim_id=claim_id,
                claim_text=claim_text,
                claim_type=claim_data.get("claim_type", "factual"),
                verification_status="completed",
                start_offset=claim_data.get("start_offset") if opts.include_claim_offsets else None,
                end_offset=claim_data.get("end_offset") if opts.include_claim_offsets else None,
                assessment=assessment,
                evidence=evidence_records,
            )
            claim_assessments.append(claim_result)

        # Determine overall verdict
        if not claim_assessments:
            overall_verdict = VERDICT_INSUFFICIENT_EVIDENCE
            overall_confidence = None
            overall_explanation = "No factual claims could be extracted for evidence-based verification."
        else:
            verdicts = [c.assessment.verdict for c in claim_assessments if c.assessment]
            if not verdicts:
                overall_verdict = VERDICT_INSUFFICIENT_EVIDENCE
                overall_confidence = None
                overall_explanation = "No claims were assessed."
            elif VERDICT_NEEDS_HUMAN_REVIEW in verdicts:
                overall_verdict = VERDICT_NEEDS_HUMAN_REVIEW
                overall_confidence = None
                overall_explanation = "Conflicting evidence from credible sources requires human review."
            elif VERDICT_MISLEADING in verdicts:
                overall_verdict = VERDICT_MISLEADING
                overall_confidence = 0.7
                overall_explanation = "Evidence analysis identified misleading context in at least one extracted claim."
            elif VERDICT_PARTIALLY_TRUE in verdicts or (VERDICT_TRUE in verdicts and VERDICT_FALSE in verdicts):
                overall_verdict = VERDICT_PARTIALLY_TRUE
                overall_confidence = 0.65
                overall_explanation = "Evidence supports some parts but contradicts or partially supports others."
            elif all(v == VERDICT_TRUE for v in verdicts):
                overall_verdict = VERDICT_TRUE
                confidences = [c.assessment.confidence for c in claim_assessments if c.assessment and c.assessment.confidence]
                overall_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.75
                overall_explanation = "Retrieved evidence supports all extracted claims."
            elif all(v == VERDICT_FALSE for v in verdicts):
                overall_verdict = VERDICT_FALSE
                confidences = [c.assessment.confidence for c in claim_assessments if c.assessment and c.assessment.confidence]
                overall_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.75
                overall_explanation = "Retrieved evidence contradicts all extracted claims."
            else:
                overall_verdict = VERDICT_INSUFFICIENT_EVIDENCE
                overall_confidence = None
                overall_explanation = "The evidence assessments do not establish a consistent overall verdict."

        return {
            "claims": claim_assessments,
            "overall_verdict": overall_verdict,
            "overall_confidence": overall_confidence,
            "overall_explanation": overall_explanation,
        }

    # ============================================================
    # Legacy Pipeline (for backward compatibility)
    # ============================================================

    def run_existing_pipeline(
        text: str,
        request: Request,
        source_url: str | None = None,
    ) -> dict[str, object]:
        loaded_classifier = request.app.state.classifier
        prediction = loaded_classifier.predict(text) if loaded_classifier else None
        claims = extract_claims(text)
        direct_source: dict[str, object] | None = None
        direct_source_error: str | None = None
        if source_url is not None:
            processed_source = request.app.state.input_processor.process(
                source_url,
                "url",
            )
            if processed_source.get("processing_status") == "processed":
                extracted_text = processed_source.get("extracted_text")
                final_url = processed_source.get("source_url")
                title = processed_source.get("title")
                if (
                    isinstance(extracted_text, str)
                    and extracted_text.strip()
                    and isinstance(final_url, str)
                ):
                    domain = (urlsplit(final_url).hostname or "").casefold().rstrip(".")
                    source_name, source_type = classify_source(domain)
                    direct_source = {
                        "evidence_id": "DIRECT-ARTICLE",
                        "claim_id": 1,
                        "source_name": (
                            source_name if source_type != "unknown" else domain
                        ),
                        "source_domain": domain,
                        "source_url": final_url,
                        "title": title if isinstance(title, str) else None,
                        "snippet": None,
                        "page_content": extracted_text[:MAX_PAGE_CONTENT_LENGTH],
                        "page_content_status": "retrieved",
                        "published_date": None,
                        "retrieved_at": "",
                        "source_type": source_type,
                        "relevance_score": None,
                        "retrieval_status": "retrieved",
                    }
                else:
                    direct_source_error = "article_content_unavailable"
            else:
                direct_source_error = "article_content_unavailable"

        claim_assessments: list[dict[str, object]] = []
        for claim in claims["claims"]:
            try:
                retrieval = request.app.state.evidence_retriever.retrieve(
                    claim["claim_text"],
                    claim["claim_id"],
                )
                if not isinstance(retrieval, dict):
                    raise TypeError("Evidence retriever returned an invalid response.")
                retrieved_evidence = retrieval.get("evidence", [])
                if not isinstance(retrieved_evidence, list) or any(
                    not isinstance(item, dict) for item in retrieved_evidence
                ):
                    raise TypeError("Evidence retriever returned invalid evidence.")
                if retrieval.get("retrieval_status", "unavailable") not in {
                    "completed",
                    "partial",
                    "no_results",
                    "unavailable",
                }:
                    raise ValueError("Evidence retriever returned an invalid status.")
            except Exception as exc:
                LOGGER.exception(
                    "Evidence retrieval failed for claim %s",
                    claim["claim_id"],
                )
                if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
                    retrieval_error = "timeout"
                elif isinstance(exc, httpx.HTTPStatusError):
                    retrieval_error = (
                        "rate_limited"
                        if exc.response.status_code == 429
                        else "http_error"
                    )
                elif is_tls_error(exc):
                    retrieval_error = "tls_error"
                elif isinstance(exc, httpx.RequestError):
                    retrieval_error = "network_error"
                elif isinstance(exc, (TypeError, ValueError)):
                    retrieval_error = "malformed_response"
                else:
                    retrieval_error = "source_unavailable"
                retrieval = {
                    "query": build_search_query(claim["claim_text"]),
                    "evidence": [],
                    "retrieval_status": "unavailable",
                    "source_errors": [
                        {"source": "web evidence retrieval", "error": retrieval_error}
                    ],
                }
                retrieved_evidence = []
            evidence = list(retrieved_evidence)
            if direct_source is not None:
                direct_page_content = direct_source.get("page_content")
                evidence.append(
                    {
                        **direct_source,
                        "claim_id": claim["claim_id"],
                        "snippet": extract_relevant_snippet(
                            claim["claim_text"],
                            direct_page_content
                            if isinstance(direct_page_content, str)
                            else "",
                        ),
                    }
                )
            raw_source_errors = retrieval.get("source_errors", [])
            source_errors = []
            if isinstance(raw_source_errors, list):
                for source_error in raw_source_errors:
                    if (
                        isinstance(source_error, dict)
                        and isinstance(source_error.get("source"), str)
                        and isinstance(source_error.get("error"), str)
                    ):
                        source_errors.append(source_error)
                    else:
                        source_errors.append(
                            {
                                "source": "web evidence retrieval",
                                "error": "malformed_response",
                            }
                        )
            retrieval_status = str(retrieval.get("retrieval_status", "unavailable"))
            if direct_source_error is not None:
                source_errors.append(
                    {
                        "source": "user-provided article",
                        "error": direct_source_error,
                    }
                )
                if retrieval_status in {"completed", "no_results"}:
                    retrieval_status = "partial"
            elif direct_source is not None and retrieval_status in {
                "unavailable",
                "no_results",
            }:
                retrieval_status = "partial"

            analysis = request.app.state.evidence_analyzer.analyze(
                claim=claim["claim_text"],
                claim_id=claim["claim_id"],
                evidence=evidence,
                retrieval_status=retrieval_status,
            )
            claim_assessments.append(
                {
                    "claim_id": claim["claim_id"],
                    "claim_text": claim["claim_text"],
                    "query": str(retrieval.get("query", "")),
                    "retrieval_status": retrieval_status,
                    "source_errors": source_errors,
                    "evidence": evidence,
                    "analysis": analysis,
                }
            )
        return {
            **_final_verdict_summary(claims["claims"], claim_assessments),
            "classifier": (
                {
                    "prediction": prediction["prediction"],
                    "label": prediction["label"],
                    "classifier": CLASSIFIER_NAME,
                    "explanation": CLASSIFICATION_EXPLANATION,
                    "interpretation": "Pattern-based signal only; not a factual verdict.",
                }
                if prediction is not None
                else None
            ),
            "claims": claims["claims"],
            "claim_assessments": claim_assessments,
        }

    def _final_verdict_summary(
        claims: list[dict[str, Any]],
        assessments: list[dict[str, Any]],
    ) -> dict[str, object]:
        if not claims:
            return {
                "final_verdict": "INSUFFICIENT EVIDENCE",
                "confidence": None,
                "explanation": "No factual claims could be extracted for evidence-based verification.",
            }
        if len(assessments) != len(claims):
            return {
                "final_verdict": "INSUFFICIENT EVIDENCE",
                "confidence": None,
                "explanation": "One or more extracted claims did not receive an evidence assessment.",
            }

        analyses = [
            item.get("analysis")
            for item in assessments
            if isinstance(item.get("analysis"), dict)
        ]
        verdicts = [
            str(analysis.get("verdict", "INSUFFICIENT EVIDENCE"))
            for analysis in analyses
        ]
        # Check for NEEDS HUMAN REVIEW first - this takes precedence
        if "NEEDS HUMAN REVIEW" in verdicts:
            explanation = (
                "Evidence assessments require human review due to conflicting signals from credible sources."
            )
            return {
                "final_verdict": "NEEDS HUMAN REVIEW",
                "confidence": None,
                "explanation": explanation,
            }
        # Check for INSUFFICIENT EVIDENCE
        if len(analyses) != len(claims) or any(
            verdict == "INSUFFICIENT EVIDENCE" for verdict in verdicts
        ):
            statuses = [str(item.get("retrieval_status", "")) for item in assessments]
            if statuses and all(status == "unavailable" for status in statuses):
                explanation = (
                    "Web evidence could not be retrieved for any extracted claim, so no factual verdict can be established."
                )
            elif any(
                analysis.get("mixed_evidence")
                for analysis in analyses
                if isinstance(analysis, dict)
            ):
                explanation = (
                    "Retrieved evidence contains conflicting signals; the claims cannot be resolved confidently."
                )
            else:
                explanation = (
                    "Available evidence was weak, conflicting, or left at least one extracted claim unresolved."
                )
            return {
                "final_verdict": "INSUFFICIENT EVIDENCE",
                "confidence": None,
                "explanation": explanation,
            }

        if "MISLEADING" in verdicts:
            final_verdict = "MISLEADING"
            explanation = (
                "Evidence analysis identified misleading context in at least one extracted claim."
            )
        elif "PARTIALLY TRUE" in verdicts or (
            "TRUE" in verdicts and "FALSE" in verdicts
        ):
            final_verdict = "PARTIALLY TRUE"
            explanation = (
                "Evidence supports some parts of the submitted content but contradicts or only partially supports others."
            )
        elif all(verdict == "TRUE" for verdict in verdicts):
            final_verdict = "REAL"
            explanation = (
                "Retrieved evidence supports all extracted claims; the classifier prediction was not used to determine this verdict."
            )
        elif all(verdict == "FALSE" for verdict in verdicts):
            final_verdict = "FAKE"
            explanation = (
                "Retrieved evidence contradicts all extracted claims; the classifier prediction was not used to determine this verdict."
            )
        else:
            return {
                "final_verdict": "INSUFFICIENT EVIDENCE",
                "confidence": None,
                "explanation": "The evidence assessments do not establish a consistent overall verdict.",
            }

        confidence_values = [analysis.get("confidence") for analysis in analyses]
        numeric_confidence = [
            float(value)
            for value in confidence_values
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]
        confidence = (
            round(sum(numeric_confidence) / len(numeric_confidence), 2)
            if len(numeric_confidence) == len(confidence_values)
            else None
        )
        return {
            "final_verdict": final_verdict,
            "confidence": confidence,
            "explanation": explanation,
        }

    def set_input_response_status(
        response: Response,
        result: dict[str, object],
    ) -> None:
        status = result["processing_status"]
        error = str(result.get("error") or "").casefold()
        if status == "rejected":
            response.status_code = (
                413
                if "exceeds the maximum" in error or "dimensions exceed" in error
                else 422
            )
        elif status == "unsupported":
            response.status_code = 415
        elif status == "unavailable":
            response.status_code = 503 if result["input_type"] == "image" else 502
        elif status == "failed":
            response.status_code = 502

    # ============================================================
    # API Endpoints
    # ============================================================

    @application.get("/api/health")
    def health(request: Request) -> dict[str, object]:
        available = request.app.state.classifier is not None
        return {
            "status": "ok" if available else "degraded",
            "api_version": config.version,
            "classifier_available": available,
        }

    # --- NEW: Unified Verification Endpoint ---
    @application.post("/api/verify", response_model=UnifiedVerifyResponse)
    async def unified_verify(
        payload: UnifiedVerifyRequest,
        request: Request,
        response: Response,
    ) -> UnifiedVerifyResponse:
        """Unified verification endpoint - single entry point for all input types."""
        verification_id = str(uuid.uuid4())
        opts = payload.options or VerificationOptions()

        try:
            # Process input based on type
            input_type = payload.input_type
            if input_type == "auto":
                if payload.input.strip().lower().startswith(("http://", "https://")):
                    input_type = "url"
                else:
                    input_type = "text"

            processed_result: dict[str, Any] = {}
            extracted_text = ""
            source_url = None
            title = None
            warnings = []

            if input_type == "url":
                processed_result = request.app.state.input_processor.process(
                    payload.input, "url"
                )
                source_url = payload.input
            elif input_type == "image":
                # For image, we'd need multipart upload - handle via separate endpoint
                # For now, treat as text with base64
                processed_result = request.app.state.input_processor.process(
                    payload.input, "text"
                )
            else:
                processed_result = request.app.state.input_processor.process(
                    payload.input, "text"
                )

            extracted_text = processed_result.get("extracted_text", "")
            if processed_result.get("title"):
                title = processed_result["title"]
                extracted_text = f"{title}\n\n{extracted_text}"

            # Language detection
            detection = request.app.state.language_detector.detect(payload.input)
            language_code = str(detection["language_code"])

            # Translation if needed
            translation_result = None
            translated_text = extracted_text

            if language_code != "en" and language_code in SUPPORTED_LANGUAGES:
                translation = request.app.state.translation_service.translate(
                    extracted_text, language_code, "en"
                )
                translation_status = str(translation.get("translation_status", "failed"))
                translated_value = translation.get("translated_text")
                translated_text = (
                    translated_value.strip()
                    if isinstance(translated_value, str) and translated_value.strip()
                    else None
                )
                if translation_status not in {"translated", "not_required"}:
                    translated_text = None
                translation_error = (
                    translation.get("error")
                    if isinstance(translation.get("error"), str)
                    else None
                )
                translation_warnings = [
                    w for w in translation.get("warnings", []) if isinstance(w, str)
                ]
                if translated_text is None:
                    if translation_status == "uncertain":
                        translation_warnings.append(
                            "Language detection was uncertain, so translation was not attempted."
                        )
                    else:
                        translation_warnings.append(
                            "Translation was unavailable; the original text was preserved and searched."
                        )
                    translation_warnings.append(
                        "Automated stance analysis may return INSUFFICIENT EVIDENCE for non-English claims."
                    )
                else:
                    translation_warnings.append(
                        "Only translated text is processed by the English NLP pipeline; translation is not evidence."
                    )

                translation_result = TranslationResult(
                    original_text=extracted_text,
                    translated_text=translated_text,
                    source_language=language_code,
                    target_language="en",
                    translation_status=translation_status,
                    warnings=translation_warnings,
                    error=translation_error,
                )
                if translated_text:
                    warnings.append(
                        "Only translated text is processed by the English NLP pipeline; translation is not evidence."
                    )
            else:
                translation_result = TranslationResult(
                    original_text=extracted_text,
                    translated_text=None if language_code == "en" else extracted_text,
                    source_language=language_code,
                    target_language="en",
                    translation_status="not_required" if language_code == "en" else "unsupported",
                    warnings=[],
                    error=None,
                )

            # Run unified pipeline on translated text
            pipeline_result = run_unified_pipeline(
                translated_text or extracted_text,
                request,
                source_url,
                opts,
            )

            # Build language detection result
            language_detection = LanguageDetectionResult(
                language_code=detection.get("language_code", "unknown"),
                language_name=detection.get("language_name", "Unknown"),
                confidence=float(detection.get("confidence", 0.0)),
                status=detection.get("status", "unknown"),
                warning=detection.get("warning"),
            )

            # Determine overall status
            overall_status = "completed"
            if any(c.verification_status == "failed" for c in pipeline_result["claims"]):
                overall_status = "failed"
            elif any(
                c.assessment and c.assessment.verdict == VERDICT_NEEDS_HUMAN_REVIEW
                for c in pipeline_result["claims"]
            ):
                overall_status = "partial"

            # Add classifier prediction if available
            classifier_result = None
            if request.app.state.classifier:
                prediction = request.app.state.classifier.predict(translated_text or extracted_text)
                classifier_result = {
                    "prediction": prediction["prediction"],
                    "label": prediction["label"],
                    "classifier": CLASSIFIER_NAME,
                    "decision_score": prediction.get("decision_score"),
                    "model_version": prediction.get("model_version"),
                    "explanation": CLASSIFICATION_EXPLANATION,
                    "interpretation": "Pattern-based signal only; not a factual verdict.",
                }
                warnings.append(
                    "The classifier prediction is a pattern-based signal and does not constitute factual verification."
                )

            # Store in database
            db = request.app.state.database
            db_data = {
                "id": verification_id,
                "input_type": input_type,
                "original_input": payload.input,
                "extracted_text": extracted_text,
                "source_url": source_url,
                "title": title,
                "extraction_status": processed_result.get("processing_status", "processed"),
                "extraction_warnings": processed_result.get("warnings", []),
                "extraction_error": processed_result.get("error"),
                "language_code": language_code,
                "language_name": detection.get("language_name"),
                "detection_confidence": detection.get("confidence"),
                "detection_status": detection.get("status"),
                "translation_status": translation_result.translation_status,
                "translated_text": translation_result.translated_text,
                "translation_warnings": translation_result.warnings,
                "translation_error": translation_result.error,
                "classifier_label": classifier_result["prediction"] if classifier_result else None,
                "classifier_decision_score": classifier_result.get("decision_score") if classifier_result else None,
                "classifier_model_version": classifier_result.get("model_version") if classifier_result else None,
                "overall_verdict": pipeline_result["overall_verdict"],
                "overall_confidence": pipeline_result["overall_confidence"],
                "overall_explanation": pipeline_result["overall_explanation"],
                "warnings": warnings,
                "status": overall_status,
                "claims": [
                    {
                        "id": c.claim_id,
                        "text": c.claim_text,
                        "claim_type": c.claim_type,
                        "verification_status": c.verification_status,
                        "assessment_verdict": c.assessment.verdict if c.assessment else None,
                        "assessment_confidence": c.assessment.confidence if c.assessment else None,
                        "assessment_explanation": c.assessment.explanation if c.assessment else None,
                        "assessment_confidence_type": c.assessment.confidence_type if c.assessment else None,
                        "assessment_limitations": c.assessment.limitations if c.assessment else [],
                        "evidence": [
                            {
                                "id": ev.evidence_id,
                                "source_type": ev.source_type,
                                "title": ev.title,
                                "publisher": ev.publisher,
                                "domain": ev.domain,
                                "url": ev.url,
                                "published_at": ev.published_at,
                                "retrieved_at": ev.retrieved_at,
                                "snippet": ev.snippet,
                                "content_status": ev.content_status,
                                "query": ev.query,
                                "connector": ev.connector,
                                "connector_status": ev.connector_status,
                                "relevance_score": ev.relevance_score,
                                "stance": ev.stance,
                            }
                            for ev in c.evidence
                        ],
                    }
                    for c in pipeline_result["claims"]
                ],
            }
            try:
                db.create_verification(db_data)
            except Exception:
                LOGGER.exception("Failed to store verification in database")

            return UnifiedVerifyResponse(
                verification_id=verification_id,
                input_type=input_type,
                original_input=payload.input,
                extracted_text=extracted_text,
                language_detection=language_detection,
                translation=translation_result,
                claims=pipeline_result["claims"],
                overall_verdict=pipeline_result["overall_verdict"],
                overall_confidence=pipeline_result["overall_confidence"],
                overall_explanation=pipeline_result["overall_explanation"],
                warnings=warnings,
                status=overall_status,
            )

        except HTTPException:
            raise
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            LOGGER.exception("Unexpected unified verification failure")
            raise HTTPException(
                status_code=500,
                detail="Verification failed unexpectedly.",
            ) from exc

    # --- Legacy Endpoints (backward compatibility) ---

    @application.post("/api/classify", response_model=ClassificationResponse)
    def classify(
        payload: TextRequest,
        request: Request,
    ) -> ClassificationResponse:
        loaded_classifier = get_loaded_classifier(request)
        result = loaded_classifier.predict(payload.text)
        return ClassificationResponse(
            prediction=result["prediction"],
            label=result["label"],
            classifier=CLASSIFIER_NAME,
            explanation=CLASSIFICATION_EXPLANATION,
        )

    @application.post("/api/verify/text", response_model=VerificationResponse)
    def verify_text(
        payload: TextRequest,
        request: Request,
    ) -> VerificationResponse:
        loaded_classifier = get_loaded_classifier(request)
        result = loaded_classifier.predict(payload.text)
        return VerificationResponse(
            text=payload.text,
            prediction=result["prediction"],
            label=result["label"],
            classifier=CLASSIFIER_NAME,
            explanation=CLASSIFICATION_EXPLANATION,
            verification_status="pending",
            final_verdict=None,
            verification_notice=VERIFICATION_NOTICE,
        )

    @application.post(
        "/api/extract-claims",
        response_model=ClaimExtractionResponse,
    )
    def extract_article_claims(payload: TextRequest) -> ClaimExtractionResponse:
        try:
            result = extract_claims(payload.text)
        except ArticleTooLongError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            LOGGER.exception("Unexpected claim extraction failure")
            raise HTTPException(
                status_code=500,
                detail="Claim extraction failed unexpectedly.",
            ) from exc
        return ClaimExtractionResponse(**result)

    @application.post(
        "/api/retrieve-evidence",
        response_model=EvidenceResponse,
    )
    def retrieve_evidence(payload: EvidenceRequest) -> EvidenceResponse:
        try:
            result = application.state.evidence_retriever.retrieve(
                payload.claim,
                payload.claim_id,
            )
        except EvidenceInputError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            LOGGER.exception("Unexpected evidence retrieval failure")
            raise HTTPException(
                status_code=500,
                detail="Evidence retrieval failed unexpectedly.",
            ) from exc
        return EvidenceResponse(**result)

    @application.post(
        "/api/analyze-evidence",
        response_model=EvidenceAnalysisResponse,
    )
    def analyze_evidence(
        payload: EvidenceAnalysisRequest,
    ) -> EvidenceAnalysisResponse:
        try:
            result = application.state.evidence_analyzer.analyze(
                claim=payload.claim,
                claim_id=payload.claim_id,
                evidence=payload.evidence,
                retrieval_status=payload.retrieval_status,
            )
        except (EvidenceAnalysisInputError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            LOGGER.exception("Unexpected evidence analysis failure")
            raise HTTPException(
                status_code=500,
                detail="Evidence analysis failed unexpectedly.",
            ) from exc
        return EvidenceAnalysisResponse(**result)

    @application.post("/api/detect-language")
    def detect_language(payload: LanguageRequest) -> dict[str, object]:
        try:
            return application.state.language_detector.detect(payload.text)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            LOGGER.exception("Unexpected language detection failure")
            raise HTTPException(
                status_code=500,
                detail="Language detection failed unexpectedly.",
            ) from exc

    @application.post(
        "/api/translate",
        response_model=TranslationResponse,
    )
    def translate_text(
        payload: TranslationRequest,
        response: Response,
    ) -> TranslationResponse:
        detection: dict[str, object] | None = None
        source_language = payload.source_language
        if source_language is None:
            detection = application.state.language_detector.detect(payload.text)
            source_language = str(detection["language_code"])
            if source_language not in SUPPORTED_LANGUAGES:
                result = {
                    "original_text": payload.text,
                    "translated_text": None,
                    "source_language": source_language,
                    "target_language": payload.target_language,
                    "translation_status": "uncertain",
                    "warnings": [
                        str(
                            detection.get(
                                "warning",
                                "Language could not be detected confidently.",
                            )
                        )
                    ],
                    "error": "Translation was not attempted because the source language is uncertain.",
                    "language_detection": detection,
                }
                response.status_code = 422
                return TranslationResponse(**result)
        try:
            result = application.state.translation_service.translate(
                payload.text,
                source_language,
                payload.target_language,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            LOGGER.exception("Unexpected translation failure")
            raise HTTPException(
                status_code=500,
                detail="Translation failed unexpectedly.",
            ) from exc
        if detection is not None:
            result["language_detection"] = detection
        if result["translation_status"] in {"unsupported", "rejected"}:
            response.status_code = 422
        elif result["translation_status"] == "unavailable":
            response.status_code = 503
        elif result["translation_status"] == "failed":
            response.status_code = 502
        return TranslationResponse(**result)

    @application.post(
        "/api/verify/multilingual",
        response_model=MultilingualVerificationResponse,
    )
    def verify_multilingual(
        payload: MultilingualVerificationRequest,
        request: Request,
        response: Response,
    ) -> MultilingualVerificationResponse:
        try:
            detection = request.app.state.language_detector.detect(payload.text)
            language_code = str(detection["language_code"])
            if language_code not in SUPPORTED_LANGUAGES:
                translation: dict[str, Any] = {
                    "translation_status": "uncertain",
                    "translated_text": None,
                    "warnings": [
                        str(
                            detection.get(
                                "warning",
                                "Input language could not be identified confidently.",
                            )
                        )
                    ],
                    "error": (
                        "Language detection was uncertain; the original text will be searched without translation."
                    ),
                }
            else:
                translation = request.app.state.translation_service.translate(
                    payload.text,
                    language_code,
                    "en",
                )

            translation_status = str(
                translation.get("translation_status", "failed")
            )
            translated_value = translation.get("translated_text")
            translated_text = (
                translated_value.strip()
                if isinstance(translated_value, str) and translated_value.strip()
                else None
            )
            if translation_status not in {"translated", "not_required"}:
                translated_text = None
            translation_error = (
                translation.get("error")
                if isinstance(translation.get("error"), str)
                else None
            )
            warnings = [
                warning
                for warning in translation.get("warnings", [])
                if isinstance(warning, str)
            ]
            if translated_text is None:
                if translation_status == "uncertain":
                    warnings.append(
                        "Language detection was uncertain, so translation was not attempted; the original text was preserved and searched."
                    )
                else:
                    warnings.append(
                        "Translation was unavailable; the original text was preserved and searched."
                    )
                warnings.append(
                    "Automated stance analysis may return INSUFFICIENT EVIDENCE for non-English claims."
                )
                if translation_error is None:
                    translation_error = (
                        "Verification continued with the original text because no usable English translation was available."
                    )
            else:
                warnings.append(
                    "Only translated text is processed by the English NLP pipeline; translation is not evidence."
                )
            pipeline = run_existing_pipeline(
                translated_text or payload.text,
                request,
                payload.source_url,
            )
            return MultilingualVerificationResponse(
                original_text=payload.text,
                language_detection=detection,
                translated_text=translated_text,
                translation_status=translation_status,
                warnings=warnings,
                error=translation_error,
                verification_status="completed",
                pipeline=pipeline,
            )
        except HTTPException:
            raise
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            LOGGER.exception("Unexpected multilingual verification failure")
            raise HTTPException(
                status_code=500,
                detail="Multilingual verification failed unexpectedly.",
            ) from exc

    @application.post(
        "/api/process-input",
        response_model=InputProcessingResponse,
    )
    def process_input(
        payload: InputRequest,
        request: Request,
        response: Response,
    ) -> InputProcessingResponse:
        try:
            result = request.app.state.input_processor.process(
                payload.input,
                payload.input_type,
            )
            if payload.run_pipeline and result["processing_status"] == "processed":
                result["pipeline"] = run_existing_pipeline(
                    result["extracted_text"],
                    request,
                    result.get("source_url")
                    if isinstance(result.get("source_url"), str)
                    else None,
                )
            set_input_response_status(response, result)
            return InputProcessingResponse(**result)
        except HTTPException:
            raise
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            LOGGER.exception("Unexpected input processing failure")
            raise HTTPException(
                status_code=500,
                detail="Input processing failed unexpectedly.",
            ) from exc

    @application.post(
        "/api/process-image",
        response_model=InputProcessingResponse,
    )
    async def process_image(
        request: Request,
        response: Response,
        file: UploadFile = File(...),
        run_pipeline: bool = Form(False),
    ) -> InputProcessingResponse:
        try:
            image_bytes = await file.read(
                request.app.state.input_processor.max_upload_bytes + 1
            )
            filename = PurePath(file.filename or "uploaded-image").name
            result = await asyncio.to_thread(
                request.app.state.input_processor.process_image,
                image_bytes,
                filename,
            )
            if run_pipeline and result["processing_status"] == "processed":
                result["pipeline"] = await asyncio.to_thread(
                    run_existing_pipeline,
                    result["extracted_text"],
                    request,
                )
            set_input_response_status(response, result)
            return InputProcessingResponse(**result)
        except HTTPException:
            raise
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            LOGGER.exception("Unexpected image processing failure")
            raise HTTPException(
                status_code=500,
                detail="Image processing failed unexpectedly.",
            ) from exc
        finally:
            await file.close()

    # --- History Endpoints ---
    @application.get("/api/verifications")
    def list_verifications(
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        db = application.state.database
        return db.list_verifications(limit=limit, offset=offset)

    @application.get("/api/verifications/{verification_id}")
    def get_verification(verification_id: str) -> dict[str, Any] | None:
        db = application.state.database
        return db.get_verification(verification_id)

    @application.delete("/api/verifications/{verification_id}")
    def delete_verification(verification_id: str) -> dict[str, bool]:
        db = application.state.database
        deleted = db.delete_verification(verification_id)
        return {"deleted": deleted}

    return application


app = create_app()