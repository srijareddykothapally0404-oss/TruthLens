# TruthLens AI - Design Document Gap Analysis

**Date:** 2026-11-06  
**Based on:** TruthLens AI Complete Design Document v1.0 (06 November 2026)  
**Current State:** Implementation Audit completed 2026-11-06

---

## Executive Summary

The current implementation covers ~70% of the design document requirements. Major gaps exist in:
1. **Article extraction library** (custom HTML parser vs Trafilatura/readability-lxml)
2. **Google Fact Check API integration** (not implemented)
3. **API contract changes** (different request/response format)
4. **SQLite persistence** for verification history (currently session-only)
5. **Scheduled monitoring** with APScheduler (not implemented)
6. **Enhanced claim extraction** (compound claims, manual editing, offsets)
7. **Evidence stance labels** (SUPPORTS/CONTRADICTS/MIXED vs current supporting/contradicting/unrelated)
8. **Environment configuration** (many more services in .env.example)
9. **Entry point** (design says `uvicorn src.api:app` vs current `backend.app.main:app`)

---

## Detailed Gap Analysis by Section

### 7. Input Acquisition & Extraction

| Design Requirement | Current Implementation | Gap | Priority |
|---|---|---|---|
| **Article extractor: Trafilatura or readability-lxml** | Custom HTMLParser in `input_processor.py` | **MAJOR** - Need to replace with proven library | High |
| **SSRF-safe fetcher with DNS pinning** | ✅ Implemented in `input_processor.py` | None | - |
| **OCR: Tesseract + pytesseract + Pillow + preprocessing** | ✅ Basic OCR in `input_processor.py` | Missing preprocessing (grayscale, resize, denoise, deskew) | Medium |
| **Social platforms: optional approved adapters** | Partial (static HTML only for X/Facebook) | Need connector framework for X, Facebook, WhatsApp | Medium |
| **Preserve original image + display OCR for correction** | ❌ Not implemented | Frontend needs OCR preview/edit | High |

### 8. Multilingual NLP & Translation

| Design Requirement | Current Implementation | Gap | Priority |
|---|---|---|---|
| **Runtime registry of supported language pairs** | Hardcoded in `language_detector.py` | Need dynamic registry from installed Argos models | Medium |
| **Argos Translate with pivot language marking** | ✅ Implemented in `translation_service.py` | Missing pivot language tracking | Low |
| **Optional IndicTrans2 / AI4Bharat evaluation** | ❌ Not evaluated | Future enhancement | Low |
| **Translation provider/pair/version/status in response** | Partial | Need to include in API response | Medium |
| **Do not pass unsupported regional text to English classifier** | ✅ Enforced in multilingual pipeline | None | - |

### 9. ML Classifier

| Design Requirement | Current Implementation | Gap | Priority |
|---|---|---|---|
| **Leakage audit & near-duplicate detection** | Basic duplicate removal only | Need source/time-aware holdout, leakage audit | High |
| **Source/time-aware holdout tests** | Random split only | Need stratified by source/date | High |
| **Per-source performance evaluation** | Not implemented | Need evaluation by publisher | Medium |
| **Store dataset version, preprocessing, params, seed, checksum** | Not implemented | Need metadata with model artifacts | Medium |
| **Decision_function margin score (not probability)** | ❌ Not exposed | API returns label only, no margin score | High |
| **Re-evaluate on recent Indian news + translations** | Not done | Ongoing requirement | Medium |

### 10. Claim Extraction

| Design Requirement | Current Implementation | Gap | Priority |
|---|---|---|---|
| **Compound claim splitting (multiple dates, quantities, propositions)** | ❌ Single sentence per claim | Need to split compound claims | High |
| **Preserve source sentence + character offsets** | ❌ Not preserved | Need offset tracking | Medium |
| **Manual claim addition/editing before evidence search** | ❌ Not supported | Frontend + API need claim editing | High |
| **Separate facts from opinions, predictions, questions, slogans** | Basic predicate heuristics | Need better classification | Medium |
| **User may edit/add/remove claims** | ❌ Not implemented | Full claim management UI needed | High |

### 11. Live Evidence Retrieval

