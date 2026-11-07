// ============================================================
// TruthLens - Utility Functions
// ============================================================

import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { format, formatDistanceToNow, parseISO, isValid } from 'date-fns';
import type { VerdictType, StanceType, SourceType, VerificationStatus, ContentStatus, ConnectorType, ConnectorStatus } from '@/types';

// -----------------------------------------------------------------------------
// Class Name Helpers
// -----------------------------------------------------------------------------

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

// -----------------------------------------------------------------------------
// Date Formatting
// -----------------------------------------------------------------------------

export function formatDate(dateString: string | null | undefined, options?: {
  includeTime?: boolean;
  relative?: boolean;
}): string {
  if (!dateString) return '—';

  try {
    const date = parseISO(dateString);
    if (!isValid(date)) return 'Invalid date';

    if (options?.relative) {
      return formatDistanceToNow(date, { addSuffix: true });
    }

    if (options?.includeTime) {
      return format(date, 'MMM d, yyyy h:mm a');
    }

    return format(date, 'MMM d, yyyy');
  } catch {
    return 'Invalid date';
  }
}

export function formatDateTime(dateString: string | null | undefined): string {
  return formatDate(dateString, { includeTime: true });
}

export function formatRelativeTime(dateString: string | null | undefined): string {
  return formatDate(dateString, { relative: true });
}

// -----------------------------------------------------------------------------
// Verdict Helpers
// -----------------------------------------------------------------------------

export function getVerdictColor(verdict: VerdictType | string): string {
  switch (verdict) {
    case 'TRUE': return 'text-green-700 bg-green-100 dark:text-green-300 dark:bg-green-900/30 border-green-200 dark:border-green-800';
    case 'FALSE': return 'text-red-700 bg-red-100 dark:text-red-300 dark:bg-red-900/30 border-red-200 dark:border-red-800';
    case 'PARTIALLY_TRUE': return 'text-amber-700 bg-amber-100 dark:text-amber-300 dark:bg-amber-900/30 border-amber-200 dark:border-amber-800';
    case 'MISLEADING': return 'text-orange-700 bg-orange-100 dark:text-orange-300 dark:bg-orange-900/30 border-orange-200 dark:border-orange-800';
    case 'INSUFFICIENT_EVIDENCE': return 'text-gray-700 bg-gray-100 dark:text-gray-300 dark:bg-gray-800 border-gray-200 dark:border-gray-700';
    case 'NEEDS_HUMAN_REVIEW': return 'text-purple-700 bg-purple-100 dark:text-purple-300 dark:bg-purple-900/30 border-purple-200 dark:border-purple-800';
    default: return 'text-gray-700 bg-gray-100 dark:text-gray-300 dark:bg-gray-800 border-gray-200 dark:border-gray-700';
  }
}

export function getVerdictLabel(verdict: VerdictType | string): string {
  switch (verdict) {
    case 'TRUE': return 'TRUE';
    case 'FALSE': return 'FALSE';
    case 'PARTIALLY_TRUE': return 'PARTIALLY TRUE';
    case 'MISLEADING': return 'MISLEADING';
    case 'INSUFFICIENT_EVIDENCE': return 'INSUFFICIENT EVIDENCE';
    case 'NEEDS_HUMAN_REVIEW': return 'NEEDS HUMAN REVIEW';
    default: return String(verdict);
  }
}

export function getVerdictDescription(verdict: VerdictType | string): string {
  switch (verdict) {
    case 'TRUE': return 'Multiple independent credible sources support this claim';
    case 'FALSE': return 'Multiple independent credible sources contradict this claim';
    case 'PARTIALLY_TRUE': return 'Distinct claim components have different evidence outcomes';
    case 'MISLEADING': return 'Context markers indicate deceptive framing or presentation';
    case 'INSUFFICIENT_EVIDENCE': return 'Evidence is unavailable, inadequate, or inconclusive';
    case 'NEEDS_HUMAN_REVIEW': return 'Conflicting credible sources require expert judgment';
    default: return 'Assessment pending';
  }
}

// -----------------------------------------------------------------------------
// Stance Helpers
// -----------------------------------------------------------------------------

