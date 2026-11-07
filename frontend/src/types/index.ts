// ============================================================
// TruthLens - Government-Grade Evidence Verification Platform
// Comprehensive Type Definitions
// ============================================================

// -----------------------------------------------------------------------------
// Authentication Types
// -----------------------------------------------------------------------------

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  department?: string;
  clearance_level: ClearanceLevel;
  is_active: boolean;
  created_at: string;
  last_login?: string;
}

export type UserRole =
  | 'admin'
  | 'analyst'
  | 'reviewer'
  | 'viewer';

export type ClearanceLevel =
  | 'public'
  | 'internal'
  | 'confidential'
  | 'restricted';

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_in: number;
}

export interface LoginRequest {
  email: string;
  password: string;
  remember_me?: boolean;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
  department?: string;
  role?: UserRole;
}

export interface AuthState {
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

// -----------------------------------------------------------------------------
// Verification Types
// -----------------------------------------------------------------------------

export type InputType = 'text' | 'url' | 'forwarded' | 'image' | 'audio' | 'auto';

export type VerificationStatus =
  | 'pending'
  | 'processing'
  | 'completed'
  | 'partial'
  | 'failed';

export type VerdictType =
  | 'TRUE'
  | 'FALSE'
  | 'PARTIALLY_TRUE'
  | 'MISLEADING'
  | 'INSUFFICIENT_EVIDENCE'
  | 'NEEDS_HUMAN_REVIEW';

export type StanceType =
  | 'SUPPORTS'
  | 'CONTRADICTS'
  | 'MIXED'
  | 'NEUTRAL'
  | 'INSUFFICIENT';

export type SourceType =
  | 'official'
  | 'fact_checker'
  | 'news'
  | 'social'
  | 'unknown';

export type ConnectorType =
  | 'gdelt'
  | 'google_factcheck'
  | 'social';

export type ConnectorStatus =
  | 'success'
  | 'rate_limited'
  | 'error';

export type ContentStatus =
  | 'retrieved'
  | 'not_attempted'
  | 'unavailable'
  | 'error';

export type ClaimType =
  | 'factual'
  | 'opinion'
  | 'prediction';

export type ClaimVerificationStatus =
  | 'completed'
  | 'pending'
  | 'failed';

export type RetrievalStatus =
  | 'completed'
  | 'unavailable'
  | 'no_results'
  | 'partial';

// Language Detection
export interface LanguageDetectionResult {
  language_code: string;
  language_name: string;
  confidence: number;
  status: string;
  warning?: string | null;
}

// Translation
export interface TranslationResult {
  original_text: string;
  translated_text: string | null;
  source_language: string;
  target_language: string;
  translation_status: string;
  warnings: string[];
  error: string | null;
  provider?: string;
  model_version?: string;
  pivot_language?: string | null;
}

// Evidence
export interface EvidenceRecord {
  evidence_id: string;
  claim_id: string;
  source_type: SourceType;
  title: string;
  publisher: string;
  domain: string;
  url: string;
  published_at: string | null;
  retrieved_at: string;
  snippet: string;
  content_status: ContentStatus;
  query: string;
  connector: ConnectorType;
  connector_status: ConnectorStatus;
  relevance_score: number;
  stance: StanceType;
  full_content?: string | null;
}

// Claim Assessment
export interface ClaimAssessment {
  verdict: VerdictType;
  confidence: number | null;
  confidence_type: string | null;
  explanation: string;
  limitations: string[];
  supporting_evidence: EvidenceRecord[];
  contradicting_evidence: EvidenceRecord[];
  mixed_evidence: EvidenceRecord[];
  neutral_evidence: EvidenceRecord[];
  insufficient_evidence: EvidenceRecord[];
  sources_used: EvidenceRecord[];
  component_assessments?: ComponentAssessment[];
  retrieval_status?: RetrievalStatus;
  retrieval_query?: string;
  retrieval_source_errors?: SourceError[];
}

export interface ComponentAssessment {
  component_text: string;
  component_verdict: VerdictType;
  component_confidence: number | null;
  supporting_evidence: EvidenceRecord[];
  contradicting_evidence: EvidenceRecord[];
}

// Source Error
export interface SourceError {
  source: string;
  error: string;
  timestamp: string;
}

// Claim
export interface ClaimResult {
  claim_id: string;
  claim_text: string;
  claim_type: ClaimType;
  verification_status: ClaimVerificationStatus;
  start_offset: number | null;
  end_offset: number | null;
  assessment: ClaimAssessment | null;
  evidence: EvidenceRecord[];
}

// Classifier
export interface ClassifierResult {
  prediction: 'Real' | 'Fake';
  label: number;
  classifier: string;
  explanation: string;
  interpretation: string;
  decision_score: number | null;
  model_version: string | null;
}

// Unified Verification Request
export interface UnifiedVerifyOptions {
  language?: string;
  claim_selection?: 'auto' | 'manual' | 'all';
  evidence_sources?: ConnectorType[];
  time_window_days?: number;
  max_results?: number;
  include_claim_offsets?: boolean;
  include_raw_evidence?: boolean;
}

export interface UnifiedVerifyRequest {
  input: string;
  input_type: InputType;
  options?: UnifiedVerifyOptions;
}

// Unified Verification Response
export interface UnifiedVerifyResponse {
  verification_id: string;
  input_type: string;
  original_input: string;
  extracted_text: string;
  language_detection: LanguageDetectionResult;
  translation: TranslationResult | null;
  classifier: ClassifierResult | null;
  claims: ClaimResult[];
  overall_verdict: VerdictType;
  overall_confidence: number | null;
  overall_explanation: string;
  warnings: string[];
  status: VerificationStatus;
  created_at: string;
  processing_time_ms: number;
  api_calls: ApiCallTrace[];
}

// API Call Trace for Transparency
export interface ApiCallTrace {
  endpoint: string;
  method: string;
  timestamp: string;
  duration_ms: number;
  status: 'success' | 'error' | 'timeout';
  request_summary?: string;
  response_summary?: string;
  error_details?: string;
}

// -----------------------------------------------------------------------------
// History Types
// -----------------------------------------------------------------------------

export interface VerificationHistoryItem {
  id: string;
  created_at: string;
  updated_at: string;
  input_type: string;
  original_input: string;
  extracted_text: string;
  overall_verdict: VerdictType;
  overall_confidence: number | null;
  status: VerificationStatus;
  processing_time_ms: number;
  claim_count: number;
  evidence_count: number;
  user_id: string;
}

export interface VerificationDetail extends VerificationHistoryItem {
  source_url: string | null;
  title: string | null;
  extraction_status: string;
  extraction_warnings: string[];
  extraction_error: string | null;
  language_code: string | null;
  language_name: string | null;
  detection_confidence: number | null;
  detection_status: string | null;
  translation_status: string | null;
  translated_text: string | null;
  translation_warnings: string[];
  translation_error: string | null;
  classifier_label: string | null;
  classifier_decision_score: number | null;
  classifier_model_version: string | null;
  overall_explanation: string | null;
  warnings: string[];
  claims: VerificationClaimDetail[];
  api_traces: ApiCallTrace[];
}

export interface VerificationClaimDetail {
  id: string;
  verification_id: string;
  claim_index: number;
  claim_text: string;
  claim_type: ClaimType;
  verification_status: ClaimVerificationStatus;
  assessment_verdict: VerdictType | null;
  assessment_confidence: number | null;
  assessment_explanation: string | null;
  assessment_confidence_type: string | null;
  assessment_limitations: string[];
  evidence: VerificationEvidenceDetail[];
}

export interface VerificationEvidenceDetail {
  id: string;
  claim_id: string;
  evidence_index: number;
  source_type: SourceType | null;
  title: string | null;
  publisher: string | null;
  domain: string | null;
  url: string | null;
  published_at: string | null;
  retrieved_at: string | null;
  snippet: string | null;
  content_status: ContentStatus | null;
  query: string | null;
  connector: ConnectorType | null;
  connector_status: ConnectorStatus | null;
  relevance_score: number | null;
  stance: StanceType | null;
  full_content: string | null;
}

// -----------------------------------------------------------------------------
// Monitoring Types
// -----------------------------------------------------------------------------

export interface MonitoringJob {
  id: string;
  name: string;
  description: string;
  query: string;
  filters: MonitoringFilters;
  schedule: MonitoringSchedule;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_run?: string;
  next_run?: string;
  run_count: number;
  created_by: string;
}

export interface MonitoringFilters {
  languages?: string[];
  countries?: string[];
  source_types?: SourceType[];
  date_range_days?: number;
  min_relevance?: number;
}

export interface MonitoringSchedule {
  type: 'interval' | 'cron';
  interval_minutes?: number;
  cron_expression?: string;
  timezone: string;
}

export interface MonitoringResult {
  job_id: string;
  job_name: string;
  run_at: string;
  status: 'success' | 'partial' | 'failed';
  claims_found: number;
  verifications_created: number;
  new_evidence_count: number;
  errors: string[];
  duration_ms: number;
}

// -----------------------------------------------------------------------------
// System Health Types
// -----------------------------------------------------------------------------

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'down';
  api_version: string;
  classifier_available: boolean;
  timestamp: string;
  services: ServiceHealth[];
  uptime_seconds: number;
}