| Design Requirement | Current Implementation | Gap | Priority |
|---|---|---|---|
| **Google Fact Check Tools API integration** | ❌ Not implemented | **MAJOR** - New connector needed | High |
| **Evidence record schema (evidence_id, claim_id, source_type, published_at, retrieved_at, content_status, connector, connector_status)** | Partial (different field names) | Need to align with design schema | High |
| **Deduplicate canonical URLs + content fingerprints** | URL + normalized title only | Need content fingerprinting | Medium |
| **Retain original + final redirected URLs** | ✅ Implemented | None | - |
| **Syndication cluster identification** | ❌ Not implemented | Need to detect syndicated copies | Medium |
| **Respect robots.txt, copyright (snippets + links only)** | Partial | Need explicit compliance | Low |
| **Time-windowed queries** | Not implemented | Need time_window parameter | Medium |

### 12. Evidence Analysis & Verdict Policy

| Design Requirement | Current Implementation | Gap | Priority |
|---|---|---|---|
| **Stance labels: SUPPORTS, CONTRADICTS, MIXED, NEUTRAL, INSUFFICIENT** | supporting, contradicting, unrelated | **Schema change needed** | High |
| **NLI model benchmarking for stronger semantics** | Rule-based only | Future enhancement | Low |
| **Calibrated thresholds, negation, numerical contradiction testing** | Basic negation handling | Need rigorous testing | Medium |
| **Human review flag for high-impact topics** | ❌ Not implemented | Need NEEDS HUMAN REVIEW verdict | Medium |
| **Classifier_label + classifier_score separate from claim_assessments** | ✅ Separated in pipeline | Need decision_score in API | Medium |
| **Classifier cannot override evidence** | ✅ Enforced | None | - |

### 13. Live News Monitoring

| Design Requirement | Current Implementation | Gap | Priority |
|---|---|---|---|
| **Scheduled monitoring with APScheduler** | ❌ Not implemented | **MAJOR** - New feature | Medium |
| **User-approved topic, query, geo/language filters, polling interval, retention** | ❌ Not implemented | Need config + storage | Medium |
| **Notify only on new relevant evidence** | ❌ Not implemented | Need notification system | Low |
| **Display published_at and retrieved_at separately** | Partial | Need consistent fields | Medium |

### 14. API Contracts (MAJOR CHANGES)

| Design Requirement | Current Implementation | Gap | Priority |
|---|---|---|---|
| **Single unified endpoint with input_type parameter** | Multiple endpoints (`/process-input`, `/process-image`, `/verify/multilingual`) | **MAJOR** - Need unified endpoint | High |
| **Request: `{input_type, text, url, include_classifier, include_evidence, time_window, max_claims}`** | Different parameters across endpoints | Need to consolidate | High |
| **Response: `{verification_id, status, extraction, language, classifier, claims, overall_verdict, warnings}`** | Different response structure | **MAJOR** - Full response redesign | High |
| **Classifier response includes decision_score + model_version** | Only label + prediction | Need margin score + version | High |
| **Claim assessment uses SUPPORTS/CONTRADICTS/MIXED/NEUTRAL/INSUFFICIENT** | Different stance labels | Schema change | High |
| **Version response schemas** | Not implemented | Need versioning | Medium |

### 15. External Services & Manual Setup

| Design Requirement | Current Implementation | Gap | Priority |
|---|---|---|---|
| **Complete .env.example with all services** | Empty .env, no .env.example | **Need to create full .env.example** | High |
| **Tesseract CMD path configuration** | Not configurable | Need TESSERACT_CMD env var | Medium |
| **Google Fact Check API key** | Not integrated | Need connector + key | High |
| **X API, Meta/Facebook, WhatsApp configs** | Not implemented | Future connectors | Low |
| **Google Vision OCR config** | Not implemented | Optional cloud OCR | Low |
| **NewsAPI config (with production warning)** | Not implemented | Need config + warning | Low |

### 16. Data Model & Storage

| Design Requirement | Current Implementation | Gap | Priority |
|---|---|---|---|
| **SQLite for local report history** | ❌ In-memory only, no persistence | **MAJOR** - Need database layer | High |
| **Retention policies for images/full text** | ❌ Not implemented | Need cleanup policies | Medium |
| **File hashing for deduplication** | ❌ Not implemented | Need hash storage | Low |
| **Deletion policy + secret-free logs** | Basic logging | Need structured retention | Medium |

### 17. Security & Responsible AI

