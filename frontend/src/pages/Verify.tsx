// ============================================================
// TruthLens - Verify Page
// ============================================================

import { useState, useEffect, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  Search,
  Link as LinkIcon,
  Image,
  FileText,
  Mic,
  Send,
  Loader2,
  X,
  ChevronLeft,
  ChevronRight,
  CheckCircle,
  AlertCircle,
  Info,
  File,
  Globe,
  Camera,
  Type,
  ArrowRight,
  Shield,
  Eye,
  EyeOff,
  Download,
  Copy,
  Share2,
  Flag,
  History,
} from 'lucide-react';
import { useVerificationStore, useUIStore } from '../lib/stores';
import { verificationApi } from '../lib/api';
import {
  Button,
  Input,
  Textarea,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
  Badge,
  VerdictBadge,
  StanceBadge,
  SourceTypeBadge,
  Modal,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
  Progress,
  Tooltip,
} from '../components/ui';
import { cn, formatDateTime, getVerdictColor, getStanceColor, formatFileSize } from '../lib/utils';

type InputType = 'text' | 'url' | 'forwarded' | 'image' | 'audio';

const InputTypeIcons: Record<InputType, React.ComponentType<{ className?: string }>> = {
  text: Type,
  url: Globe,
  forwarded: Share2,
  image: Camera,
  audio: Mic,
};

const inputTypeConfig: Record<InputType, { label: string; description: string; color: string }> = {
  text: { label: 'Text', description: 'Paste or type text content to verify', color: 'blue' },
  url: { label: 'URL', description: 'Enter a webpage URL to extract and verify claims', color: 'green' },
  forwarded: { label: 'Forwarded', description: 'Verify forwarded messages (WhatsApp, Telegram, etc.)', color: 'purple' },
  image: { label: 'Image', description: 'Upload an image for OCR and verification', color: 'orange' },
  audio: { label: 'Audio', description: 'Upload audio for transcription and verification', color: 'red' },
};