export function getStanceColor(stance: StanceType | string): string {
  switch (stance) {
    case 'SUPPORTS': return 'text-green-600 bg-green-50 dark:text-green-400 dark:bg-green-900/20 border-green-100 dark:border-green-800';
    case 'CONTRADICTS': return 'text-red-600 bg-red-50 dark:text-red-400 dark:bg-red-900/20 border-red-100 dark:border-red-800';
    case 'MIXED': return 'text-amber-600 bg-amber-50 dark:text-amber-400 dark:bg-amber-900/20 border-amber-100 dark:border-amber-800';
    case 'NEUTRAL': return 'text-blue-600 bg-blue-50 dark:text-blue-400 dark:bg-blue-900/20 border-blue-100 dark:border-blue-800';
    case 'INSUFFICIENT': return 'text-gray-600 bg-gray-50 dark:text-gray-400 dark:bg-gray-800 border-gray-100 dark:border-gray-700';
    default: return 'text-gray-600 bg-gray-50 dark:text-gray-400 dark:bg-gray-800 border-gray-100 dark:border-gray-700';
  }
}

export function getStanceLabel(stance: StanceType | string): string {
  switch (stance) {
    case 'SUPPORTS': return 'Supports';
    case 'CONTRADICTS': return 'Contradicts';
    case 'MIXED': return 'Mixed';
    case 'NEUTRAL': return 'Neutral';
    case 'INSUFFICIENT': return 'Insufficient';
    default: return String(stance);
  }
}

export function getStanceIcon(stance: StanceType | string): string {
  switch (stance) {
    case 'SUPPORTS': return '↗';
    case 'CONTRADICTS': return '↘';
    case 'MIXED': return '↔';
    case 'NEUTRAL': return '○';
    case 'INSUFFICIENT': return '?';
    default: return '•';
  }
}

// -----------------------------------------------------------------------------
// Source Type Helpers
// -----------------------------------------------------------------------------

export function getSourceTypeInfo(sourceType: SourceType | string): { label: string; class: string; icon: string } {
  switch (sourceType) {
    case 'official': return { label: 'OFFICIAL', class: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300 border-blue-200 dark:border-blue-800', icon: '🏛️' };
    case 'fact_checker': return { label: 'FACT-CHECKER', class: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300 border-green-200 dark:border-green-800', icon: '✓' };
    case 'news': return { label: 'NEWS', class: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300 border-purple-200 dark:border-purple-800', icon: '📰' };
    case 'social': return { label: 'SOCIAL', class: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300 border-orange-200 dark:border-orange-800', icon: '💬' };
    case 'unknown': return { label: 'UNKNOWN', class: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-600', icon: '?' };
    default: return { label: 'UNKNOWN', class: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-600', icon: '?' };
  }
}

// -----------------------------------------------------------------------------
// Status Helpers
// -----------------------------------------------------------------------------

export function getStatusColor(status: VerificationStatus | string): string {
  switch (status) {
    case 'completed': return 'text-green-600 bg-green-50 dark:text-green-400 dark:bg-green-900/20';
    case 'partial': return 'text-amber-600 bg-amber-50 dark:text-amber-400 dark:bg-amber-900/20';
    case 'failed': return 'text-red-600 bg-red-50 dark:text-red-400 dark:bg-red-900/20';
    case 'processing': return 'text-blue-600 bg-blue-50 dark:text-blue-400 dark:bg-blue-900/20';
    case 'pending': return 'text-gray-600 bg-gray-50 dark:text-gray-400 dark:bg-gray-800';
    default: return 'text-gray-600 bg-gray-50 dark:text-gray-400 dark:bg-gray-800';
  }
}

export function getStatusLabel(status: VerificationStatus | string): string {
  switch (status) {
    case 'completed': return 'Completed';
    case 'partial': return 'Partial';
    case 'failed': return 'Failed';
    case 'processing': return 'Processing';
    case 'pending': return 'Pending';
    default: return String(status);
  }
}

// -----------------------------------------------------------------------------
// Content Status Helpers
// -----------------------------------------------------------------------------

export function getContentStatusLabel(status: ContentStatus | string): string {
  switch (status) {
    case 'retrieved': return 'Retrieved';
    case 'not_attempted': return 'Not Attempted';
    case 'unavailable': return 'Unavailable';
    case 'error': return 'Error';
    default: return String(status);
  }
}

// -----------------------------------------------------------------------------
// Connector Helpers
// -----------------------------------------------------------------------------

export function getConnectorLabel(connector: ConnectorType | string): string {
  switch (connector) {
    case 'gdelt': return 'GDELT';
    case 'google_factcheck': return 'Google Fact Check';
    case 'social': return 'Social Media';
    default: return String(connector);
  }
}

export function getConnectorStatusColor(status: ConnectorStatus | string): string {
  switch (status) {
    case 'success': return 'text-green-600 bg-green-50 dark:text-green-400 dark:bg-green-900/20';
    case 'rate_limited': return 'text-amber-600 bg-amber-50 dark:text-amber-400 dark:bg-amber-900/20';
    case 'error': return 'text-red-600 bg-red-50 dark:text-red-400 dark:bg-red-900/20';
    default: return 'text-gray-600 bg-gray-50 dark:text-gray-400 dark:bg-gray-800';
  }
}

// -----------------------------------------------------------------------------
// File Size Formatting
// -----------------------------------------------------------------------------

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// -----------------------------------------------------------------------------
// Number Formatting
// -----------------------------------------------------------------------------

export function formatNumber(num: number | null | undefined): string {
  if (num === null || num === undefined) return '—';
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
  return num.toString();
}

export function formatPercentage(value: number | null | undefined, decimals = 0): string {
  if (value === null || value === undefined) return '—';
  return (value * 100).toFixed(decimals) + '%';
}

export function formatConfidence(confidence: number | null | undefined): string {
  if (confidence === null || confidence === undefined) return 'Not established';
  return `${Math.round(confidence * 100)}%`;
}

// -----------------------------------------------------------------------------
// Text Truncation
// -----------------------------------------------------------------------------

export function truncate(text: string | null | undefined, maxLength: number): string {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 3) + '...';
}

export function truncateMiddle(text: string | null | undefined, maxLength: number): string {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  const half = Math.floor(maxLength / 2) - 2;
  return text.slice(0, half) + '...' + text.slice(-half);
}

// -----------------------------------------------------------------------------
// URL Validation
// -----------------------------------------------------------------------------

export function isValidUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return ['http:', 'https:'].includes(parsed.protocol) && !parsed.username && !parsed.password;
  } catch {
    return false;
  }
}

export function getDomain(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return '';
  }
}

// -----------------------------------------------------------------------------
// Debounce
// -----------------------------------------------------------------------------

export function debounce<T extends (...args: unknown[]) => unknown>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: ReturnType<typeof setTimeout> | null = null;
  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}

// -----------------------------------------------------------------------------
// Generate ID
// -----------------------------------------------------------------------------

export function generateId(): string {
  return crypto.randomUUID();
}

// -----------------------------------------------------------------------------
// Copy to Clipboard
// -----------------------------------------------------------------------------

export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

// -----------------------------------------------------------------------------
// Download Blob
// -----------------------------------------------------------------------------

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// -----------------------------------------------------------------------------
// Error Message Extraction
// -----------------------------------------------------------------------------

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  if (error && typeof error === 'object' && 'response' in error) {
    const axiosError = error as { response?: { data?: { detail?: string; message?: string } } };
    return axiosError.response?.data?.detail || axiosError.response?.data?.message || 'An error occurred';
  }
  return 'An unknown error occurred';
}

