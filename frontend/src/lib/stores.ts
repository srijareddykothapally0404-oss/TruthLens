// ============================================================
// TruthLens - Zustand State Management
// ============================================================

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type {
  User,
  AuthTokens,
  AuthState,
  UnifiedVerifyResponse,
  VerificationHistoryItem,
  VerificationDetail,
  MonitoringJob,
  MonitoringResult,
  HealthResponse,
  ToastMessage,
  InputType,
  UnifiedVerifyRequest,
} from '@/types';
import { verificationApi } from './api';

// -----------------------------------------------------------------------------
// Auth Store
// -----------------------------------------------------------------------------

interface AuthStore extends AuthState {
  login: (user: User, tokens: AuthTokens) => void;
  logout: () => void;
  setUser: (user: User) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  updateUser: (data: Partial<User>) => void;
  hasRole: (roles: string[]) => boolean;
  hasClearance: (level: string) => boolean;
  fetchUser: () => Promise<void>;
}

const CLEARANCE_HIERARCHY: Record<string, number> = {
  public: 0,
  internal: 1,
  confidential: 2,
  restricted: 3,
};

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      user: null,
      tokens: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: (user, tokens) => set({ user, tokens, isAuthenticated: true, error: null }),
      logout: () => set({ user: null, tokens: null, isAuthenticated: false, error: null }),
      setUser: (user) => set({ user }),
      setLoading: (isLoading) => set({ isLoading }),
      setError: (error) => set({ error }),
      updateUser: (data) => set((state) => ({ user: state.user ? { ...state.user, ...data } : null })),
      hasRole: (roles) => {
        const user = get().user;
        return user ? roles.includes(user.role) : false;
      },
      hasClearance: (level) => {
        const user = get().user;
        if (!user) return false;
        return (CLEARANCE_HIERARCHY[user.clearance_level] ?? 0) >= (CLEARANCE_HIERARCHY[level] ?? 0);
      },
      fetchUser: async () => {
        const { tokens } = get();
        if (!tokens?.access_token) return;
        set({ isLoading: true });
        try {
          const { authApi } = await import('./api');
          const user = await authApi.getMe();
          set({ user, isLoading: false, isAuthenticated: true });
        } catch {
          set({ isLoading: false });
        }
      },
    }),
    {
      name: 'truthlens-auth',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        user: state.user,
        tokens: state.tokens,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

// -----------------------------------------------------------------------------
// Verification Store
// -----------------------------------------------------------------------------

interface VerificationStore {
  currentVerification: UnifiedVerifyResponse | null;
  history: VerificationHistoryItem[];
  historyTotal: number;
  historyPage: number;
  historyPageSize: number;
  historyFilters: Record<string, unknown>;
  historyLoading: boolean;
  selectedVerification: VerificationDetail | null;
  selectedVerificationLoading: boolean;
  verificationsLoading: boolean;
  isLoading: boolean;
  error: string | null;
  stats: {
    total_verifications: number;
    false_claims: number;
    true_claims: number;
    avg_confidence: number;
    verifications_change: number;
    false_claims_change: number;
    true_claims_change: number;
    confidence_change: number;
    recent_verifications: VerificationHistoryItem[];
  } | null;

  // Actions
  setCurrentVerification: (verification: UnifiedVerifyResponse | null) => void;
  clearCurrent: () => void;
  clearCurrentVerification: () => void;
  setHistory: (items: VerificationHistoryItem[], total: number) => void;
  addHistoryItem: (item: VerificationHistoryItem) => void;
  removeHistoryItem: (id: string) => void;
  setHistoryPage: (page: number) => void;
  setHistoryPageSize: (size: number) => void;
  setHistoryFilters: (filters: Record<string, unknown>) => void;
  setHistoryLoading: (loading: boolean) => void;
  setSelectedVerification: (verification: VerificationDetail | null) => void;
  setSelectedVerificationLoading: (loading: boolean) => void;
  setVerificationsLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  fetchHistory: (params?: { limit?: number; offset?: number; verdict?: string; status?: string; date_from?: string; date_to?: string }) => Promise<void>;
  verify: (request: UnifiedVerifyRequest) => Promise<boolean>;
  verifyUrl: (url: string, options?: UnifiedVerifyRequest['options']) => Promise<boolean>;
  verifyImage: (file: File, options?: UnifiedVerifyRequest['options']) => Promise<boolean>;
  verifyAudio: (file: File, options?: UnifiedVerifyRequest['options']) => Promise<boolean>;
}

export const useVerificationStore = create<VerificationStore>((set, _get) => ({
  currentVerification: null,
  history: [],
  historyTotal: 0,
  historyPage: 1,
  historyPageSize: 20,
  historyFilters: {},
  historyLoading: false,
  selectedVerification: null,
  selectedVerificationLoading: false,
  verificationsLoading: false,
  isLoading: false,
  error: null,
  stats: null,

  setCurrentVerification: (verification) => set({ currentVerification: verification, error: null }),
  clearCurrent: () => set({ currentVerification: null }),
  clearCurrentVerification: () => set({ currentVerification: null }),
  setHistory: (items, total) => set({ history: items, historyTotal: total }),
  addHistoryItem: (item) => set((state) => ({ history: [item, ...state.history], historyTotal: state.historyTotal + 1 })),
  removeHistoryItem: (id) => set((state) => ({ history: state.history.filter((h) => h.id !== id), historyTotal: state.historyTotal - 1 })),
  setHistoryPage: (page) => set({ historyPage: page }),
  setHistoryPageSize: (size) => set({ historyPageSize: size }),
  setHistoryFilters: (filters) => set({ historyFilters: filters }),
  setHistoryLoading: (loading) => set({ historyLoading: loading }),
  setSelectedVerification: (verification) => set({ selectedVerification: verification }),
  setSelectedVerificationLoading: (loading) => set({ selectedVerificationLoading: loading }),
  setVerificationsLoading: (loading) => set({ verificationsLoading: loading }),
  setError: (error) => set({ error }),

  fetchHistory: async (params) => {
    set({ historyLoading: true, error: null });
    try {
      const { items, total } = await verificationApi.getHistory(params);
      set({ history: items, historyTotal: total, historyLoading: false });
    } catch (err) {
      set({ historyLoading: false, error: err instanceof Error ? err.message : 'Failed to fetch history' });
    }
  },

  verify: async (request) => {
    set({ verificationsLoading: true, isLoading: true, error: null });
    try {
      const result = await verificationApi.verifyUnified(request);
      set({ currentVerification: result, verificationsLoading: false, isLoading: false });
      return true;
    } catch (err) {
      set({ verificationsLoading: false, isLoading: false, error: err instanceof Error ? err.message : 'Verification failed' });
      return false;
    }
  },

  verifyUrl: async (url, options) => {
    set({ verificationsLoading: true, isLoading: true, error: null });
    try {
      const result = await verificationApi.verifyUrl(url, options);
      set({ currentVerification: result, verificationsLoading: false, isLoading: false });
      return true;
    } catch (err) {
      set({ verificationsLoading: false, isLoading: false, error: err instanceof Error ? err.message : 'Verification failed' });
      return false;
    }
  },

  verifyImage: async (file, options) => {
    set({ verificationsLoading: true, isLoading: true, error: null });
    try {
      const result = await verificationApi.verifyImage(file, options);
      set({ currentVerification: result, verificationsLoading: false, isLoading: false });
      return true;
    } catch (err) {
      set({ verificationsLoading: false, isLoading: false, error: err instanceof Error ? err.message : 'Verification failed' });
      return false;
    }
  },

  verifyAudio: async (file, options) => {
    set({ verificationsLoading: true, isLoading: true, error: null });
    try {
      // For now, use the same image endpoint or create a new one
      const formData = new FormData();
      formData.append('file', file);
      if (options) {
        formData.append('options', JSON.stringify(options));
      }
      // Assuming there's an audio endpoint or we use a generic one
      const result = await verificationApi.verifyUnified({ input: '', input_type: 'audio', options });
      set({ currentVerification: result, verificationsLoading: false, isLoading: false });
      return true;
    } catch (err) {
      set({ verificationsLoading: false, isLoading: false, error: err instanceof Error ? err.message : 'Verification failed' });
      return false;
    }
  },

  fetchStats: async () => {
    try {
      const { items } = await verificationApi.getHistory({ limit: 1000 });
      const total = items.length;
      const falseClaims = items.filter(i => i.overall_verdict === 'FALSE').length;
      const trueClaims = items.filter(i => i.overall_verdict === 'TRUE').length;
      const avgConfidence = total > 0 ? items.reduce((sum, i) => sum + (i.overall_confidence || 0), 0) / total : 0;

      // Calculate changes (simplified - comparing first half vs second half)
      const midpoint = Math.floor(total / 2);
      const recent = items.slice(0, midpoint);
      const older = items.slice(midpoint);

      const recentFalse = recent.filter(i => i.overall_verdict === 'FALSE').length;
      const olderFalse = older.filter(i => i.overall_verdict === 'FALSE').length;
      const recentTrue = recent.filter(i => i.overall_verdict === 'TRUE').length;
      const olderTrue = older.filter(i => i.overall_verdict === 'TRUE').length;
      const recentAvgConf = recent.length > 0 ? recent.reduce((sum, i) => sum + (i.overall_confidence || 0), 0) / recent.length : 0;
      const olderAvgConf = older.length > 0 ? older.reduce((sum, i) => sum + (i.overall_confidence || 0), 0) / older.length : 0;

      set({
        stats: {
          total_verifications: total,
          false_claims: falseClaims,
          true_claims: trueClaims,
          avg_confidence: avgConfidence,
          verifications_change: total - older.length,
          false_claims_change: recentFalse - olderFalse,
          true_claims_change: recentTrue - olderTrue,
          confidence_change: Math.round((recentAvgConf - olderAvgConf) * 100),
          recent_verifications: items.slice(0, 5),
        }
      });
    } catch {
      // Stats are optional, don't show error
    }
  },
}));

// -----------------------------------------------------------------------------
// Monitoring Store
// -----------------------------------------------------------------------------

interface MonitoringStore {
  jobs: MonitoringJob[];
  selectedJob: MonitoringJob | null;
  jobResults: MonitoringResult[];
  jobsLoading: boolean;
  resultsLoading: boolean;

  setJobs: (jobs: MonitoringJob[]) => void;
  addJob: (job: MonitoringJob) => void;
  updateJob: (job: MonitoringJob) => void;
  removeJob: (id: string) => void;
  setSelectedJob: (job: MonitoringJob | null) => void;
  setJobResults: (results: MonitoringResult[]) => void;
  addJobResult: (result: MonitoringResult) => void;
  setJobsLoading: (loading: boolean) => void;
  setResultsLoading: (loading: boolean) => void;
}

export const useMonitoringStore = create<MonitoringStore>((set) => ({
  jobs: [],
  selectedJob: null,
  jobResults: [],
  jobsLoading: false,
  resultsLoading: false,

  setJobs: (jobs) => set({ jobs }),
  addJob: (job) => set((state) => ({ jobs: [job, ...state.jobs] })),
  updateJob: (job) => set((state) => ({ jobs: state.jobs.map((j) => (j.id === job.id ? job : j)) })),
  removeJob: (id) => set((state) => ({ jobs: state.jobs.filter((j) => j.id !== id) })),
  setSelectedJob: (job) => set({ selectedJob: job }),
  setJobResults: (results) => set({ jobResults: results }),
  addJobResult: (result) => set((state) => ({ jobResults: [result, ...state.jobResults] })),
  setJobsLoading: (loading) => set({ jobsLoading: loading }),
  setResultsLoading: (loading) => set({ resultsLoading: loading }),
}));

// -----------------------------------------------------------------------------
// Health Store
// -----------------------------------------------------------------------------

interface HealthStore {
  health: HealthResponse | null;
  lastChecked: Date | null;
  checking: boolean;
  error: string | null;

  setHealth: (health: HealthResponse) => void;
  setChecking: (checking: boolean) => void;
  setError: (error: string | null) => void;
}

export const useHealthStore = create<HealthStore>((set) => ({
  health: null,
  lastChecked: null,
  checking: false,
  error: null,

  setHealth: (health) => set({ health, lastChecked: new Date(), checking: false, error: null }),
  setChecking: (checking) => set({ checking }),
  setError: (error) => set({ error, checking: false }),
}));

// -----------------------------------------------------------------------------
// UI Store (Toasts, Modals, etc.)
// -----------------------------------------------------------------------------

interface UIStore {
  toasts: ToastMessage[];
  modals: Record<string, { isOpen: boolean; data: unknown }>;
  sidebarOpen: boolean;
  theme: 'light' | 'dark';

  // Toasts
  addToast: (toast: Omit<ToastMessage, 'id'>) => string;
  removeToast: (id: string) => void;
  clearToasts: () => void;

  // Modals
  openModal: (key: string, data?: unknown) => void;
  closeModal: (key: string) => void;
  isModalOpen: (key: string) => boolean;

  // Sidebar
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;

  // Theme
  setTheme: (theme: 'light' | 'dark') => void;
  toggleTheme: () => void;
}

export const useUIStore = create<UIStore>()(
  persist(
    (set, get) => ({
      toasts: [],
      modals: {},
      sidebarOpen: false,
      theme: 'light',

      addToast: (toast) => {
        const id = crypto.randomUUID();
        const newToast: ToastMessage = { ...toast, id };
        set((state) => ({ toasts: [...state.toasts, newToast] }));

        if (toast.duration !== 0) {
          setTimeout(() => get().removeToast(id), toast.duration ?? 5000);
        }
        return id;
      },

      removeToast: (id) => set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
      clearToasts: () => set({ toasts: [] }),

      openModal: (key, data) => set((state) => ({ modals: { ...state.modals, [key]: { isOpen: true, data } } })),
      closeModal: (key) => set((state) => ({ modals: { ...state.modals, [key]: { isOpen: false, data: null } } })),
      isModalOpen: (key) => get().modals[key]?.isOpen ?? false,

      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      setSidebarOpen: (open) => set({ sidebarOpen: open }),

      setTheme: (theme) => {
        document.documentElement.dataset.theme = theme;
        set({ theme });
      },
      toggleTheme: () => set((state) => {
        const newTheme = state.theme === 'light' ? 'dark' : 'light';
        document.documentElement.dataset.theme = newTheme;
        return { theme: newTheme };
      }),
    }),
    {
      name: 'truthlens-ui',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ theme: state.theme, sidebarOpen: state.sidebarOpen }),
    }
  )
);

