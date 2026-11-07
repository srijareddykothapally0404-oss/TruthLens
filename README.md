# TruthLens AI — Government-Grade Evidence Verification Platform

TruthLens accepts plain text, copied forwarded messages, public article URLs, and
uploaded screenshots, then can pass extracted text through the existing
TF-IDF + LinearSVC classifier, claim extractor, evidence retriever, and
evidence analyzer. The classifier is a text-pattern signal, not a fact-check.
Evidence retrieval and analysis remain separate and may return
`INSUFFICIENT EVIDENCE` when sources are unavailable or inconclusive.

## Project Overview

TruthLens is a government-grade evidence verification platform that combines a TF-IDF +
LinearSVC text-pattern classifier with claim extraction, public evidence
retrieval, and a rule-based evidence assessment. A classifier prediction is
not a factual verdict. Every retrieved item is a source lead; conclusions are
conservative and may be `INSUFFICIENT EVIDENCE`.

### Architecture and Technology

- **Backend:** Python, FastAPI, Pydantic, scikit-learn, and Uvicorn.
- **Input Processing:** Bounded static HTML extraction and optional local OCR.
- **Language Processing:** Unicode/script-based detection plus local `langid`;
  optional Argos Translate models for offline translation.
- **Evidence:** Public GDELT search results, assessed from supplied titles and
  snippets by a cautious, rule-based analyzer.
- **Frontend:** React, TypeScript, Vite, Tailwind CSS, React Router, and Lucide.
- **Model Artifacts:** The existing TF-IDF vectorizer and LinearSVC artifacts
  are used for prediction; they are not retrained or replaced at application
  startup.
- **Authentication:** JWT-based secure authentication system with role-based access.
- **Real-time:** WebSocket support for live verification updates and monitoring.

### Project Structure

```text
backend/app/main.py          FastAPI application entry point
src/api.py                   API routes, schemas, and service wiring
src/predictor.py             Existing TF-IDF + LinearSVC prediction wrapper
src/claim_extractor.py       Candidate claim extraction
src/input_processor.py       Safe text, article URL, and image processing
src/language_detector.py     Local supported-language detection
src/translation_service.py   Optional local Argos translation
src/evidence_retrieval.py    Public GDELT evidence search
src/evidence_analyzer.py     Rule-based evidence assessments
src/auth.py                  Authentication and authorization
src/websocket.py             Real-time WebSocket handlers
models/                      Existing model artifacts (retain these files)
data/                        Existing datasets (retain these files)
tests/                       Backend unit and API integration tests
frontend/src/                React application, API client, and styles
```

### Install and Run

From the project root in PowerShell, create and activate a virtual environment,
then install the project's declared Python dependencies:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Start the backend from the project root:

```powershell
python -m uvicorn backend.app.main:app --reload
```

In another PowerShell terminal, install frontend dependencies and start Vite:

```powershell
Set-Location C:\Users\srija\Desktop\TruthLens\frontend
npm install
if (!(Test-Path .env)) { Copy-Item .env.example .env }
npm run dev
```

Local URLs:

- Frontend: `http://127.0.0.1:5173`
- Production preview (after building): `http://127.0.0.1:4173`
- Backend health: `http://127.0.0.1:8000/api/health`
- API documentation: `http://127.0.0.1:8000/docs`
- WebSocket endpoint: `ws://127.0.0.1:8000/ws`

The frontend base URL is configured with `VITE_API_BASE_URL` in
`frontend/.env`. This setting is public browser configuration; never put
secrets in frontend environment variables. `.env` files, virtual environments,
dependency folders, caches, and generated builds are ignored by `.gitignore`;
datasets and model artifacts are deliberately not ignored or removed.
The backend's default CORS allowlist includes the local Vite development and
preview origins; deployments should set `TRUTHLENS_CORS_ORIGINS` explicitly.

### Deploy to Render

The root `render.yaml` blueprint creates a Python API service and a static
frontend. In Render, choose **New → Blueprint**, connect this GitHub
repository, and apply the blueprint. The frontend and API are configured to
use `truthlens-web.onrender.com` and `truthlens-api.onrender.com`.

The web build uses `requirements-web.txt`, which omits training-only
dependencies and uses the existing TF-IDF/SVM model files. Training datasets
and PyTorch checkpoints remain in the local workspace but are excluded from
Git. Render's free web service has an ephemeral filesystem, so SQLite
verification history is not durable across service restarts or redeploys.

### Features