export interface ServiceHealth {
  name: string;
  status: 'available' | 'degraded' | 'unavailable' | 'on-demand';
  detail: string;
  last_checked: string;
  latency_ms?: number;
  error?: string;
}

// -----------------------------------------------------------------------------
// API Error Types
// -----------------------------------------------------------------------------

export interface ApiErrorResponse {
  detail: string;
  error_code?: string;
  timestamp: string;
  path: string;
  request_id: string;
}

// -----------------------------------------------------------------------------
// UI State Types
// -----------------------------------------------------------------------------

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info' | 'loading';
  message: string;
  duration?: number;
}

export interface ModalState<T = unknown> {
  isOpen: boolean;
  data: T | null;
}

export interface TableState {
  page: number;
  pageSize: number;
  sortBy: string | null;
  sortOrder: 'asc' | 'desc';
  filters: Record<string, unknown>;
}

// -----------------------------------------------------------------------------
// Form Types
// -----------------------------------------------------------------------------

export interface VerificationFormData {
  input: string;
  input_type: InputType;
  options: {
    language?: string;
    claim_selection: 'auto' | 'manual' | 'all';
    evidence_sources: ConnectorType[];
    time_window_days: number;
    max_results: number;
    include_claim_offsets: boolean;
    include_raw_evidence: boolean;
  };
}

