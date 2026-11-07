import { useEffect, useState } from "react";
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  BadgeCheck,
  Check,
  ChevronDown,
  CircleHelp,
  Clock3,
  FileCheck2,
  FileImage,
  FileText,
  Globe2,
  House,
  Languages,
  LoaderCircle,
  Menu,
  Moon,
  Radio,
  Search,
  Shield,
  ShieldCheck,
  Sparkles,
  Sun,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import {
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import {
  ApiError,
  getApiBaseUrl,
  getHealth,
  isMultilingualResult,
  isProcessingResult,
  processImage,
  processText,
  verifyMultilingual,
  verifyUnified,
  listVerifications,
  getVerification,
  deleteVerification,
  type UnifiedVerifyRequest,
} from "./api";
import type {
  UnifiedVerifyResponse,
  VerificationHistoryItem,
  VerificationDetail,
  ClaimAssessment,
  HealthResponse,
  MultilingualResult,
  ProcessingResult,
  VerificationSession,
  ClaimResult,
  EvidenceRecord,
} from "@/types";

type Theme = "light" | "dark";
type InputMode = VerificationSession["inputMode"];

const navigation = [
  { to: "/", label: "Overview", icon: House, end: true },
  { to: "/verify", label: "Verify news", icon: Search },
  { to: "/history", label: "Verification history", icon: Clock3 },
  { to: "/about", label: "About TruthLens", icon: CircleHelp },
  { to: "/status", label: "API status", icon: Activity },
];

const pageTitles: Record<string, string> = {
  "/": "Overview",
  "/verify": "Verify news",
  "/results": "Verification results",
  "/history": "Verification history",
  "/about": "About TruthLens",
  "/status": "API status",
};

function useBackendHealth() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const check = () => {
      getHealth(controller.signal)
        .then(setHealth)
        .catch(() => setHealth(null))
        .finally(() => setChecked(true));
    };
    check();
    const timer = window.setInterval(check, 30_000);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, []);

  return { health, checked };
}

