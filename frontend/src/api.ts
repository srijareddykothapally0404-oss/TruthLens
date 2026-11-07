import type {
  HealthResponse,
  UnifiedVerifyResponse,
  VerificationHistoryItem,
  VerificationDetail,
  ProcessingResult,
  MultilingualResult,
} from "@/types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000")
  .replace(/\/+$/, "");

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isOptionalString(value: unknown): boolean {
  return value === undefined || value === null || typeof value === "string";
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function getErrorMessage(payload: unknown, status: number): string {
  if (!isRecord(payload)) return `The API request failed with status ${status}.`;
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload.detail)) {
    const messages = payload.detail.flatMap((item) => {
      if (!isRecord(item) || typeof item.msg !== "string") return [];
      const location = Array.isArray(item.loc)
        ? item.loc.filter((part): part is string | number =>
            typeof part === "string" || typeof part === "number")
          .slice(1)
          .join(".")
        : "";
      return [location ? `${location}: ${item.msg}` : item.msg];
    });
    if (messages.length) return messages.join(" ");
  }
  if (typeof payload.error === "string") return payload.error;
  return `The API request failed with status ${status}.`;
}

function isEvidenceItem(value: unknown): boolean {
  if (!isRecord(value)) return false;
  return [
    "evidence_id",
    "source_name",
    "source_domain",
    "source_url",
    "title",
    "snippet",
    "page_content",
    "page_content_status",
    "published_date",
    "assessment",
    "source_type",
    "connector",
    "connector_status",
    "stance",
  ].every((key) => isOptionalString(value[key]))
    && (value.relevance_score === undefined
      || value.relevance_score === null
      || (typeof value.relevance_score === "number" && Number.isFinite(value.relevance_score)));
}

function isEvidenceArray(value: unknown): boolean {
  return Array.isArray(value) && value.every(isEvidenceItem);
}

function isSourceErrorArray(
  value: unknown,
): value is Array<{ source: string; error: string }> {
  return Array.isArray(value) && value.every((item) =>
    isRecord(item)
    && typeof item.source === "string"
    && typeof item.error === "string");
}

export function isProcessingResult(value: unknown): value is ProcessingResult {
  return isRecord(value)
    && typeof value.input_type === "string"
    && typeof value.original_input === "string"
    && typeof value.extracted_text === "string"
    && isOptionalString(value.source_url)
    && typeof value.processing_status === "string"
    && isStringArray(value.warnings)
    && isOptionalString(value.error)
    && isOptionalString(value.title);
}

function isHealthResponse(value: unknown): value is HealthResponse {
  return isRecord(value)
    && typeof value.status === "string"
    && typeof value.api_version === "string"
    && typeof value.classifier_available === "boolean";
}

export function isMultilingualResult(value: unknown): value is MultilingualResult {
  if (!isRecord(value) || !isRecord(value.language_detection)) return false;
  const detection = value.language_detection;
  if (
    typeof value.original_text !== "string"
    || typeof detection.language_code !== "string"
    || typeof detection.language_name !== "string"
    || typeof detection.detection_status !== "string"
    || !(detection.detection_confidence === null
      || (typeof detection.detection_confidence === "number"
        && Number.isFinite(detection.detection_confidence)))
    || typeof value.translation_status !== "string"
    || !isOptionalString(value.translated_text)
    || !isStringArray(value.warnings)
    || !isOptionalString(value.error)
    || typeof value.verification_status !== "string"
  ) return false;

  if (value.pipeline === null) return true;
  if (!isRecord(value.pipeline)) return false;
  const { classifier, claims, claim_assessments: assessments } = value.pipeline;
  if (
    typeof value.pipeline.final_verdict !== "string"
    || !(value.pipeline.confidence === null
      || (typeof value.pipeline.confidence === "number"
        && Number.isFinite(value.pipeline.confidence)))
    || typeof value.pipeline.explanation !== "string"
    || !(classifier === null || (
      isRecord(classifier)
      && typeof classifier.prediction === "string"
      && typeof classifier.classifier === "string"
      && typeof classifier.explanation === "string"
      && typeof classifier.interpretation === "string"
      && typeof classifier.label === "number"
    ))
    || !Array.isArray(claims)
    || !claims.every((claim) => isRecord(claim)
      && typeof claim.claim_id === "number"
      && typeof claim.claim_text === "string"
      && typeof claim.claim_type === "string"
      && typeof claim.verification_status === "string")
    || !Array.isArray(assessments)
  ) return false;

  return assessments.every((assessment) => {
    if (
      !isRecord(assessment)
      || typeof assessment.claim_id !== "number"
      || typeof assessment.claim_text !== "string"
      || typeof assessment.query !== "string"
      || typeof assessment.retrieval_status !== "string"
      || !isSourceErrorArray(assessment.source_errors)
      || !isEvidenceArray(assessment.evidence)
      || !isRecord(assessment.analysis)
    ) return false;
    const analysis = assessment.analysis;
    return typeof analysis.verdict === "string"
      && (analysis.confidence === null
        || (typeof analysis.confidence === "number" && Number.isFinite(analysis.confidence)))
      && isOptionalString(analysis.confidence_type)
      && typeof analysis.explanation === "string"
      && isEvidenceArray(analysis.supporting_evidence)
      && isEvidenceArray(analysis.contradicting_evidence)
      && isEvidenceArray(analysis.neutral_evidence)
      && isEvidenceArray(analysis.conflicting_evidence)
      && isEvidenceArray(analysis.sources_used)
      && isStringArray(analysis.limitations)
      && typeof analysis.verification_status === "string";
  });
}