export interface VerificationFormErrors {
  input?: string;
  input_type?: string;
  options?: Partial<VerificationFormData['options']>;
}

// -----------------------------------------------------------------------------
// Export/Report Types
// -----------------------------------------------------------------------------

export interface ExportOptions {
  format: 'pdf' | 'json' | 'csv';
  include_evidence: boolean;
  include_api_traces: boolean;
  include_raw_responses: boolean;
  date_range?: {
    from: string;
    to: string;
  };
}

export interface VerificationReport {
  verification: VerificationDetail;
  generated_at: string;
  generated_by: string;
  format: string;
  pages: number;
}

// ============================================================
// Type Guards
// ============================================================

export function isVerdictType(value: string): value is VerdictType {
  return [
    'TRUE',
    'FALSE',
    'PARTIALLY_TRUE',
    'MISLEADING',
    'INSUFFICIENT_EVIDENCE',
    'NEEDS_HUMAN_REVIEW',
  ].includes(value);
}

export function isStanceType(value: string): value is StanceType {
  return ['SUPPORTS', 'CONTRADICTS', 'MIXED', 'NEUTRAL', 'INSUFFICIENT'].includes(value);
}

export function isVerificationStatus(value: string): value is VerificationStatus {
  return ['pending', 'processing', 'completed', 'partial', 'failed'].includes(value);
}

export function getVerdictColor(verdict: VerdictType): string {
  switch (verdict) {
    case 'TRUE': return 'text-green-700 bg-green-100 dark:text-green-300 dark:bg-green-900/30';
    case 'FALSE': return 'text-red-700 bg-red-100 dark:text-red-300 dark:bg-red-900/30';
    case 'PARTIALLY_TRUE': return 'text-amber-700 bg-amber-100 dark:text-amber-300 dark:bg-amber-900/30';
    case 'MISLEADING': return 'text-orange-700 bg-orange-100 dark:text-orange-300 dark:bg-orange-900/30';
    case 'INSUFFICIENT_EVIDENCE': return 'text-gray-700 bg-gray-100 dark:text-gray-300 dark:bg-gray-800';
    case 'NEEDS_HUMAN_REVIEW': return 'text-purple-700 bg-purple-100 dark:text-purple-300 dark:bg-purple-900/30';
    default: return 'text-gray-700 bg-gray-100 dark:text-gray-300 dark:bg-gray-800';
  }
}