function App() {
  const [theme, setTheme] = useState<Theme>(
    () => sessionStorage.getItem("newslens-theme") === "dark" ? "dark" : "light",
  );
  const [session, setSession] = useState<VerificationSession | null>(null);
  const [unifiedResult, setUnifiedResult] = useState<UnifiedVerifyResponse | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { health, checked } = useBackendHealth();

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    sessionStorage.setItem("newslens-theme", theme);
  }, [theme]);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname]);

  const title = pageTitles[location.pathname] || "TruthLens";

  return (
    <div className="app-shell">
      {mobileNavOpen && (
        <button
          aria-label="Close navigation"
          className="mobile-backdrop"
          onClick={() => setMobileNavOpen(false)}
        />
      )}
      <aside className={`sidebar ${mobileNavOpen ? "sidebar-open" : ""}`}>
        <div className="brand-lockup">
          <div className="brand-mark"><ShieldCheck size={21} strokeWidth={2.2} /></div>
          <div>
            <div className="brand-name">TruthLens<span>AI</span></div>
            <div className="brand-caption">EVIDENCE INTELLIGENCE</div>
          </div>
          <button
            className="icon-button sidebar-close"
            aria-label="Close menu"
            onClick={() => setMobileNavOpen(false)}
          >
            <X size={18} />
          </button>
        </div>

        <div className="workspace-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          {navigation.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => `nav-link ${isActive ? "nav-active" : ""}`}
            >
              <Icon size={18} strokeWidth={1.8} />
              <span>{label}</span>
              {to === "/verify" && <span className="nav-shortcut">NEW</span>}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <div className="sidebar-note-icon"><Shield size={17} /></div>
            <div>
              <strong>Evidence first</strong>
              <span>Classifier signals are not verdicts.</span>
            </div>
          </div>
          <div className="sidebar-user">
            <div className="avatar">NL</div>
            <div className="user-copy">
              <strong>Local workspace</strong>
              <span>Private session</span>
            </div>
            <span className="user-status" title="Local workspace" />
          </div>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => setMobileNavOpen(true)}
            >
              <Menu size={20} />
            </button>
            <div className="breadcrumbs">
              <span>TruthLens</span><span className="crumb-slash">/</span><strong>{title}</strong>
            </div>
          </div>
          <div className="topbar-actions">
            <span className={`connection-pill ${health ? "connected" : "disconnected"}`}>
              <span className="connection-dot" />
              {health ? "API connected" : checked ? "API offline" : "Checking API"}
            </span>
            <button
              className="icon-button theme-toggle"
              aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
              onClick={() => setTheme(theme === "light" ? "dark" : "light")}
            >
              {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
            </button>
            <div className="topbar-avatar" aria-label="TruthLens government workspace">T</div>
          </div>
        </header>

        <main className="page-content">
          <Routes>
            <Route
              path="/"
              element={<Dashboard health={health} onStart={() => navigate("/verify")} />}
            />
            <Route
              path="/verify"
              element={
                <VerifyPage
                  onComplete={(nextSession, unified) => {
                    setSession(nextSession);
                    setUnifiedResult(unified);
                    navigate("/results");
                  }}
                />
              }
            />
            <Route path="/results" element={<ResultsPage session={session} unifiedResult={unifiedResult} />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="/status" element={<StatusPage />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
        <footer className="app-footer">
          <span>TruthLens <span className="footer-dot">·</span> Government-Grade Evidence Verification</span>
          <span>Local development workspace</span>
        </footer>
      </div>
    </div>
  );
}

function PageIntro({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="page-intro">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}

function Dashboard({
  health,
  onStart,
}: {
  health: HealthResponse | null;
  onStart: () => void;
}) {
  return (
    <>
      <section className="welcome-banner">
        <div className="welcome-copy">
          <div className="welcome-kicker"><Sparkles size={14} /> NEWS VERIFICATION WORKSPACE</div>
          <h1>Clarity starts with<br /><span>what the evidence says.</span></h1>
          <p>Review claims with transparent signals, source context, and careful language — never a guess dressed up as a fact.</p>
          <button className="button button-white" onClick={onStart}>
            Start a verification <ArrowRight size={16} />
          </button>
        </div>
        <div className="welcome-visual" aria-hidden="true">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="orbit-core"><ShieldCheck size={44} /></div>
          <div className="orbit-chip chip-one"><FileCheck2 size={16} /><span>Claims</span></div>
          <div className="orbit-chip chip-two"><Globe2 size={16} /><span>Sources</span></div>
          <div className="orbit-chip chip-three"><BadgeCheck size={16} /><span>Context</span></div>
          <div className="visual-spark spark-one">✦</div>
          <div className="visual-spark spark-two">✦</div>
        </div>
      </section>

      <div className="section-heading">
        <div><span className="section-kicker">YOUR WORKSPACE</span><h2>Verification overview</h2></div>
        <span className="updated-label"><span className="live-dot" /> Live system status</span>
      </div>

      <section className="overview-grid">
        <article className="overview-card">
          <div className="overview-card-top"><span className="overview-icon icon-green"><Radio size={18} /></span><span className="card-kicker">BACKEND</span></div>
          <strong className="overview-value">{health ? "Connected" : "Offline"}</strong>
          <span className="overview-foot">{health ? `API v${health.api_version}` : "Check the local API service"}</span>
          <div className={`card-indicator ${health ? "indicator-green" : "indicator-red"}`} />
        </article>
        <article className="overview-card">
          <div className="overview-card-top"><span className="overview-icon icon-blue"><Languages size={18} /></span><span className="card-kicker">LANGUAGE</span></div>
          <strong className="overview-value">12 languages</strong>
          <span className="overview-foot">English + 11 Indian languages</span>
          <span className="card-corner-icon"><Globe2 size={39} /></span>
        </article>
        <article className="overview-card">
          <div className="overview-card-top"><span className="overview-icon icon-violet"><FileText size={18} /></span><span className="card-kicker">INPUT TYPES</span></div>
          <strong className="overview-value">Text, links & images</strong>
          <span className="overview-foot">Including forwarded messages</span>
          <span className="card-corner-icon"><FileImage size={39} /></span>
        </article>
      </section>

      <section className="dashboard-lower">
        <article className="panel workflow-panel">
          <div className="panel-heading">
            <div><span className="section-kicker">HOW IT WORKS</span><h2>From input to insight</h2></div>
            <span className="subtle-count">4 steps</span>
          </div>
          <div className="workflow">
            {[
              { icon: FileText, title: "Submit content", text: "Text, an article link, a forwarded message, or screenshot.", color: "step-blue" },
              { icon: Languages, title: "Understand language", text: "Detect language and translate locally when configured.", color: "step-violet" },
              { icon: Search, title: "Extract & investigate", text: "Identify claims and search for related source material.", color: "step-amber" },
              { icon: BadgeCheck, title: "Review evidence", text: "See supporting, contradicting, and inconclusive signals.", color: "step-green" },
            ].map((step, index) => {
              const Icon = step.icon;
              return (
                <div className="workflow-step" key={step.title}>
                  <div className={`workflow-icon ${step.color}`}><Icon size={18} /></div>
                  <div className="workflow-copy"><div className="workflow-title">{step.title}</div><p>{step.text}</p></div>
                  <span className="workflow-number">0{index + 1}</span>
                </div>
              );
            })}
          </div>
        </article>

        <article className="panel activity-panel">
          <div className="panel-heading">
            <div><span className="section-kicker">ACTIVITY</span><h2>Recent verifications</h2></div>
            <span className="activity-icon"><Activity size={17} /></span>
          </div>
          <div className="empty-activity">
            <div className="empty-activity-icon"><Clock3 size={21} /></div>
            <strong>No saved activity</strong>
            <p>Verification history is not stored by this backend. Results stay in this browser session.</p>
            <button className="text-button" onClick={onStart}>Run your first check <ArrowRight size={14} /></button>
          </div>
        </article>
      </section>

      <section className="trust-strip">
        <div className="trust-icon"><ShieldCheck size={19} /></div>
        <div><strong>Evidence, not assumptions</strong><span>Classifier output is a text-pattern signal. It is never treated as a factual verdict.</span></div>
        <Link to="/about" className="trust-link">How we work <ArrowUpRight size={14} /></Link>
      </section>
    </>
  );
}

function VerifyPage({
  onComplete,
}: {
  onComplete: (session: VerificationSession, unified: UnifiedVerifyResponse | null) => void;
}) {
  const [mode, setMode] = useState<InputMode>("text");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [useUnified, setUseUnified] = useState(false);

  const maxUploadBytes = 8 * 1024 * 1024;
  const charCount = text.length;

  function selectImage(candidate: File | undefined) {
    if (!candidate) return;
    if (candidate.size > maxUploadBytes) {
      setFile(null);
      setError("The selected image exceeds the 8 MB upload limit.");
      return;
    }
    if (!/\.(png|jpe?g|webp)$/i.test(candidate.name)) {
      setFile(null);
      setError("Choose a PNG, JPG, or WEBP image.");
      return;
    }
    setFile(candidate);
    setError("");
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (mode === "image" && !file) {
      setError("Choose a PNG, JPG, or WEBP screenshot to continue.");
      return;
    }
    if (mode !== "image" && !text.trim()) {
      setError("Add a headline, article text, message, or public article URL first.");
      return;
    }
    if (mode === "image" && file && file.size > maxUploadBytes) {
      setError("The selected image exceeds the 8 MB upload limit.");
      return;
    }

    setLoading(true);
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 150_000);
    const submittedInput = mode === "image" ? file?.name || "Uploaded image" : text.trim();
    let processing: ProcessingResult | null = null;
    let verification: MultilingualResult | null = null;
    let unifiedResult: UnifiedVerifyResponse | null = null;
    let frontendError: string | null = null;

    async function runLegacyVerification() {
      if (!processing) {
        processing = mode === "image"
          ? await processImage(file!, controller.signal)
          : await processText(
              text.trim(),
              mode === "url" ? "url" : mode === "forwarded" ? "forwarded" : "text",
              controller.signal,
            );
      }

      if (processing.processing_status !== "processed") {
        frontendError = processing.error || `Input processing status: ${processing.processing_status}.`;
        return;
      }

      try {
        verification = await verifyMultilingual(
          processing.extracted_text,
          controller.signal,
          processing.source_url,
        );
      } catch (requestError) {
        if (requestError instanceof ApiError && isMultilingualResult(requestError.payload)) {
          verification = requestError.payload;
        } else {
          frontendError = requestError instanceof Error
            ? requestError.message
            : "Verification could not be completed.";
        }
      }
    }

    try {
      if (useUnified) {
        // Use new unified endpoint
        const request: UnifiedVerifyRequest = {
          input: mode === "image" ? file!.name : text.trim(),
          input_type: mode === "url" ? "url" : mode === "image" ? "image" : "text",
          options: {
            evidence_sources: ["gdelt", "google_factcheck"],
            time_window_days: 7,
            max_results: 10,
            include_claim_offsets: true,
            include_raw_evidence: false,
          },
        };

        // For image, we need to use multipart - fall back to legacy for now
        if (mode === "image" && file) {
          // Use legacy for image uploads until unified supports multipart
          processing = await processImage(file, controller.signal);
          if (processing.processing_status === "processed") {
            try {
              unifiedResult = await verifyUnified({
                input: processing.extracted_text,
                input_type: "text",
                options: request.options,
              }, controller.signal);
            } catch (requestError) {
              if (!(requestError instanceof ApiError) || requestError.status !== 404) {
                throw requestError;
              }
              await runLegacyVerification();
            }
          }
        } else {
          try {
            unifiedResult = await verifyUnified(request, controller.signal);
          } catch (requestError) {
            if (!(requestError instanceof ApiError) || requestError.status !== 404) {
              throw requestError;
            }
            await runLegacyVerification();
          }
        }
      } else {
        await runLegacyVerification();
      }
    } catch (requestError) {
      if (requestError instanceof ApiError && isProcessingResult(requestError.payload)) {
        processing = requestError.payload;
        frontendError = processing.error || requestError.message;
      } else {
        frontendError = requestError instanceof Error
          ? requestError.message
          : "The request could not be completed.";
      }
    } finally {
      window.clearTimeout(timer);
      setLoading(false);
      onComplete({
        submittedInput,
        inputMode: mode,
        processing,
        verification,
        frontendError,
        createdAt: new Date().toISOString(),
      }, unifiedResult);
    }
  }

  return (
    <>
      <PageIntro
        eyebrow="START A REVIEW"
        title="What would you like to verify?"
        description="Submit a story or message. TruthLens will extract text, identify its language, and review claims against available evidence."
        action={
          <>
            <span className="secure-label"><ShieldCheck size={15} /> Private session · Legacy verification active</span>
          </>
        }
      />

      <div className="verify-layout">
        <section className="panel verify-panel">
          <div className="input-tabs" role="tablist" aria-label="Choose input type">
            {([
              ["text", FileText, "Text / headline"],
              ["url", Globe2, "Article URL"],
              ["forwarded", Radio, "Forwarded"],
              ["image", FileImage, "Screenshot"],
            ] as const).map(([key, Icon, label]) => (
              <button
                type="button"
                role="tab"
                aria-selected={mode === key}
                className={`input-tab ${mode === key ? "input-tab-active" : ""}`}
                key={key}
                onClick={() => {
                  setMode(key);
                  setError("");
                }}
              >
                <Icon size={16} /> <span>{label}</span>
              </button>
            ))}
          </div>

          <form onSubmit={submit}>
            {mode === "image" ? (
              <div
                className={`drop-zone ${file ? "drop-zone-selected" : ""}`}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  selectImage(event.dataTransfer.files[0]);
                }}
              >
                <input
                  aria-label="Upload a news screenshot"
                  className="file-input"
                  type="file"
                  accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
                  onChange={(event) => selectImage(event.target.files?.[0])}
                />
                <div className="drop-icon"><Upload size={23} /></div>
                {file ? (
                  <>
                    <strong>{file.name}</strong>
                    <span>{formatBytes(file.size)} · Click to choose another image</span>
                    <button className="remove-file" type="button" onClick={(event) => { event.stopPropagation(); setFile(null); }}>
                      <X size={14} /> Remove
                    </button>
                  </>
                ) : (
                  <>
                    <strong>Drop a screenshot here, or browse files</strong>
                    <span>PNG, JPG, or WEBP · Maximum 8 MB</span>
                    <span className="drop-hint">Local OCR must be configured on the backend.</span>
                  </>
                )}
              </div>
            ) : (
              <label className="field-label" htmlFor="news-input">
                {mode === "url" ? "Public article or post URL" : mode === "forwarded" ? "Copied WhatsApp or Telegram message" : "News text or headline"}
                {mode === "url" ? (
                  <input
                    id="news-input"
                    className="text-input"
                    type="url"
                    placeholder="https://news-site.example/article"
                    value={text}
                    onChange={(event) => setText(event.target.value)}
                    maxLength={100_000}
                    required
                  />
                ) : (
                  <textarea
                    id="news-input"
                    className="text-area"
                    placeholder={mode === "forwarded"
                      ? "Paste the forwarded message exactly as received…"
                      : "Paste a headline or article text to begin…"}
                    value={text}
                    onChange={(event) => setText(event.target.value)}
                    maxLength={100_000}
                    rows={9}
                    required
                  />
                )}
              </label>
            )}

            {error && <div className="inline-error" role="alert"><CircleHelp size={16} />{error}</div>}
            <div className="form-meta">
              <span>{mode === "url" ? "Only public, static pages can be read. Private destinations are blocked." : mode === "image" ? "Uploaded images are processed locally by the configured OCR service." : "Your submission is sent to your configured TruthLens backend."}</span>
              {mode !== "image" && mode !== "url" && <span>{charCount.toLocaleString()} / 100,000</span>}
            </div>
            <div className="form-divider" />
            <div className="submit-row">
              <span className="submit-disclaimer"><Shield size={14} /> No verdict without evidence</span>
              <button className="button button-primary" type="submit" disabled={loading}>
                {loading ? <><LoaderCircle className="spin" size={16} /> Reviewing…</> : <>Analyze news <ArrowRight size={16} /></>}
              </button>
            </div>
          </form>
        </section>

        <aside className="verify-aside">
          <div className="panel process-card">
            <span className="section-kicker">YOUR REVIEW FLOW</span>
            <h2>What happens next?</h2>
            <div className="mini-flow">
              <MiniStep number="01" title="Extract" text="Read submitted text or accessible page content." />
              <MiniStep number="02" title="Detect & translate" text="Language detection; local translation when available." />
              <MiniStep number="03" title="Analyze claims" text="Classifier signal, factual claims, and evidence search." />
              <MiniStep number="04" title="Show results" text="Evidence and uncertainty presented separately." last />
            </div>
          </div>
          <div className="note-card">
            <ShieldCheck size={17} />
            <p><strong>A careful distinction</strong> The AI classifier detects writing patterns. Only supplied source evidence informs the claim verdict.</p>
          </div>
        </aside>
      </div>
    </>
  );
}

