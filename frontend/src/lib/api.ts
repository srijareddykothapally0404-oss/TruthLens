// ============================================================
// TruthLens - API Client with Authentication
// ============================================================

import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import type {
  User,
  AuthTokens,
  LoginRequest,
  RegisterRequest,
  UnifiedVerifyRequest,
  UnifiedVerifyResponse,
  VerificationHistoryItem,
  VerificationDetail,
  MonitoringJob,
  MonitoringResult,
  HealthResponse,
  ApiErrorResponse,
} from '@/types';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
const WS_URL = (import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000/ws').replace(/\/+$/, '');

// Token storage keys
const ACCESS_TOKEN_KEY = 'truthlens_access_token';
const REFRESH_TOKEN_KEY = 'truthlens_refresh_token';
const USER_KEY = 'truthlens_user';

// Create axios instance
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - add auth token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - handle token refresh
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: unknown) => void;
  reject: (reason: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiErrorResponse>) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${token}`;
          }
          return api(originalRequest);
        }).catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
        if (!refreshToken) throw new Error('No refresh token');

        const response = await axios.post<AuthTokens>(`${API_BASE_URL}/api/auth/refresh`, {
          refresh_token: refreshToken,
        });

        const { access_token, refresh_token: newRefreshToken } = response.data;
        localStorage.setItem(ACCESS_TOKEN_KEY, access_token);
        localStorage.setItem(REFRESH_TOKEN_KEY, newRefreshToken);

        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
        }

        processQueue(null, access_token);
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        clearAuth();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

// Auth helpers
export function getStoredAuth(): { user: User | null; tokens: AuthTokens | null } {
  try {
    const userStr = localStorage.getItem(USER_KEY);
    const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);

    if (userStr && accessToken && refreshToken) {
      return {
        user: JSON.parse(userStr) as User,
        tokens: { access_token: accessToken, refresh_token: refreshToken, token_type: 'bearer', expires_in: 3600 },
      };
    }
  } catch {
    // Invalid stored data
  }
  return { user: null, tokens: null };
}

export function setAuth(user: User, tokens: AuthTokens): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
}

export function clearAuth(): void {
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

// Auth API
export const authApi = {
  async login(credentials: LoginRequest): Promise<{ user: User; tokens: AuthTokens }> {
    const response = await api.post<{ user: User } & AuthTokens>('/api/auth/login', credentials);
    const { user, access_token, refresh_token, token_type, expires_in } = response.data;
    const tokens: AuthTokens = { access_token, refresh_token, token_type, expires_in };
    setAuth(user, tokens);
    return { user, tokens };
  },

  async register(data: RegisterRequest): Promise<{ user: User; tokens: AuthTokens }> {
    const response = await api.post<{ user: User } & AuthTokens>('/api/auth/register', data);
    const { user, access_token, refresh_token, token_type, expires_in } = response.data;
    const tokens: AuthTokens = { access_token, refresh_token, token_type, expires_in };
    setAuth(user, tokens);
    return { user, tokens };
  },

  async logout(): Promise<void> {
    try {
      await api.post('/api/auth/logout');
    } finally {
      clearAuth();
    }
  },

  async getMe(): Promise<User> {
    const response = await api.get<User>('/api/auth/me');
    return response.data;
  },

  async refreshToken(): Promise<AuthTokens> {
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (!refreshToken) throw new Error('No refresh token');
    const response = await api.post<AuthTokens>('/api/auth/refresh', { refresh_token: refreshToken });
    const tokens = response.data;
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
    return tokens;
  },
};

// Verification API
export const verificationApi = {
  async verifyUnified(request: UnifiedVerifyRequest): Promise<UnifiedVerifyResponse> {
    const response = await api.post<UnifiedVerifyResponse>('/api/verify', request);
    return response.data;
  },

  async verifyText(text: string, options?: UnifiedVerifyRequest['options']): Promise<UnifiedVerifyResponse> {
    return this.verifyUnified({ input: text, input_type: 'text', options });
  },

  async verifyUrl(url: string, options?: UnifiedVerifyRequest['options']): Promise<UnifiedVerifyResponse> {
    return this.verifyUnified({ input: url, input_type: 'url', options });
  },

  async verifyImage(file: File, options?: UnifiedVerifyRequest['options']): Promise<UnifiedVerifyResponse> {
    const formData = new FormData();
    formData.append('file', file);
    if (options) {
      formData.append('options', JSON.stringify(options));
    }
    const response = await api.post<UnifiedVerifyResponse>('/api/verify/image', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  async getHistory(params?: {
    limit?: number;
    offset?: number;
    verdict?: string;
    status?: string;
    date_from?: string;
    date_to?: string;
  }): Promise<{ items: VerificationHistoryItem[]; total: number }> {
    const response = await api.get<{ items: VerificationHistoryItem[]; total: number }>('/api/verifications', { params });
    return response.data;
  },

  async getVerification(id: string): Promise<VerificationDetail> {
    const response = await api.get<VerificationDetail>(`/api/verifications/${id}`);
    return response.data;
  },

  async deleteVerification(id: string): Promise<void> {
    await api.delete(`/api/verifications/${id}`);
  },

  async exportVerification(id: string, format: 'pdf' | 'json' | 'csv'): Promise<Blob> {
    const response = await api.get(`/api/verifications/${id}/export`, {
      params: { format },
      responseType: 'blob',
    });
    return response.data;
  },
};

// Monitoring API
export const monitoringApi = {
  async getJobs(): Promise<MonitoringJob[]> {
    const response = await api.get<MonitoringJob[]>('/api/monitoring/jobs');
    return response.data;
  },

  async getJob(id: string): Promise<MonitoringJob> {
    const response = await api.get<MonitoringJob>(`/api/monitoring/jobs/${id}`);
    return response.data;
  },

  async createJob(job: Omit<MonitoringJob, 'id' | 'created_at' | 'updated_at' | 'last_run' | 'next_run' | 'run_count' | 'created_by'>): Promise<MonitoringJob> {
    const response = await api.post<MonitoringJob>('/api/monitoring/jobs', job);
    return response.data;
  },

  async updateJob(id: string, job: Partial<MonitoringJob>): Promise<MonitoringJob> {
    const response = await api.patch<MonitoringJob>(`/api/monitoring/jobs/${id}`, job);
    return response.data;
  },

  async deleteJob(id: string): Promise<void> {
    await api.delete(`/api/monitoring/jobs/${id}`);
  },

  async getResults(jobId: string, limit = 50): Promise<MonitoringResult[]> {
    const response = await api.get<MonitoringResult[]>(`/api/monitoring/jobs/${jobId}/results`, { params: { limit } });
    return response.data;
  },

  async runJobNow(id: string): Promise<MonitoringResult> {
    const response = await api.post<MonitoringResult>(`/api/monitoring/jobs/${id}/run`);
    return response.data;
  },
};

// Health API
export const healthApi = {
  async getHealth(): Promise<HealthResponse> {
    const response = await api.get<HealthResponse>('/api/health');
    return response.data;
  },
};

// Legacy API (for backward compatibility)
export const legacyApi = {
  async classify(text: string): Promise<{ prediction: string; label: number; classifier: string; explanation: string }> {
    const response = await api.post('/api/classify', { text });
    return response.data;
  },

  async verifyText(text: string): Promise<any> {
    const response = await api.post('/api/verify/text', { text });
    return response.data;
  },

  async verifyMultilingual(text: string, sourceUrl?: string): Promise<any> {
    const response = await api.post('/api/verify/multilingual', { text, source_url: sourceUrl });
    return response.data;
  },

  async extractClaims(text: string): Promise<any> {
    const response = await api.post('/api/extract-claims', { text });
    return response.data;
  },

  async retrieveEvidence(claim: string, claimId?: number): Promise<any> {
    const response = await api.post('/api/retrieve-evidence', { claim, claim_id: claimId });
    return response.data;
  },

  async analyzeEvidence(claim: string, claimId: number, evidence: any[]): Promise<any> {
    const response = await api.post('/api/analyze-evidence', { claim, claim_id: claimId, evidence });
    return response.data;
  },

  async processInput(input: string, inputType: string, runPipeline = false): Promise<any> {
    const response = await api.post('/api/process-input', { input, input_type: inputType, run_pipeline: runPipeline });
    return response.data;
  },

  async processImage(file: File, runPipeline = false): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('run_pipeline', String(runPipeline));
    const response = await api.post('/api/process-image', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  async detectLanguage(text: string): Promise<any> {
    const response = await api.post('/api/detect-language', { text });
    return response.data;
  },

  async translate(text: string, sourceLang?: string, targetLang = 'en'): Promise<any> {
    const response = await api.post('/api/translate', { text, source_language: sourceLang, target_language: targetLang });
    return response.data;
  },
};

// WebSocket connection
export function createWebSocketConnection(onMessage: (data: any) => void, onClose?: () => void): WebSocket {
  const token = localStorage.getItem(ACCESS_TOKEN_KEY);
  const wsUrl = `${WS_URL}?token=${encodeURIComponent(token || '')}`;
  const ws = new WebSocket(wsUrl);

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch {
      // Ignore parse errors
    }
  };

  ws.onclose = () => {
    if (onClose) onClose();
  };

  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
  };

  return ws;
}

// Export API instance for direct use if needed
export { api, API_BASE_URL, WS_URL };