| Design Requirement | Current Implementation | Gap | Priority |
|---|---|---|---|
| **User-facing disclaimer** | In API responses, not prominent in UI | Need prominent UI disclaimer | High |
| **Log correlation IDs, connector, latency, status, retry, model versions** | Basic logging | Need structured logging | Medium |
| **Track extraction success, OCR failure rate, translation coverage, retrieval success, evidence freshness, abstention rate** | ❌ Not implemented | Need metrics/observability | Medium |

### 19. Testing

| Design Requirement | Current Implementation | Gap | Priority |
|---|---|---|---|
| **Trafilatura/readability extractor tests with fixtures** | Custom parser tests | Need new extractor tests | High |
| **OCR tests: English, Telugu, Hindi images with reviewed expected text** | Basic PNG test | Need real image fixtures | High |
| **Translation tests: every installed pair + missing package fallback** | Partial | Need comprehensive pair testing | Medium |
| **Integration: Telugu text -> detection -> translation -> claims -> evidence** | Partial | Need full pipeline test | High |
| **GDELT timeout -> graceful partial report** | ✅ Implemented | None | - |
| **Missing Fact Check key -> connector marked unconfigured** | ❌ Not implemented | Need Fact Check connector first | High |
| **Frontend displays source links, retrieval timestamps, warnings** | Partial | Need timestamp display | Medium |
| **No search results never becomes FALSE automatically** | ✅ Enforced | None | - |

### 20. Deployment

| Design Requirement | Current Implementation | Gap | Priority |
|---|---|---|---|
| **Entry point: `uvicorn src.api:app --reload`** | `uvicorn backend.app.main:app --reload` | **Entry point mismatch** | High |
| **PostgreSQL for multi-user hosted** | SQLite planned | Future | Low |

---

## RED Items (External APIs/Services Required But Not Available)

| Service | Purpose | Status | Action Required |
|---|---|---|---|
| **Google Fact Check Tools API** | Live fact-check retrieval | **NOT CONFIGURED** | Need API key from Google Cloud Console |
| **GDELT DOC API** | Article discovery | ✅ Working (public, no key) | None |
| **Argos Translate models** | Offline translation | **NOT INSTALLED** | Need to install argostranslate + .argosmodel packages |
| **Tesseract OCR + traineddata** | Local OCR | **NOT INSTALLED** | Need Windows installer + language data |
| **X (Twitter) API** | Social post retrieval | **NOT CONFIGURED** | Need X Developer account + Bearer token |
| **Meta/Facebook Graph API** | Facebook post retrieval | **NOT CONFIGURED** | Need Meta Developer account + Access token |
| **WhatsApp Cloud API** | WhatsApp message retrieval | **NOT CONFIGURED** | Need Meta Business account |
| **Google Cloud Vision** | Cloud OCR fallback | **NOT CONFIGURED** | Need GCP project + credentials |
| **NewsAPI** | Article search (dev only, not production) | **NOT CONFIGURED** | Need API key (dev only) |
| **IndicTrans2 / AI4Bharat** | Better translation | **NOT EVALUATED** | Future evaluation |

---

## Implementation Priority Matrix

### Phase 1: Critical API Contract Alignment (Week 1-2)
- [ ] Create unified `/api/verify` endpoint matching design spec
- [ ] Align request/response schemas with design document
- [ ] Add `decision_score` and `model_version` to classifier response
- [ ] Change stance labels to SUPPORTS/CONTRADICTS/MIXED/NEUTRAL/INSUFFICIENT
- [ ] Fix entry point to `uvicorn src.api:app`

### Phase 2: Core Extraction & Evidence (Week 2-3)
- [ ] Replace custom HTML parser with Trafilatura
- [ ] Add OCR preprocessing (grayscale, resize, denoise, deskew)
- [ ] Implement Google Fact Check Tools API connector
- [ ] Add time_window parameter to evidence retrieval
- [ ] Implement content fingerprint deduplication

### Phase 3: Persistence & History (Week 3)
- [ ] Add SQLite database layer for verification history
- [ ] Implement retention policies
- [ ] Frontend history page connects to backend persistence

### Phase 4: Enhanced Claims & Monitoring (Week 4)
- [ ] Compound claim splitting
- [ ] Manual claim editing API + UI
- [ ] APScheduler-based scheduled monitoring
- [ ] Character offset preservation