function MiniStep({
  number,
  title,
  text,
  last,
}: {
  number: string;
  title: string;
  text: string;
  last?: boolean;
}) {
  return (
    <div className={`mini-step ${last ? "mini-step-last" : ""}`}>
      <span className="mini-step-number">{number}</span>
      <div><strong>{title}</strong><p>{text}</p></div>
    </div>
  );
}

function ResultsPage({ session, unifiedResult }: { session: VerificationSession | null; unifiedResult: UnifiedVerifyResponse | null }) {
  if (!session && !unifiedResult) {
    return (
      <div className="empty-results panel">
        <div className="empty-activity-icon"><FileCheck2 size={23} /></div>
        <h1>No verification in this session</h1>
        <p>Results are kept only in the current browser session and are not saved to a backend history.</p>
        <Link className="button button-primary" to="/verify">Start a verification <ArrowRight size={16} /></Link>
      </div>
    );
  }

  // Use unified result if available, otherwise fall back to legacy
  if (unifiedResult) {
    return <UnifiedResultsPage result={unifiedResult} />;
  }

  const verification = session?.verification;
  const pipeline = verification?.pipeline;
  return (
    <>
      <PageIntro
        eyebrow="REVIEW SUMMARY"
        title="Verification results"
        description="Input extraction, language processing, classifier signals, and evidence assessments are shown as separate steps."
        action={<Link to="/verify" className="button button-secondary">New verification <ArrowRight size={15} /></Link>}
      />
      <div className="results-stack">
        {session?.frontendError && <div className="result-alert" role="alert"><CircleHelp size={18} /><div><strong>Review could not continue</strong><span>{session.frontendError}</span></div></div>}
        {session?.processing && (
          <section className="panel result-card">
            <ResultSectionHeader icon={FileText} label="01 · SUBMITTED CONTENT" title="Original content" />
            <div className="original-meta">
              <span className="soft-chip">{formatInputType(session.inputMode)}</span>
              {safeExternalUrl(session.processing.source_url) && <a className="source-link" href={safeExternalUrl(session.processing.source_url)!} target="_blank" rel="noreferrer">{session.processing.source_url}<ArrowUpRight size={13} /></a>}
            </div>
            <div className="content-block">
              <span className="content-label">SUBMITTED</span>
              <p>{session.inputMode === "image" ? `Image upload: ${session.submittedInput}` : session.submittedInput}</p>
            </div>
            {session.processing.extracted_text && (
              <div className="content-block extracted-block">
                <span className="content-label">EXTRACTED TEXT</span>
                <p>{session.processing.extracted_text}</p>
              </div>
            )}
            {session.processing.warnings.map((warning) => <p className="result-warning" key={warning}><CircleHelp size={14} />{warning}</p>)}
          </section>
        )}

        {verification && (
          <>
            <section className="panel result-card">
              <ResultSectionHeader icon={Languages} label="02 · LANGUAGE" title="Language & translation" />
              <div className="language-result-grid">
                <div className="language-result">
                  <span className="content-label">DETECTED LANGUAGE</span>
                  <strong>{verification.language_detection.language_name} <span>({verification.language_detection.language_code})</span></strong>
                  <small>{verification.language_detection.detection_status === "detected" ? "Detected by local language analysis" : verification.language_detection.detection_status}</small>
                  {verification.language_detection.detection_confidence !== null && <small>Detection score: {(verification.language_detection.detection_confidence * 100).toFixed(1)}% · heuristic</small>}
                </div>
                <div className="language-result">
                  <span className="content-label">TRANSLATION STATUS</span>
                  <strong>{translationLabel(verification.translation_status)}</strong>
                  <small>{verification.translated_text ? "English translation used for evidence analysis" : pipeline ? "Original text preserved and searched; language limitations are noted in the verdict." : "Verification could not be completed."}</small>
                </div>
              </div>
              {verification.translated_text && (
                <div className="content-block translated-block">
                  <span className="content-label">ENGLISH TRANSLATION · AUDIT COPY</span>
                  <p>{verification.translated_text}</p>
                </div>
              )}
              {verification.error && <p className="result-warning"><CircleHelp size={14} />{verification.error}</p>}
              {verification.warnings.map((warning) => <p className="result-warning" key={warning}><CircleHelp size={14} />{warning}</p>)}
            </section>

            {pipeline && (
              <>
                <section className="panel result-card final-verdict-card" aria-live="polite">
                  <ResultSectionHeader icon={Shield} label="03 · FINAL EVIDENCE VERDICT" title="Verification verdict" />
                  <div className="final-verdict-summary">
                    <span className={`verdict-pill final-verdict-pill ${verdictClass(pipeline.final_verdict)}`}>
                      {pipeline.final_verdict}
                    </span>
                    <div className="final-verdict-confidence">
                      <span className="content-label">CONFIDENCE LEVEL</span>
                      <strong>{pipeline.confidence === null ? "Not established" : `${(pipeline.confidence * 100).toFixed(0)}%`}</strong>
                      {pipeline.confidence !== null && <small>Heuristic estimate, not a calibrated probability</small>}
                    </div>
                  </div>
                  <p className="final-verdict-explanation">{pipeline.explanation}</p>
                </section>
                {pipeline.classifier && (
                  <section className="panel result-card classifier-card">
                    <ResultSectionHeader icon={Activity} label="04 · CLASSIFIER SIGNAL" title="Text-pattern prediction" />
                    <div className="classifier-result">
                      <div className="classifier-prediction">
                        <span className="content-label">PREDICTION</span>
                        <strong>{pipeline.classifier.prediction}</strong>
                      </div>
                      <div className="classifier-explanation">
                        <span>{pipeline.classifier.classifier}</span>
                        <p>{pipeline.classifier.explanation}</p>
                        <b><Shield size={13} /> This is not a factual verdict.</b>
                      </div>
                    </div>
                  </section>
                )}
                <section className="result-claims">
                  <div className="panel-heading claims-heading">
                    <div><span className="section-kicker">05 · CLAIM REVIEW</span><h2>{pipeline.claims.length} factual {pipeline.claims.length === 1 ? "claim" : "claims"} extracted</h2></div>
                    <span className="subtle-count">Evidence-led assessment</span>
                  </div>
                  {pipeline.claims.length === 0 ? (
                    <div className="panel no-claims"><FileText size={19} /><div><strong>No extractable factual claims</strong><p>The sentence-based extractor did not identify a candidate claim in this text.</p></div></div>
                  ) : (
                    <div className="claim-list">
                      {pipeline.claims.map((claim) => {
                        const assessment = pipeline.claim_assessments.find((item) => item.claim_id === claim.claim_id);
                        return <ClaimCard key={claim.claim_id} assessment={assessment} claimText={claim.claim_text} />;
                      })}
                    </div>
                  )}
                </section>
              </>
            )}
          </>
        )}
        {!session?.processing && !verification && !session?.frontendError && (
          <div className="panel no-claims"><LoaderCircle size={19} /><div><strong>No result data</strong><p>Start a new verification to review content.</p></div></div>
        )}
      </div>
    </>
  );
}