// New type guards for unified verification
function isLanguageDetectionResult(value: unknown): value is {
  language_code: string;
  language_name: string;
  confidence: number;
  status: string;
  warning: string | null;
} {
  return isRecord(value)
    && typeof value.language_code === "string"
    && typeof value.language_name === "string"
    && typeof value.confidence === "number"
    && typeof value.status === "string"
    && isOptionalString(value.warning);
}

function isTranslationResult(value: unknown): value is {
  original_text: string;
  translated_text: string | null;
  source_language: string;
  target_language: string;
  translation_status: string;
  warnings: string[];
  error: string | null;
} {
  return isRecord(value)
    && typeof value.original_text === "string"
    && isOptionalString(value.translated_text)
    && typeof value.source_language === "string"
    && typeof value.target_language === "string"
    && typeof value.translation_status === "string"
    && isStringArray(value.warnings)
    && isOptionalString(value.error);
}

function isClaimAssessment(value: unknown): value is {
  verdict: string;
  confidence: number | null;
  confidence_type: string | null;
  explanation: string;
  limitations: string[];
} {
  return isRecord(value)
    && typeof value.verdict === "string"
    && (value.confidence === null || (typeof value.confidence === "number" && Number.isFinite(value.confidence)))
    && isOptionalString(value.confidence_type)
    && typeof value.explanation === "string"
    && isStringArray(value.limitations);
}

// EvidenceRecord type guard - matches the new unified verification schema
function isClaimResult(value: unknown): value is {
  claim_id: string;
  claim_text: string;
  claim_type: string;
  verification_status: string;
  start_offset: number | null;
  end_offset: number | null;
  assessment: unknown;
  evidence: unknown[];
} {
  return isRecord(value)
    && typeof value.claim_id === "string"
    && typeof value.claim_text === "string"
    && typeof value.claim_type === "string"
    && typeof value.verification_status === "string"
    && (value.start_offset === null || typeof value.start_offset === "number")
    && (value.end_offset === null || typeof value.end_offset === "number")
    && (value.assessment === null || isClaimAssessment(value.assessment))
    && Array.isArray(value.evidence);
}

function isVerificationHistoryItem(value: unknown): value is VerificationHistoryItem {
  return isRecord(value)
    && typeof value.id === "string"
    && typeof value.created_at === "string"
    && typeof value.input_type === "string"
    && typeof value.original_input === "string"
    && typeof value.overall_verdict === "string"
    && (value.overall_confidence === null || typeof value.overall_confidence === "number");
}

export function isUnifiedVerifyResponse(value: unknown): value is UnifiedVerifyResponse {
  if (!isRecord(value)) return false;
  return (
    typeof value.verification_id === "string"
    && typeof value.input_type === "string"
    && typeof value.original_input === "string"
    && typeof value.extracted_text === "string"
    && isLanguageDetectionResult(value.language_detection)
    && (value.translation === null || isTranslationResult(value.translation))
    && Array.isArray(value.claims) && value.claims.every(isClaimResult)
    && typeof value.overall_verdict === "string"
    && (value.overall_confidence === null || (typeof value.overall_confidence === "number" && Number.isFinite(value.overall_confidence)))
    && typeof value.overall_explanation === "string"
    && isStringArray(value.warnings)
    && typeof value.status === "string"
  );
}

function isVerificationDetail(value: unknown): value is VerificationDetail {
  if (!isRecord(value)) return false;
  return (
    typeof value.id === "string"
    && typeof value.created_at === "string"
    && typeof value.updated_at === "string"
    && typeof value.input_type === "string"
    && typeof value.original_input === "string"
    && typeof value.extracted_text === "string"
    && isOptionalString(value.source_url)
    && isOptionalString(value.title)
    && typeof value.extraction_status === "string"
    && isStringArray(value.extraction_warnings)
    && isOptionalString(value.extraction_error)
    && isOptionalString(value.language_code)
    && isOptionalString(value.language_name)
    && (value.detection_confidence === null || typeof value.detection_confidence === "number")
    && isOptionalString(value.detection_status)
    && isOptionalString(value.translation_status)
    && isOptionalString(value.translated_text)
    && isStringArray(value.translation_warnings)
    && isOptionalString(value.translation_error)
    && isOptionalString(value.classifier_label)
    && (value.classifier_decision_score === null || typeof value.classifier_decision_score === "number")
    && isOptionalString(value.classifier_model_version)
    && isOptionalString(value.overall_verdict)
    && (value.overall_confidence === null || typeof value.overall_confidence === "number")
    && isOptionalString(value.overall_explanation)
    && isStringArray(value.warnings)
    && typeof value.status === "string"
    && Array.isArray(value.claims)
  );
}

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