export function Verify() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { verify, verifyUrl, verifyImage, verifyAudio, fetchHistory, clearCurrent, currentVerification, isVerifying, error } = useVerificationStore();
  const { addToast } = useUIStore();

  const [activeType, setActiveType] = useState<InputType>('text');
  const [textInput, setTextInput] = useState('');
  const [urlInput, setUrlInput] = useState('');
  const [forwardedInput, setForwardedInput] = useState('');
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [showResult, setShowResult] = useState(false);
  const [resultStep, setResultStep] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const audioInputRef = useRef<HTMLInputElement>(null);

  // Initialize from URL params
  useEffect(() => {
    const type = searchParams.get('type') as InputType;
    if (type && inputTypeConfig[type]) {
      setActiveType(type);
    }
  }, [searchParams]);

  const handleVerify = async () => {
    let success = false;
    setShowResult(true);
    setResultStep(0);

    try {
      switch (activeType) {
        case 'text':
        case 'forwarded':
          success = await verify({
            text: activeType === 'text' ? textInput : forwardedInput,
            source_url: activeType === 'text' ? undefined : undefined,
            language: 'auto',
          });
          break;
        case 'url':
          success = await verifyUrl(urlInput);
          break;
        case 'image':
          if (imageFile) {
            success = await verifyImage(imageFile);
          }
          break;
        case 'audio':
          if (audioFile) {
            success = await verifyAudio(audioFile);
          }
          break;
      }

      if (success) {
        addToast({ type: 'success', title: 'Verification Complete', message: 'Results are ready for review' });
        fetchHistory();
      }
    } catch (err) {
      addToast({ type: 'error', title: 'Verification Failed', message: err instanceof Error ? err.message : 'Unknown error' });
    }
  };

  const handleFileChange = (file: File | null, setter: (file: File | null) => void) => {
    if (file) {
      // Validate file type and size
      const maxSize = 10 * 1024 * 1024; // 10MB
      if (file.size > maxSize) {
        addToast({ type: 'error', title: 'File Too Large', message: 'Maximum file size is 10MB' });
        return;
      }
      setter(file);
    } else {
      setter(null);
    }
  };

  const clearForm = () => {
    setTextInput('');
    setUrlInput('');
    setForwardedInput('');
    setImageFile(null);
    setAudioFile(null);
    setShowResult(false);
    clearCurrent();
    if (fileInputRef.current) fileInputRef.current.value = '';
    if (audioInputRef.current) audioInputRef.current.value = '';
  };

  const canVerify = () => {
    switch (activeType) {
      case 'text':
        return textInput.trim().length >= 10;
      case 'url':
        return urlInput.trim().length > 0 && /^https?:\/\//.test(urlInput.trim());
      case 'forwarded':
        return forwardedInput.trim().length >= 10;
      case 'image':
        return imageFile !== null;
      case 'audio':
        return audioFile !== null;
    }
  };

  const result = currentVerification;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Verify Content</h1>
        <p className="text-gray-600 dark:text-gray-400 mt-1">
          Submit text, URLs, images, or audio for evidence-based fact verification
        </p>
      </div>

      {/* Input Type Tabs */}
      <Card variant="outlined" padding="none">
        <Tabs defaultValue={activeType} onValueChange={setActiveType} className="w-full">
          <TabsList className="grid grid-cols-5 p-1 bg-gray-50 dark:bg-gray-800/50">
            {(Object.keys(inputTypeConfig) as InputType[]).map((type) => {
              const Icon = InputTypeIcons[type];
              return (
                <TabsTrigger
                  key={type}
                  value={type}
                  className="flex flex-col items-center gap-1 py-3 px-2 text-sm data-[state=active]:bg-white data-[state=active]:shadow-sm data-[state=active]:text-gray-900 dark:data-[state=active]:text-white"
                >
                  <Icon className="w-5 h-5" />
                  <span>{inputTypeConfig[type].label}</span>
                </TabsTrigger>
              );
            })}
          </TabsList>
        </Tabs>
      </Card>

      {/* Input Form */}
      <Card variant="outlined">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', `bg-${inputTypeConfig[activeType].color}-100 dark:bg-${inputTypeConfig[activeType].color}-900/30`)}>
              {(() => {
                const Icon = InputTypeIcons[activeType];
                return <Icon className={cn('w-5 h-5', `text-${inputTypeConfig[activeType].color}-600 dark:text-${inputTypeConfig[activeType].color}-400`)} />;
              })()}
            </div>
            <div>
              <CardTitle className="text-lg">{inputTypeConfig[activeType].label} Verification</CardTitle>
              <p className="text-sm text-gray-500 dark:text-gray-400">{inputTypeConfig[activeType].description}</p>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Text Input */}
          {(activeType === 'text' || activeType === 'forwarded') && (
            <Textarea
              label={activeType === 'text' ? 'Text Content' : 'Forwarded Message'}
              placeholder={activeType === 'text' ? 'Paste the text you want to verify...' : 'Paste the forwarded message...'}
              value={activeType === 'text' ? textInput : forwardedInput}
              onChange={(e) => (activeType === 'text' ? setTextInput(e.target.value) : setForwardedInput(e.target.value))}
              rows={6}
              required
              minLength={10}
              helperText={`Minimum 10 characters • ${(activeType === 'text' ? textInput : forwardedInput).length} characters`}
            />
          )}

          {/* URL Input */}
          {activeType === 'url' && (
            <Input
              label="Website URL"
              placeholder="https://example.com/article"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              leftIcon={<LinkIcon className="w-5 h-5" />}
              required
              helperText="Enter a full URL including http:// or https://"
            />
          )}

          {/* Image Upload */}
          {activeType === 'image' && (
            <div className="space-y-3">
              <div
                className={cn(
                  'border-2 border-dashed rounded-xl p-8 text-center transition-colors',
                  imageFile ? 'border-green-500 bg-green-50 dark:bg-green-900/20' : 'border-gray-300 dark:border-gray-600 hover:border-blue-400 dark:hover:border-blue-600'
                )}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); }}
                onDrop={(e) => { e.preventDefault(); if (e.dataTransfer.files[0]) handleFileChange(e.dataTransfer.files[0], setImageFile); }}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={(e) => handleFileChange(e.target.files[0], setImageFile)}
                  className="hidden"
                />
                {imageFile ? (
                  <div className="flex items-center justify-center gap-4">
                    <div className="w-16 h-16 rounded-lg bg-gray-100 dark:bg-gray-800 flex items-center center overflow-hidden">
                      <img src={URL.createObjectURL(imageFile)} alt="Preview" className="w-full h-full object-cover" />
                    </div>
                    <div className="text-left">
                      <p className="font-medium text-gray-900 dark:text-white">{imageFile.name}</p>
                      <p className="text-sm text-gray-500 dark:text-gray-400">{formatFileSize(imageFile.size)}</p>
                      <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); setImageFile(null); }} leftIcon={<X className="w-4 h-4" />}>
                        Remove
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div>
                    <Camera className="w-12 h-12 mx-auto text-gray-400 dark:text-gray-500 mb-3" />
                    <p className="text-gray-600 dark:text-gray-400 mb-1">Drag & drop an image or click to browse</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">PNG, JPG, WebP up to 10MB</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Audio Upload */}
          {activeType === 'audio' && (
            <div className="space-y-3">
              <div
                className={cn(
                  'border-2 border-dashed rounded-xl p-8 text-center transition-colors',
                  audioFile ? 'border-green-500 bg-green-50 dark:bg-green-900/20' : 'border-gray-300 dark:border-gray-600 hover:border-blue-400 dark:hover:border-blue-600'
                )}
                onClick={() => audioInputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); }}
                onDrop={(e) => { e.preventDefault(); if (e.dataTransfer.files[0]) handleFileChange(e.dataTransfer.files[0], setAudioFile); }}
              >
                <input
                  ref={audioInputRef}
                  type="file"
                  accept="audio/*"
                  onChange={(e) => handleFileChange(e.target.files[0], setAudioFile)}
                  className="hidden"
                />
                {audioFile ? (
                  <div className="flex items-center justify-center gap-4">
                    <div className="w-16 h-16 rounded-lg bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                      <FileText className="w-8 h-8 text-gray-400" />
                    </div>
                    <div className="text-left">
                      <p className="font-medium text-gray-900 dark:text-white">{audioFile.name}</p>
                      <p className="text-sm text-gray-500 dark:text-gray-400">{formatFileSize(audioFile.size)}</p>
                      <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); setAudioFile(null); }} leftIcon={<X className="w-4 h-4" />}>
                        Remove
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div>
                    <Mic className="w-12 h-12 mx-auto text-gray-400 dark:text-gray-500 mb-3" />
                    <p className="text-gray-600 dark:text-gray-400 mb-1">Drag & drop audio or click to browse</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">MP3, WAV, M4A up to 10MB</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Verify Button */}
          <div className="flex gap-3 pt-2">
            <Button
              variant="primary"
              size="lg"
              fullWidth
              loading={isVerifying}
              leftIcon={!isVerifying ? <Search className="w-4 h-4" /> : <Loader2 className="w-4 h-4" />}
              onClick={handleVerify}
              disabled={!canVerify() || isVerifying}
            >
              {isVerifying ? 'Verifying...' : 'Verify Content'}
            </Button>
            <Button variant="outline" size="lg" onClick={clearForm} disabled={isVerifying}>
              <X className="w-4 h-4" />
              Clear
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      {showResult && result && (
        <div className="space-y-6 animate-fade-in">
          {/* Result Header */}
          <Card variant="elevated">
            <CardContent className="pt-6">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div className="flex items-center gap-4">
                  <div className={cn('w-16 h-16 rounded-xl flex items-center justify-center', getVerdictColor(result.verdict).bg)}>
                    <VerdictBadge verdict={result.verdict} size="lg" />
                  </div>
                  <div>
                    <h2 className="text-2xl font-bold text-gray-900 dark:text-white">{result.verdict}</h2>
                    <p className="text-gray-600 dark:text-gray-400">Confidence: {Math.round(result.confidence * 100)}%</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" leftIcon={<Download className="w-4 h-4" />}>Export PDF</Button>
                  <Button variant="outline" size="sm" leftIcon={<Copy className="w-4 h-4" />}>Copy Link</Button>
                  <Button variant="outline" size="sm" leftIcon={<Share2 className="w-4 h-4" />}>Share</Button>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="mt-6">
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-gray-600 dark:text-gray-400">Verification Progress</span>
                  <span className="font-medium text-gray-900 dark:text-white">{resultStep}/4 Steps Complete</span>
                </div>
                <Progress value={(resultStep / 4) * 100} className="h-3" />
                <div className="flex justify-between mt-2 text-xs text-gray-500 dark:text-gray-400">
                  <span className={cn(resultStep >= 1 && 'text-green-600 dark:text-green-400')}>1. Input Processing</span>
                  <span className={cn(resultStep >= 2 && 'text-green-600 dark:text-green-400')}>2. Evidence Retrieval</span>
                  <span className={cn(resultStep >= 3 && 'text-green-600 dark:text-green-400')}>3. Stance Analysis</span>
                  <span className={cn(resultStep >= 4 && 'text-green-600 dark:text-green-400')}>4. Final Verdict</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Claim Text */}
          <Card variant="outlined">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="w-5 h-5" />
                Analyzed Claim
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-gray-900 dark:text-white whitespace-pre-wrap">{result.claim_text}</p>
              <div className="flex flex-wrap gap-2 mt-4">
                <Badge variant="outline">{result.language.toUpperCase()}</Badge>
                <Badge variant="outline">{result.input_type}</Badge>
                <Badge variant="outline">{Math.round(result.processing_time_ms)}ms</Badge>
              </div>
            </CardContent>
          </Card>

          {/* Evidence & Stance */}
          {result.evidence && result.evidence.length > 0 && (
            <Card variant="outlined">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Shield className="w-5 h-5" />
                  Evidence & Stance Analysis
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {result.evidence.map((evidence, index) => (
                    <div key={evidence.id} className="border rounded-lg p-4 bg-gray-50 dark:bg-gray-800/50">
                      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-3">
                        <div className="flex items-center gap-3">
                          <span className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 text-sm font-medium flex items-center justify-center">{index + 1}</span>
                          <div>
                            <p className="font-medium text-gray-900 dark:text-white truncate max-w-md">{evidence.title}</p>
                            <p className="text-sm text-gray-500 dark:text-gray-400">{evidence.source_name} • {evidence.source_type}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <StanceBadge stance={evidence.stance} />
                          <SourceTypeBadge type={evidence.source_type} />
                        </div>
                      </div>
                      <p className="text-gray-700 dark:text-gray-300 mb-3">{evidence.snippet}</p>
                      <div className="flex flex-wrap gap-2 text-sm">
                        <Badge variant="outline">Relevance: {Math.round(evidence.relevance_score * 100)}%</Badge>
                        <Badge variant="outline">Credibility: {Math.round(evidence.credibility_score * 100)}%</Badge>
                        <Button variant="ghost" size="sm" leftIcon={<ExternalLink className="w-3 h-3" />} onClick={() => window.open(evidence.url, '_blank')}>
                          View Source
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Reasoning */}
          {result.reasoning && (
            <Card variant="outlined">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Info className="w-5 h-5" />
                  Reasoning
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{result.reasoning}</p>
              </CardContent>
            </Card>
          )}

          {/* Risk Factors */}
          {result.risk_factors && result.risk_factors.length > 0 && (
            <Card variant="outlined" className="border-red-200 dark:border-red-800">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Flag className="w-5 h-5 text-red-600" />
                  Risk Factors Identified
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {result.risk_factors.map((factor, i) => (
                    <li key={i} className="flex items-center gap-2 text-red-700 dark:text-red-300">
                      <AlertCircle className="w-4 h-4 flex-shrink-0" />
                      <span>{factor}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Actions */}
          <Card variant="outlined" padding="none">
            <CardContent className="pt-0">
              <div className="flex flex-wrap gap-3">
                <Button variant="primary" leftIcon={<ArrowRight className="w-4 h-4" />} onClick={() => navigate(`/history/${result.id}`)}>
                  View Full Report
                </Button>
                <Button variant="outline" leftIcon={<History className="w-4 h-4" />} onClick={() => navigate('/history')}>
                  View History
                </Button>
                <Button variant="outline" leftIcon={<Plus className="w-4 h-4" />} onClick={clearForm}>
                  New Verification
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}