function UnifiedResultsPage({ result }: { result: UnifiedVerifyResponse }) {
  return (
    <>
      <PageIntro
        eyebrow="REVIEW SUMMARY"
        title="Verification results"
        description="Unified verification: input extraction, language processing, and evidence assessments."
        action={<Link to="/verify" className="button button-secondary">New verification <ArrowRight size={15} /></Link>}
      />
      <div className="results-stack">
        <section className="panel result-card">
          <ResultSectionHeader icon={FileText} label="01 · SUBMITTED CONTENT" title="Original content" />
          <div className="original-meta">
            <span className="soft-chip">{result.input_type}</span>
            {safeExternalUrl(result.original_input) && <a className="source-link" href={safeExternalUrl(result.original_input)!} target="_blank" rel="noreferrer">{result.original_input}<ArrowUpRight size={13} /></a>}
          </div>
          <div className="content-block">
            <span className="content-label">SUBMITTED</span>
            <p>{result.original_input}</p>
          </div>
          <div className="content-block extracted-block">
            <span className="content-label">EXTRACTED TEXT</span>
            <p>{result.extracted_text}</p>
          </div>
          {result.warnings.map((warning) => <p className="result-warning" key={warning}><CircleHelp size={14} />{warning}</p>)}
        </section>

        <section className="panel result-card">
          <ResultSectionHeader icon={Languages} label="02 · LANGUAGE" title="Language & translation" />
          <div className="language-result-grid">
            <div className="language-result">
              <span className="content-label">DETECTED LANGUAGE</span>
              <strong>{result.language_detection.language_name} <span>({result.language_detection.language_code})</span></strong>
              <small>{result.language_detection.status === "detected" ? "Detected by local language analysis" : result.language_detection.status}</small>
              {result.language_detection.confidence !== null && <small>Detection score: {(result.language_detection.confidence * 100).toFixed(1)}% · heuristic</small>}
              {result.language_detection.warning && <p className="result-warning"><CircleHelp size={14} />{result.language_detection.warning}</p>}
            </div>
            {result.translation && (
              <div className="language-result">
                <span className="content-label">TRANSLATION STATUS</span>
                <strong>{translationLabel(result.translation.translation_status)}</strong>
                <small>{result.translation.translated_text ? "English translation used for evidence analysis" : "Original text preserved and searched; language limitations are noted in the verdict."}</small>
              </div>
            )}
          </div>
          {result.translation?.translated_text && (
            <div className="content-block translated-block">
              <span className="content-label">ENGLISH TRANSLATION · AUDIT COPY</span>
              <p>{result.translation.translated_text}</p>
            </div>
          )}
          {result.translation?.error && <p className="result-warning"><CircleHelp size={14} />{result.translation.error}</p>}
          {result.translation?.warnings.map((warning) => <p className="result-warning" key={warning}><CircleHelp size={14} />{warning}</p>)}
        </section>

        <section className="panel result-card final-verdict-card" aria-live="polite">
          <ResultSectionHeader icon={Shield} label="03 · FINAL EVIDENCE VERDICT" title="Verification verdict" />
          <div className="final-verdict-summary">
            <span className={`verdict-pill final-verdict-pill ${verdictClass(result.overall_verdict)}`}>
              {result.overall_verdict}
            </span>
            <div className="final-verdict-confidence">
              <span className="content-label">CONFIDENCE LEVEL</span>
              <strong>{result.overall_confidence === null ? "Not established" : `${(result.overall_confidence * 100).toFixed(0)}%`}</strong>
              {result.overall_confidence !== null && <small>Heuristic estimate, not a calibrated probability</small>}
            </div>
          </div>
          <p className="final-verdict-explanation">{result.overall_explanation}</p>
        </section>

        <section className="result-claims">
          <div className="panel-heading claims-heading">
            <div><span className="section-kicker">04 · CLAIM REVIEW</span><h2>{result.claims.length} factual {result.claims.length === 1 ? "claim" : "claims"} extracted</h2></div>
            <span className="subtle-count">Evidence-led assessment</span>
          </div>
          {result.claims.length === 0 ? (
            <div className="panel no-claims"><FileText size={19} /><div><strong>No extractable factual claims</strong><p>The sentence-based extractor did not identify a candidate claim in this text.</p></div></div>
          ) : (
            <div className="claim-list">
              {result.claims.map((claim) => (
                <UnifiedClaimCard key={claim.claim_id} claim={claim} />
              ))}
            </div>
          )}
        </section>
      </div>
    </>
  );
}