export function getVerdictLabel(verdict: VerdictType): string {
  switch (verdict) {
    case 'TRUE': return 'TRUE';
    case 'FALSE': return 'FALSE';
    case 'PARTIALLY_TRUE': return 'PARTIALLY TRUE';
    case 'MISLEADING': return 'MISLEADING';
    case 'INSUFFICIENT_EVIDENCE': return 'INSUFFICIENT EVIDENCE';
    case 'NEEDS_HUMAN_REVIEW': return 'NEEDS HUMAN REVIEW';
    default: return verdict;
  }
}

export function getStanceColor(stance: StanceType): string {
  switch (stance) {
    case 'SUPPORTS': return 'text-green-600 bg-green-50 dark:text-green-400 dark:bg-green-900/20';
    case 'CONTRADICTS': return 'text-red-600 bg-red-50 dark:text-red-400 dark:bg-red-900/20';
    case 'MIXED': return 'text-amber-600 bg-amber-50 dark:text-amber-400 dark:bg-amber-900/20';
    case 'NEUTRAL': return 'text-blue-600 bg-blue-50 dark:text-blue-400 dark:bg-blue-900/20';
    case 'INSUFFICIENT': return 'text-gray-600 bg-gray-50 dark:text-gray-400 dark:bg-gray-800';
    default: return 'text-gray-600 bg-gray-50 dark:text-gray-400 dark:bg-gray-800';
  }
}

export function getSourceTypeBadge(sourceType: SourceType): { label: string; class: string } {
  switch (sourceType) {
    case 'official': return { label: 'OFFICIAL', class: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300' };
    case 'fact_checker': return { label: 'FACT-CHECKER', class: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300' };
    case 'news': return { label: 'NEWS', class: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300' };
    case 'social': return { label: 'SOCIAL', class: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300' };
    case 'unknown': return { label: 'UNKNOWN', class: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300' };
    default: return { label: 'UNKNOWN', class: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300' };
  }
}

// ============================================================
// Legacy Types (for backward compatibility with App.tsx)
// ============================================================

export interface ProcessingResult {
  input_type: string;
  original_input: string;
  extracted_text: string;
  source_url: string | null;
  processing_status: string;
  warnings: string[];
  error: string | null;
  title?: string | null;
}

export interface EvidenceItem {
  evidence_id?: string | null;
  source_name?: string | null;
  source_domain?: string | null;
  source_url?: string | null;
  title?: string | null;
  snippet?: string | null;
  page_content?: string | null;
  page_content_status?: string | null;
  published_date?: string | null;
  relevance_score?: number | null;
  assessment?: string | null;
  source_type?: string | null;
  connector?: string | null;
  connector_status?: string | null;
  stance?: string | null;
}

export interface LegacyClaimAssessment {
  claim_id: number;
  claim_text: string;
  query: string;
  retrieval_status: string;
  source_errors: Array<{ source: string; error: string }>;
  evidence: EvidenceItem[];
  analysis: {
    verdict: string;
    confidence: number | null;
    confidence_type: string | null;
    explanation: string;
    supporting_evidence: EvidenceItem[];
    contradicting_evidence: EvidenceItem[];
    neutral_evidence: EvidenceItem[];
    conflicting_evidence: EvidenceItem[];
    sources_used: EvidenceItem[];
    limitations: string[];
    verification_status: string;
  };
}

export interface PipelineResult {
  final_verdict: string;
  confidence: number | null;
  explanation: string;
  classifier: {
    prediction: string;
    label: number;
    classifier: string;
    explanation: string;
    interpretation: string;
  } | null;
  claims: Array<{
    claim_id: number;
    claim_text: string;
    claim_type: string;
    verification_status: string;
  }>;
  claim_assessments: LegacyClaimAssessment[];
}

export interface MultilingualResult {
  original_text: string;
  language_detection: {
    language_code: string;
    language_name: string;
    detection_confidence: number | null;
    detection_status: string;
    warning?: string;
  };
  translated_text: string | null;
  translation_status: string;
  warnings: string[];
  error: string | null;
  verification_status: string;
  pipeline: PipelineResult | null;
}

export interface VerificationSession {
  submittedInput: string;
  inputMode: 'text' | 'forwarded' | 'url' | 'image';
  processing: ProcessingResult | null;
  verification: MultilingualResult | null;
  frontendError: string | null;
  createdAt: string;
}

// Legacy ClaimResult and EvidenceRecord aliases for backward compat
export type LegacyClaimResult = ClaimResult;
export type LegacyEvidenceRecord = EvidenceRecord;