// -----------------------------------------------------------------------------
// Verification Form Store
// -----------------------------------------------------------------------------

interface VerificationFormStore {
  input: string;
  inputType: InputType;
  options: {
    language?: string;
    claim_selection: 'auto' | 'manual' | 'all';
    evidence_sources: ('gdelt' | 'google_factcheck' | 'social')[];
    time_window_days: number;
    max_results: number;
    include_claim_offsets: boolean;
    include_raw_evidence: boolean;
  };
  errors: Record<string, string>;
  isSubmitting: boolean;

  setInput: (input: string) => void;
  setInputType: (type: InputType) => void;
  setOption: <K extends keyof VerificationFormStore['options']>(key: K, value: VerificationFormStore['options'][K]) => void;
  setError: (field: string, error: string) => void;
  clearError: (field: string) => void;
  clearErrors: () => void;
  setSubmitting: (submitting: boolean) => void;
  reset: () => void;
}

const defaultOptions: VerificationFormStore['options'] = {
  claim_selection: 'auto',
  evidence_sources: ['gdelt', 'google_factcheck'],
  time_window_days: 7,
  max_results: 10,
  include_claim_offsets: true,
  include_raw_evidence: false,
};

export const useVerificationFormStore = create<VerificationFormStore>((set) => ({
  input: '',
  inputType: 'text',
  options: defaultOptions,
  errors: {},
  isSubmitting: false,

  setInput: (input) => set({ input }),
  setInputType: (inputType) => set({ inputType }),
  setOption: (key, value) => set((state) => ({ options: { ...state.options, [key]: value } })),
  setError: (field, error) => set((state) => ({ errors: { ...state.errors, [field]: error } })),
  clearError: (field) => set((state) => {
    const { [field]: _, ...rest } = state.errors;
    return { errors: rest };
  }),
  clearErrors: () => set({ errors: {} }),
  setSubmitting: (isSubmitting) => set({ isSubmitting }),
  reset: () => set({ input: '', inputType: 'text', options: defaultOptions, errors: {}, isSubmitting: false }),
}));

// -----------------------------------------------------------------------------
// Selection Store (for bulk actions)
// -----------------------------------------------------------------------------

interface SelectionStore {
  selectedIds: Set<string>;
  selectAll: boolean;

  toggle: (id: string) => void;
  toggleAll: (ids: string[]) => void;
  clear: () => void;
  isSelected: (id: string) => boolean;
  getSelected: () => string[];
}

export const useSelectionStore = create<SelectionStore>((set, get) => ({
  selectedIds: new Set(),
  selectAll: false,

  toggle: (id) => set((state) => {
    const newSet = new Set(state.selectedIds);
    if (newSet.has(id)) newSet.delete(id);
    else newSet.add(id);
    return { selectedIds: newSet, selectAll: false };
  }),

  toggleAll: (ids) => set((state) => {
    const allSelected = ids.every((id) => state.selectedIds.has(id));
    if (allSelected) {
      return { selectedIds: new Set(), selectAll: false };
    } else {
      return { selectedIds: new Set(ids), selectAll: true };
    }
  }),

  clear: () => set({ selectedIds: new Set(), selectAll: false }),
  isSelected: (id) => get().selectedIds.has(id),
  getSelected: () => Array.from(get().selectedIds),
}));