function UnifiedClaimCard({ claim }: { claim: ClaimResult }) {
  const [expanded, setExpanded] = useState(true);

  return (
    <article className="panel claim-card">
      <button className="claim-card-toggle" onClick={() => setExpanded(!expanded)} aria-expanded={expanded}>
        <span className="claim-number">{claim.claim_id.slice(-2).padStart(2, "0")}</span>
        <span className="claim-main"><span className="content-label">FACTUAL CLAIM</span><strong>{claim.claim_text}</strong></span>
        <span className={`verdict-pill ${verdictClass(claim.assessment?.verdict || "INSUFFICIENT EVIDENCE")}`}>
          {claim.assessment?.verdict || "NOT ANALYZED"}
        </span>
        <ChevronDown className={expanded ? "chevron-open" : ""} size={18} />
      </button>
      {expanded && claim.assessment && (
        <div className="claim-card-body">
          <div className="verdict-explanation">
            <div><span className="content-label">EVIDENCE ASSESSMENT</span><p>{claim.assessment.explanation}</p></div>
            {claim.assessment.confidence !== null && <div className="confidence-box"><strong>{(claim.assessment.confidence * 100).toFixed(0)}%</strong><span>Heuristic estimate<br />not calibrated probability</span></div>}
          </div>
          <div className="evidence-groups">
            <UnifiedEvidenceGroup title="Supporting evidence" icon={ArrowUpRight} items={claim.evidence.filter(e => e.stance === "SUPPORTS")} tone="support" />
            <UnifiedEvidenceGroup title="Contradicting evidence" icon={ArrowDownRight} items={claim.evidence.filter(e => e.stance === "CONTRADICTS")} tone="contradict" />
            <UnifiedEvidenceGroup title="Mixed evidence" icon={CircleHelp} items={claim.evidence.filter(e => e.stance === "MIXED")} tone="conflicting" />
            <UnifiedEvidenceGroup title="Neutral / insufficient" icon={CircleHelp} items={claim.evidence.filter(e => e.stance === "NEUTRAL" || e.stance === "INSUFFICIENT")} tone="neutral" />
          </div>
          {claim.assessment.limitations.length > 0 && (
            <details className="limitations">
              <summary>Limitations ({claim.assessment.limitations.length})</summary>
              <ul>{claim.assessment.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>
            </details>
          )}
        </div>
      )}
    </article>
  );
}

function UnifiedEvidenceGroup({
  title,
  icon: Icon,
  items,
  tone,
}: {
  title: string;
  icon: typeof ArrowUpRight;
  items: EvidenceRecord[];
  tone: "support" | "contradict" | "conflicting" | "neutral";
}) {
  return (
    <div className={`evidence-group evidence-${tone}`}>
      <div className="evidence-group-title"><Icon size={15} /><strong>{title}</strong><span>{items.length}</span></div>
      {items.length === 0 ? <p className="evidence-empty">No {tone === "support" ? "supporting" : tone === "contradict" ? "contradicting" : tone === "conflicting" ? "mixed" : "neutral"} items supplied.</p> : (
        <div className="evidence-items">
          {items.map((item, index) => (
            <div className="evidence-item" key={item.evidence_id || `${item.url}-${index}`}>
              <div className="evidence-source-row">
                <strong>{item.publisher || item.domain || "Source not identified"}</strong>
              </div>
              <span className="evidence-stance">
                {tone === "support" ? "Supports claim" : tone === "contradict" ? "Contradicts claim" : tone === "conflicting" ? "Mixed signal" : "Neutral / insufficient"}
              </span>
              {safeExternalUrl(item.url) && (
                <a
                  className="evidence-source-url"
                  href={safeExternalUrl(item.url)!}
                  target="_blank"
                  rel="noreferrer"
                >
                  {item.url}<ArrowUpRight size={12} />
                </a>
              )}
              {item.title && <div className="evidence-title">{item.title}</div>}
              {item.snippet && <p>{item.snippet}</p>}
              <span className="evidence-domain">{item.domain || "Domain unavailable"}{item.published_at ? ` · ${item.published_at}` : ""}</span>
              <span className="evidence-meta">Connector: {item.connector} · Status: {item.connector_status} · Relevance: {(item.relevance_score * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ResultSectionHeader({
  icon: Icon,
  label,
  title,
}: {
  icon: typeof FileText;
  label: string;
  title: string;
}) {
  return <div className="result-section-header"><span className="result-section-icon"><Icon size={17} /></span><div><span className="section-kicker">{label}</span><h2>{title}</h2></div></div>;
}

import type { LegacyClaimAssessment } from "./types";

// Legacy assessment adapter - converts LegacyClaimAssessment to ClaimAssessment-compatible shape
function adaptLegacyAssessment(legacy: LegacyClaimAssessment): ClaimAssessment {
  return {
    verdict: legacy.analysis.verdict as ClaimAssessment["verdict"],
    confidence: legacy.analysis.confidence,
    confidence_type: legacy.analysis.confidence_type,
    explanation: legacy.analysis.explanation,
    limitations: legacy.analysis.limitations,
    supporting_evidence: [],
    contradicting_evidence: [],
    mixed_evidence: [],
    neutral_evidence: [],
    insufficient_evidence: [],
    sources_used: [],
  };
}

function ClaimCard({
  assessment,
  claimText,
}: {
  assessment: LegacyClaimAssessment | undefined;
  claimText: string;
}) {
  const adapted = assessment ? adaptLegacyAssessment(assessment) : undefined;
  const [expanded, setExpanded] = useState(true);

  return (
    <article className="panel claim-card">
      <button className="claim-card-toggle" onClick={() => setExpanded(!expanded)} aria-expanded={expanded}>
        <span className="claim-number">{assessment?.claim_id ? String(assessment.claim_id).padStart(2, "0") : "—"}</span>
        <span className="claim-main"><span className="content-label">FACTUAL CLAIM</span><strong>{claimText}</strong></span>
        <span className={`verdict-pill ${verdictClass(adapted?.verdict)}`}>{adapted?.verdict || "NOT ANALYZED"}</span>
        <ChevronDown className={expanded ? "chevron-open" : ""} size={18} />
      </button>
      {expanded && adapted && (
        <div className="claim-card-body">
          <div className="verdict-explanation">
            <div><span className="content-label">EVIDENCE ASSESSMENT</span><p>{adapted.explanation}</p></div>
            {adapted.confidence !== null && <div className="confidence-box"><strong>{(adapted.confidence * 100).toFixed(0)}%</strong><span>Heuristic estimate<br />not calibrated probability</span></div>}
          </div>
          <div className="evidence-groups">
            <EvidenceGroup title="Supporting evidence" icon={ArrowUpRight} items={assessment?.analysis.supporting_evidence ?? []} tone="support" />
            <EvidenceGroup title="Contradicting evidence" icon={ArrowDownRight} items={assessment?.analysis.contradicting_evidence ?? []} tone="contradict" />
            <EvidenceGroup title="Conflicting evidence" icon={CircleHelp} items={assessment?.analysis.conflicting_evidence ?? []} tone="conflicting" />
            <EvidenceGroup title="Neutral / insufficient" icon={CircleHelp} items={assessment?.analysis.neutral_evidence ?? []} tone="neutral" />
          </div>
          {assessment?.retrieval_status && assessment.retrieval_status !== "completed" && (
            <div className="retrieval-note">
              <Radio size={14} />
              <div>
                <strong>Web evidence: {retrievalStatusLabel(assessment.retrieval_status)}</strong>
                <p>{retrievalStatusExplanation(assessment.retrieval_status)}</p>
                {assessment.query && <small>Search query: “{assessment.query}”</small>}
                {assessment.source_errors.map((sourceError, index) => (
                  <small key={`${sourceError.source}-${index}`}>
                    {sourceError.source}: {retrievalErrorLabel(sourceError.error)}
                  </small>
                ))}
              </div>
            </div>
          )}
          {adapted.limitations.length > 0 && (
            <details className="limitations">
              <summary>Limitations ({adapted.limitations.length})</summary>
              <ul>{adapted.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>
            </details>
          )}
        </div>
      )}
    </article>
  );
}

function retrievalStatusLabel(status: string): string {
  switch (status) {
    case "unavailable":
      return "unavailable";
    case "no_results":
      return "no results";
    case "partial":
      return "partially available";
    default:
      return status;
  }
}

function retrievalStatusExplanation(status: string): string {
  if (status === "unavailable") {
    return "Web evidence could not be retrieved. No search-result evidence is available for this claim.";
  }
  if (status === "no_results") {
    return "The web search completed but returned no sources for this claim.";
  }
  return "Some results or webpage content could not be retrieved. Treat the available evidence cautiously.";
}

function retrievalErrorLabel(error: string): string {
  const labels: Record<string, string> = {
    timeout: "request timed out",
    tls_error: "TLS/SSL connection failed",
    rate_limited: "search service rate-limited the request",
    http_error: "search service returned an HTTP error",
    network_error: "network connection failed",
    malformed_response: "search service returned an invalid response",
    response_too_large: "search response exceeded the size limit",
    content_unavailable: "webpage content was unavailable",
    article_content_unavailable: "article text could not be retrieved",
    source_unavailable: "source was unavailable",
  };
  return labels[error] || "source could not be retrieved";
}

function EvidenceGroup({
  title,
  icon: Icon,
  items,
  tone,
}: {
  title: string;
  icon: typeof ArrowUpRight;
  items: Array<{
    evidence_id?: string | null;
    source_name?: string | null;
    source_domain?: string | null;
    source_url?: string | null;
    title?: string | null;
    snippet?: string | null;
    page_content?: string | null;
    published_date?: string | null;
  }>;
  tone: "support" | "contradict" | "conflicting" | "neutral";
}) {
  return (
    <div className={`evidence-group evidence-${tone}`}>
      <div className="evidence-group-title"><Icon size={15} /><strong>{title}</strong><span>{items.length}</span></div>
      {items.length === 0 ? <p className="evidence-empty">No {tone === "support" ? "supporting" : tone === "contradict" ? "contradicting" : tone === "conflicting" ? "conflicting" : "neutral"} items supplied.</p> : (
        <div className="evidence-items">
          {items.map((item, index) => (
            <div className="evidence-item" key={item.evidence_id || `${item.source_url}-${index}`}>
              <div className="evidence-source-row">
                <strong>{item.source_name || item.source_domain || "Source not identified"}</strong>
              </div>
              <span className="evidence-stance">
                {tone === "support" ? "Supports claim" : tone === "contradict" ? "Contradicts claim" : tone === "conflicting" ? "Conflicting signal" : "Neutral / insufficient"}
              </span>
              {safeExternalUrl(item.source_url) && (
                <a
                  className="evidence-source-url"
                  href={safeExternalUrl(item.source_url)!}
                  target="_blank"
                  rel="noreferrer"
                >
                  {item.source_url}<ArrowUpRight size={12} />
                </a>
              )}
              {item.title && <div className="evidence-title">{item.title}</div>}
              {(item.snippet || item.page_content) && (
                <p>{item.snippet || `${item.page_content?.slice(0, 500)}${(item.page_content?.length || 0) > 500 ? "…" : ""}`}</p>
              )}
              <span className="evidence-domain">{item.source_domain || "Domain unavailable"}{item.published_date ? ` · ${item.published_date}` : ""}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function HistoryPage() {
  const [history, setHistory] = useState<VerificationHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedDetail, setSelectedDetail] = useState<VerificationDetail | null>(null);

  async function loadHistory() {
    setLoading(true);
    setError("");
    try {
      const result = await listVerifications(50, 0);
      setHistory(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load history");
    } finally {
      setLoading(false);
    }
  }

  async function loadDetail(id: string) {
    try {
      const detail = await getVerification(id);
      setSelectedDetail(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load detail");
    }
  }

  async function handleDelete(id: string) {
    if (!window.confirm("Delete this verification record?")) return;
    try {
      await deleteVerification(id);
      setHistory(prev => prev.filter(h => h.id !== id));
      if (selectedDetail?.id === id) setSelectedDetail(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete");
    }
  }

  useEffect(() => { loadHistory(); }, []);

  if (selectedDetail) {
    return (
      <>
        <PageIntro
          eyebrow="VERIFICATION DETAIL"
          title="Verification history detail"
          description="Full verification record from database."
          action={<button className="button button-secondary" onClick={() => setSelectedDetail(null)}><ArrowRight size={14} /> Back to history</button>}
        />
        <VerificationDetailView detail={selectedDetail} onDelete={() => handleDelete(selectedDetail.id)} />
      </>
    );
  }

  return (
    <>
      <PageIntro
        eyebrow="YOUR ACTIVITY"
        title="Verification history"
        description="Review past verifications from the database."
        action={<button className="button button-secondary" onClick={loadHistory} disabled={loading}>{loading ? <LoaderCircle className="spin" size={14} /> : <Activity size={14} />} Refresh</button>}
      />
      {error && <div className="inline-error" role="alert"><CircleHelp size={16} />{error}</div>}
      <section className="panel history-panel">
        {loading ? (
          <div className="history-loading"><LoaderCircle size={24} /><span>Loading history…</span></div>
        ) : history.length === 0 ? (
          <div className="empty-activity">
            <div className="empty-activity-icon"><Clock3 size={21} /></div>
            <strong>No history yet</strong>
            <p>Verification records will appear here after using the unified verification endpoint.</p>
            <Link to="/verify" className="button button-primary">Start a verification <ArrowRight size={15} /></Link>
          </div>
        ) : (
          <div className="history-list">
            {history.map((item) => (
              <article className="history-item" key={item.id}>
                <div className="history-main">
                  <span className={`verdict-pill ${verdictClass(item.overall_verdict)}`}>{item.overall_verdict}</span>
                  <div className="history-info">
                    <strong>{item.original_input.slice(0, 100)}{item.original_input.length > 100 ? "…" : ""}</strong>
                    <span className="history-meta">{item.input_type} · {new Date(item.created_at).toLocaleString()}</span>
                  </div>
                </div>
                <div className="history-actions">
                  <span className="confidence-badge">{item.overall_confidence !== null ? `${(item.overall_confidence * 100).toFixed(0)}%` : "N/A"}</span>
                  <button className="icon-button" onClick={() => loadDetail(item.id)} title="View details"><FileCheck2 size={16} /></button>
                  <button className="icon-button icon-button-danger" onClick={() => handleDelete(item.id)} title="Delete"><Trash2 size={16} /></button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  );
}

function VerificationDetailView({ detail, onDelete }: { detail: VerificationDetail; onDelete: () => void }) {
  return (
    <div className="detail-view">
      <section className="panel result-card">
        <div className="detail-header">
          <div>
            <span className="section-kicker">VERIFICATION RECORD</span>
            <h2>{detail.original_input.slice(0, 120)}{detail.original_input.length > 120 ? "…" : ""}</h2>
          </div>
          <div className="detail-actions">
            <span className={`verdict-pill ${verdictClass(detail.overall_verdict || "INSUFFICIENT EVIDENCE")}`}>
              {detail.overall_verdict || "INSUFFICIENT EVIDENCE"}
            </span>
            <button className="icon-button icon-button-danger" onClick={onDelete} title="Delete"><Trash2 size={16} /></button>
          </div>
        </div>
        <div className="detail-meta">
          <span>ID: {detail.id}</span>
          <span>Created: {new Date(detail.created_at).toLocaleString()}</span>
          <span>Input type: {detail.input_type}</span>
          <span>Status: {detail.status}</span>
        </div>
        {detail.overall_explanation && <p className="detail-explanation">{detail.overall_explanation}</p>}
        {detail.warnings.map((w) => <p className="result-warning" key={w}><CircleHelp size={14} />{w}</p>)}
      </section>

      {detail.claims.length > 0 && (
        <section className="result-claims">
          <div className="panel-heading claims-heading">
            <div><span className="section-kicker">CLAIMS</span><h2>{detail.claims.length} claim(s)</h2></div>
          </div>
          <div className="claim-list">
            {detail.claims.map((claim) => (
              <article className="panel claim-card" key={claim.id}>
                <div className="claim-header">
                  <span className="claim-number">{String(claim.claim_index + 1).padStart(2, "0")}</span>
                  <strong>{claim.claim_text}</strong>
                  <span className={`verdict-pill ${verdictClass(claim.assessment_verdict || "INSUFFICIENT EVIDENCE")}`}>
                    {claim.assessment_verdict || "NOT ANALYZED"}
                  </span>
                </div>
                {claim.assessment_explanation && <p className="claim-explanation">{claim.assessment_explanation}</p>}
                {claim.assessment_confidence !== null && <div className="confidence-box"><strong>{(claim.assessment_confidence * 100).toFixed(0)}%</strong></div>}
                {claim.evidence.length > 0 && (
                  <div className="evidence-groups">
                    <EvidenceGroup title="Evidence" icon={ArrowUpRight} items={claim.evidence.map(e => ({
                      evidence_id: e.id,
                      source_name: e.publisher,
                      source_domain: e.domain,
                      source_url: e.url,
                      title: e.title,
                      snippet: e.snippet,
                      page_content: null,
                      published_date: e.published_at,
                    }))} tone="support" />
                  </div>
                )}
              </article>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function AboutPage() {
  return (
    <>
      <PageIntro eyebrow="ABOUT THE PROJECT" title="A careful lens on the news" description="TruthLens AI is a government-grade evidence verification platform for exploring news claims alongside retrieved source material." />
      <div className="about-grid">
        <section className="panel about-main">
          <div className="about-mark"><ShieldCheck size={24} /></div>
          <h2>Designed to distinguish signals from evidence.</h2>
          <p>TruthLens combines a TF-IDF + LinearSVC text classifier with claim extraction, public evidence retrieval, and a cautious rule-based assessment. These parts answer different questions and are displayed separately.</p>
          <div className="about-callout"><Shield size={17} /><span>The classifier predicts text patterns. It does not decide whether a news story is true.</span></div>
          <h3>What it can do</h3>
          <ul className="feature-list">
            <li><Check size={16} /> Process text, headlines, public article URLs, forwarded text, and screenshots.</li>
            <li><Check size={16} /> Detect English and eleven supported Indian languages.</li>
            <li><Check size={16} /> Extract candidate factual sentences and search for related source material.</li>
            <li><Check size={16} /> Show support, contradiction, uncertainty, source links, and limitations.</li>
          </ul>
        </section>
        <section className="panel limitations-panel">
          <span className="section-kicker">IMPORTANT LIMITATIONS</span>
          <h2>What to keep in mind</h2>
          <div className="limitation-row"><span>01</span><p>Translation requires optional locally installed Argos models. Unavailable translation stops multilingual verification.</p></div>
          <div className="limitation-row"><span>02</span><p>Evidence search depends on the public GDELT service and can be unavailable or incomplete.</p></div>
          <div className="limitation-row"><span>03</span><p>OCR requires the local Tesseract executable. Extraction and language detection may make mistakes.</p></div>
          <div className="limitation-row"><span>04</span><p>Rule-based verdicts are cautious assessments of supplied snippets, not expert or legal determinations.</p></div>
          <div className="limitation-row"><span>05</span><p>No user account, database-backed history, or persistent verification records exist.</p></div>
        </section>
      </div>
    </>
  );
}

function StatusPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [checkedAt, setCheckedAt] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function refresh() {
    setLoading(true);
    setError("");
    try {
      const result = await getHealth();
      setHealth(result);
      setCheckedAt(new Date().toISOString());
    } catch (requestError) {
      setHealth(null);
      setError(requestError instanceof Error ? requestError.message : "The API health check failed.");
      setCheckedAt(new Date().toISOString());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void refresh(); }, []);

  return (
    <>
      <PageIntro
        eyebrow="SYSTEM MONITORING"
        title="API status"
        description="Live health is checked using the backend's /api/health endpoint. Other optional services are reported only when their actual request is made."
        action={<button className="button button-secondary" onClick={() => void refresh()} disabled={loading}>{loading ? <LoaderCircle className="spin" size={15} /> : <Activity size={15} />} Refresh</button>}
      />
      <section className="panel status-panel">
        <div className="status-overview">
          <div className={`status-emblem ${health ? "status-ok" : "status-down"}`}>{loading ? <LoaderCircle className="spin" size={25} /> : health ? <Check size={25} /> : <X size={25} />}</div>
          <div><span className="section-kicker">BACKEND HEALTH</span><h2>{loading ? "Checking connection…" : health ? (health.status === "ok" ? "All systems reachable" : "Backend degraded") : "Backend unavailable"}</h2><p>{checkedAt ? `Last checked ${new Date(checkedAt).toLocaleTimeString()}` : "Waiting for first health check"}</p></div>
        </div>
        {error && <div className="inline-error status-error"><CircleHelp size={16} />{error}</div>}
        <div className="status-services">
          <ServiceRow name="FastAPI backend" detail={health ? `API version ${health.api_version}` : "GET /api/health"} state={health ? "available" : loading ? "checking" : "unavailable"} />
          <ServiceRow name="TF-IDF + LinearSVC artifacts" detail="Reported by classifier_available" state={health?.classifier_available ? "available" : loading ? "checking" : "unavailable"} />
          <ServiceRow name="Local translation" detail="Optional Argos models · checked when translating" state="on-demand" />
          <ServiceRow name="Image OCR" detail="Local Tesseract · checked when processing an image" state="on-demand" />
          <ServiceRow name="Public evidence retrieval" detail="External GDELT service · checked during claim review" state="on-demand" />
          <ServiceRow name="Google Fact Check API" detail="Optional · checked during evidence retrieval" state="on-demand" />
        </div>
        <div className="status-footnote"><Globe2 size={15} /> API base URL <code>{getApiBaseUrl()}</code></div>
      </section>
    </>
  );
}

function ServiceRow({
  name,
  detail,
  state,
}: {
  name: string;
  detail: string;
  state: "available" | "unavailable" | "checking" | "on-demand";
}) {
  const label = {
    available: "Available",
    unavailable: "Unavailable",
    checking: "Checking",
    "on-demand": "On demand",
  }[state];
  return <div className="service-row"><div className={`service-indicator service-${state}`} /><div className="service-copy"><strong>{name}</strong><span>{detail}</span></div><span className={`service-state state-${state}`}>{label}</span></div>;
}

function NotFound() {
  return <div className="panel empty-results"><div className="empty-activity-icon"><Search size={22} /></div><h1>Page not found</h1><p>This page is not part of the TruthLens workspace.</p><Link className="button button-primary" to="/">Back to overview</Link></div>;
}

function formatInputType(mode: InputMode): string {
  return { text: "Text / headline", forwarded: "Forwarded message", url: "Article URL", image: "Image upload" }[mode];
}

function translationLabel(status: string): string {
  return {
    translated: "Translated to English",
    not_required: "English · translation not required",
    unavailable: "Translation unavailable",
    uncertain: "Language uncertain",
    failed: "Translation failed",
    rejected: "Translation rejected",
  }[status] || status.replaceAll("_", " ");
}

function verdictClass(verdict?: string): string {
  if (!verdict) return "verdict-muted";
  if (verdict === "TRUE" || verdict === "REAL") return "verdict-true";
  if (verdict === "FALSE" || verdict === "FAKE") return "verdict-false";
  if (verdict === "MISLEADING") return "verdict-misleading";
  if (verdict === "PARTIALLY TRUE") return "verdict-partial";
  if (verdict === "NEEDS HUMAN REVIEW") return "verdict-human-review";
  return "verdict-insufficient";
}

function formatBytes(bytes: number): string {
  return bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(0)} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function safeExternalUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) {
      return null;
    }
    return url.href;
  } catch {
    return null;
  }
}

export default App;