// -----------------------------------------------------------------------------
// Role Display
// -----------------------------------------------------------------------------

export function getRoleLabel(role: string): string {
  switch (role) {
    case 'admin': return 'Administrator';
    case 'analyst': return 'Analyst';
    case 'reviewer': return 'Reviewer';
    case 'viewer': return 'Viewer';
    default: return role;
  }
}

export function getRoleColor(role: string): string {
  switch (role) {
    case 'admin': return 'text-red-700 bg-red-100 dark:text-red-300 dark:bg-red-900/30';
    case 'analyst': return 'text-blue-700 bg-blue-100 dark:text-blue-300 dark:bg-blue-900/30';
    case 'reviewer': return 'text-purple-700 bg-purple-100 dark:text-purple-300 dark:bg-purple-900/30';
    case 'viewer': return 'text-gray-700 bg-gray-100 dark:text-gray-300 dark:bg-gray-800';
    default: return 'text-gray-700 bg-gray-100 dark:text-gray-300 dark:bg-gray-800';
  }
}

// -----------------------------------------------------------------------------
// Clearance Level
// -----------------------------------------------------------------------------

export function getClearanceLabel(level: string): string {
  switch (level) {
    case 'public': return 'Public';
    case 'internal': return 'Internal';
    case 'confidential': return 'Confidential';
    case 'restricted': return 'Restricted';
    default: return level;
  }
}

export function getClearanceColor(level: string): string {
  switch (level) {
    case 'public': return 'text-green-700 bg-green-100 dark:text-green-300 dark:bg-green-900/30';
    case 'internal': return 'text-blue-700 bg-blue-100 dark:text-blue-300 dark:bg-blue-900/30';
    case 'confidential': return 'text-amber-700 bg-amber-100 dark:text-amber-300 dark:bg-amber-900/30';
    case 'restricted': return 'text-red-700 bg-red-100 dark:text-red-300 dark:bg-red-900/30';
    default: return 'text-gray-700 bg-gray-100 dark:text-gray-300 dark:bg-gray-800';
  }
}