### Phase 5: Configuration & Observability (Week 4-5)
- [ ] Create complete `.env.example` with all services
- [ ] Add structured logging with correlation IDs
- [ ] Add metrics tracking (extraction success, OCR failure, etc.)
- [ ] Prominent UI disclaimer

### Phase 6: Testing & RED Items (Week 5-6)
- [ ] Install Tesseract + language data (RED)
- [ ] Install Argos + required .argosmodel packages (RED)
- [ ] Get Google Fact Check API key (RED)
- [ ] Comprehensive test fixtures for OCR, translation, extraction
- [ ] Full integration test pipeline

---

## Files to Modify/Create

### Backend - Core Changes
| File | Change Type | Description |
|---|---|---|
| `src/api.py` | **MAJOR REWRITE** | Unified endpoint, new schemas, SQLite integration |
| `src/input_processor.py` | **MAJOR REWRITE** | Trafilatura integration, OCR preprocessing |
| `src/evidence_retrieval.py` | **MODIFY** | Google Fact Check connector, time_window, fingerprint dedup |
| `src/evidence_analyzer.py` | **MODIFY** | New stance labels, NEEDS HUMAN REVIEW verdict |
| `src/claim_extractor.py` | **MODIFY** | Compound splitting, offsets, manual editing support |
| `src/predictor.py` | **MODIFY** | Expose decision_function margin score |
| `src/language_detector.py` | **MODIFY** | Dynamic language pair registry |
| `src/translation_service.py` | **MODIFY** | Pivot language tracking, provider metadata |
| `src/database.py` | **NEW** | SQLite models + persistence layer |
| `src/monitoring.py` | **NEW** | APScheduler monitoring service |
| `src/logging_config.py` | **NEW** | Structured logging + correlation IDs |
| `src/config.py` | **NEW** | Centralized config from .env |

### Backend - Training/Evaluation
| File | Change Type | Description |
|---|---|---|
| `src/train_tfidf.py` | **MODIFY** | Leakage audit, source/time holdout, metadata storage |

### Frontend - Core Changes
| File | Change Type | Description |
|---|---|---|
| `frontend/src/api.ts` | **MAJOR REWRITE** | New unified API client matching design contracts |
| `frontend/src/types.ts` | **MAJOR REWRITE** | New TypeScript interfaces for unified response |
| `frontend/src/App.tsx` | **MODIFY** | Claim editing UI, OCR preview, history from DB, disclaimer |
| `frontend/src/components/` | **NEW** | Reusable components (ClaimEditor, EvidenceCard, etc.) |

### Configuration
| File | Change Type | Description |
|---|---|---|
| `.env.example` | **NEW** | Complete template from design doc Section 15.2 |
| `.env` | **CREATE** | Local development overrides |
| `frontend/.env.example` | **NEW** | Frontend-specific config |

### Tests
| File | Change Type | Description |
|---|---|---|
| `tests/test_input_processor.py` | **MODIFY** | Trafilatura tests, OCR fixture tests |
| `tests/test_evidence_retrieval.py` | **MODIFY** | Fact Check connector tests |
| `tests/test_claim_extractor.py` | **MODIFY** | Compound claim, offset tests |
| `tests/test_integration.py` | **NEW** | Full pipeline integration tests |
| `tests/fixtures/` | **NEW** | OCR images, HTML fixtures, expected outputs |

---

## Estimated Effort

| Phase | Backend Days | Frontend Days | Total Days |
|---|---|---|---|
| Phase 1: API Contracts | 3 | 2 | 5 |
| Phase 2: Extraction & Evidence | 4 | 1 | 5 |
| Phase 3: Persistence | 2 | 2 | 4 |
| Phase 4: Claims & Monitoring | 3 | 3 | 6 |
| Phase 5: Config & Observability | 2 | 1 | 3 |
| Phase 6: Testing & RED Items | 3 | 1 | 4 |
| **Total** | **17** | **10** | **27 days** |

---

## Next Steps

1. **User to provide RED items**: Google Fact Check API key, Tesseract installation, Argos models
2. **Start Phase 1**: Unified API endpoint implementation
3. **Parallel**: Create `.env.example` and install Tesseract/Argos
4. **Review**: Confirm API contract changes before frontend work

---

*Gap analysis completed 2026-11-06 based on TruthLens AI Complete Design Document v1.0*