#### Core Verification Pipeline
1. **Input Extraction** — Text, URLs, forwarded messages, images (OCR)
2. **Language Detection** — 12 languages (English + 11 Indian languages)
3. **Translation** — Offline Argos Translate with pivot language support
4. **Classifier Signal** — TF-IDF + LinearSVC pattern detection (not a verdict)
5. **Claim Extraction** — Sentence-level factual claim identification
6. **Evidence Retrieval** — GDELT DOC API + Google Fact Check Tools API
7. **Evidence Analysis** — Rule-based stance assessment with conservative verdicts

#### Government-Grade Features
- **Authentication & Authorization** — JWT tokens, role-based access control
- **Audit Logging** — Comprehensive verification history with full API traceability
- **Real-time Updates** — WebSocket-powered live verification progress
- **API Transparency** — Full API request/response details visible in UI
- **Monitoring Dashboard** — Live system health, scheduled verification jobs
- **Export Capabilities** — PDF/JSON export of verification reports

#### Supported Languages
English, Hindi, Bengali, Tamil, Telugu, Marathi, Gujarati, Kannada, Malayalam, Punjabi, Odia, Urdu

#### Verdict Types
- `TRUE` — Multiple independent credible sources support the claim
- `FALSE` — Multiple independent credible sources contradict the claim
- `PARTIALLY TRUE` — Distinct claim components have different evidence outcomes
- `MISLEADING` — Context markers indicate deceptive framing
- `INSUFFICIENT EVIDENCE` — Default when evidence is unavailable or inadequate
- `NEEDS HUMAN REVIEW` — Conflicting credible sources require expert judgment

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | System health and classifier status |
| `/api/auth/login` | POST | User authentication |
| `/api/auth/register` | POST | User registration |
| `/api/auth/me` | GET | Current user profile |
| `/api/verify` | POST | **Unified verification endpoint** |
| `/api/verify/text` | POST | Legacy text verification |
| `/api/verify/multilingual` | POST | Legacy multilingual verification |
| `/api/classify` | POST | Classifier signal only |
| `/api/extract-claims` | POST | Claim extraction |
| `/api/retrieve-evidence` | POST | Evidence retrieval |
| `/api/analyze-evidence` | POST | Evidence analysis |
| `/api/process-input` | POST | Input processing (text/URL/forwarded) |
| `/api/process-image` | POST | Image OCR processing |
| `/api/detect-language` | POST | Language detection |
| `/api/translate` | POST | Translation |
| `/api/verifications` | GET | List verification history |
| `/api/verifications/{id}` | GET | Verification detail with full API trace |
| `/api/verifications/{id}` | DELETE | Delete verification record |
| `/api/monitoring/jobs` | GET | Scheduled monitoring jobs |
| `/api/monitoring/jobs` | POST | Create monitoring job |
| `/ws` | WS | Real-time WebSocket connection |

### Configuration

#### Backend Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TRUTHLENS_API_VERSION` | "1.0.0" | API version |
| `TRUTHLENS_MODEL_DIR` | `./models` | Model artifacts directory |
| `TRUTHLENS_EVIDENCE_TIMEOUT` | 5.0 | GDELT request timeout (seconds) |
| `TRUTHLENS_EVIDENCE_MAX_RESULTS` | 5 | Max evidence items per claim |
| `TRUTHLENS_INPUT_TIMEOUT` | 8.0 | Input processing timeout (seconds) |
| `TRUTHLENS_INPUT_MAX_LENGTH` | 100000 | Max text input length |
| `TRUTHLENS_CORS_ORIGINS` | dev origins | Comma-separated CORS origins |
| `TRUTHLENS_JWT_SECRET` | required | JWT signing secret |
| `TRUTHLENS_GOOGLE_FACTCHECK_KEY` | optional | Google Fact Check API key |
| `TRUTHLENS_TESSERACT_CMD` | auto | Tesseract executable path |

#### Frontend Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | Backend API base URL |
| `VITE_WS_URL` | `ws://127.0.0.1:8000/ws` | WebSocket URL |

### External Dependencies (Optional)

| Service | Purpose | Required |
|---------|---------|----------|
| **Google Fact Check Tools API** | Live fact-check retrieval | No (RED item) |
| **Argos Translate models** | Offline translation | No (RED item) |
| **Tesseract OCR + traineddata** | Local OCR | No (RED item) |
| **GDELT DOC API** | Article discovery | No (Public, no key) |

### Testing

```bash
# Backend tests
.venv\Scripts\python.exe -m pytest -q

# Frontend type checking
cd frontend && npm run typecheck

# Frontend production build
cd frontend && npm run build
```

### License

Government use authorized. See LICENSE file for details.