async function request(path: string, init?: RequestInit): Promise<unknown> {
  let response: Response;
  try {
    const headers = new Headers(init?.headers);
    if (init?.body && !(init.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("The request timed out. Try again with shorter input.", 0, null);
    }
    throw new ApiError(
      "Cannot reach the TruthLens API. Check that the backend is running and the API URL is correct.",
      0,
      null,
    );
  }

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(getErrorMessage(payload, response.status), response.status, payload);
  }
  if (payload === null) {
    throw new ApiError("The API returned an empty or invalid JSON response.", 502, payload);
  }
  return payload;
}

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const result = await request("/api/health", { signal });
  if (!isHealthResponse(result)) {
    throw new ApiError("The API returned an invalid health response.", 502, result);
  }
  return result;
}

export async function processText(
  input: string,
  inputType: "text" | "url" | "forwarded",
  signal?: AbortSignal,
): Promise<ProcessingResult> {
  const result = await request("/api/process-input", {
    method: "POST",
    body: JSON.stringify({ input, input_type: inputType, run_pipeline: false }),
    signal,
  });
  if (!isProcessingResult(result)) {
    throw new ApiError("The API returned an invalid input-processing response.", 502, result);
  }
  return result;
}

export async function processImage(
  file: File,
  signal?: AbortSignal,
): Promise<ProcessingResult> {
  const data = new FormData();
  data.append("file", file);
  data.append("run_pipeline", "false");
  const result = await request("/api/process-image", {
    method: "POST",
    body: data,
    signal,
  });
  if (!isProcessingResult(result)) {
    throw new ApiError("The API returned an invalid image-processing response.", 502, result);
  }
  return result;
}

export async function verifyMultilingual(
  text: string,
  signal?: AbortSignal,
  sourceUrl?: string | null,
): Promise<MultilingualResult> {
  const result = await request("/api/verify/multilingual", {
    method: "POST",
    body: JSON.stringify({ text, source_url: sourceUrl || null }),
    signal,
  });
  if (!isMultilingualResult(result)) {
    throw new ApiError("The API returned an invalid multilingual verification response.", 502, result);
  }
  return result;
}

// New unified verification endpoint
export interface UnifiedVerifyOptions {
  language?: string;
  claim_selection?: "auto" | "manual" | "all";
  evidence_sources?: ("gdelt" | "google_factcheck" | "social")[];
  time_window_days?: number;
  max_results?: number;
  include_claim_offsets?: boolean;
  include_raw_evidence?: boolean;
}

export interface UnifiedVerifyRequest {
  input: string;
  input_type: "text" | "url" | "image" | "auto";
  options?: UnifiedVerifyOptions;
}

export async function verifyUnified(
  payload: UnifiedVerifyRequest,
  signal?: AbortSignal,
): Promise<UnifiedVerifyResponse> {
  const result = await request("/api/verify", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
  if (!isUnifiedVerifyResponse(result)) {
    throw new ApiError("The API returned an invalid unified verification response.", 502, result);
  }
  return result;
}

// History endpoints
export async function listVerifications(
  limit: number = 50,
  offset: number = 0,
  signal?: AbortSignal,
): Promise<VerificationHistoryItem[]> {
  const result = await request(`/api/verifications?limit=${limit}&offset=${offset}`, { signal });
  if (!Array.isArray(result) || !result.every(isVerificationHistoryItem)) {
    throw new ApiError("The API returned an invalid verifications list.", 502, result);
  }
  return result;
}

export async function getVerification(
  verificationId: string,
  signal?: AbortSignal,
): Promise<VerificationDetail | null> {
  const result = await request(`/api/verifications/${verificationId}`, { signal });
  if (result === null) {
    return null;
  }
  if (!isVerificationDetail(result)) {
    throw new ApiError("The API returned an invalid verification detail.", 502, result);
  }
  return result;
}

export async function deleteVerification(
  verificationId: string,
  signal?: AbortSignal,
): Promise<boolean> {
  const result = await request(`/api/verifications/${verificationId}`, {
    method: "DELETE",
    signal,
  });
  if (!isRecord(result) || typeof result.deleted !== "boolean") {
    throw new ApiError("The API returned an invalid delete response.", 502, result);
  }
  return result.deleted;
}