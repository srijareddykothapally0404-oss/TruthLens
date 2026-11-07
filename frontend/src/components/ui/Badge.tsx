// ============================================================
// TruthLens - Badge & Label Components
// ============================================================

import { cn } from '../../lib/utils';
import { ReactNode } from 'react';

// -----------------------------------------------------------------------------
// Badge
// -----------------------------------------------------------------------------

interface BadgeProps {
  children: ReactNode;
  className?: string;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'outline';
  size?: 'sm' | 'md' | 'lg';
  dot?: boolean;
  dotColor?: string;
}

export function Badge({ children, className, variant = 'default', size = 'md', dot, dotColor }: BadgeProps) {
  const variants = {
    default: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300 border-blue-200 dark:border-blue-800',
    success: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300 border-green-200 dark:border-green-800',
    warning: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300 border-amber-200 dark:border-amber-800',
    danger: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300 border-red-200 dark:border-red-800',
    info: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300 border-purple-200 dark:border-purple-800',
    neutral: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-600',
    outline: 'bg-transparent text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-600',
  };

  const sizes = {
    sm: 'px-2 py-0.5 text-xs gap-1',
    md: 'px-2.5 py-1 text-xs gap-1.5',
    lg: 'px-3 py-1.5 text-sm gap-2',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center font-medium rounded-full border',
        variants[variant],
        sizes[size],
        className
      )}
    >
      {dot && <span className={cn('w-1.5 h-1.5 rounded-full', dotColor || 'bg-current')} />}
      {children}
    </span>
  );
}

// -----------------------------------------------------------------------------
// Verdict Badge
// -----------------------------------------------------------------------------

interface VerdictBadgeProps {
  verdict: string;
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
}

export function VerdictBadge({ verdict, size = 'md', showIcon = true }: VerdictBadgeProps) {
  const verdictStyles: Record<string, { bg: string; text: string; border: string; icon: string }> = {
    TRUE: { bg: 'bg-green-100', text: 'text-green-800', border: 'border-green-200', icon: '✓' },
    FALSE: { bg: 'bg-red-100', text: 'text-red-800', border: 'border-red-200', icon: '✗' },
    PARTIALLY_TRUE: { bg: 'bg-amber-100', text: 'text-amber-800', border: 'border-amber-200', icon: '◐' },
    MISLEADING: { bg: 'bg-orange-100', text: 'text-orange-800', border: 'border-orange-200', icon: '⚠' },
    INSUFFICIENT_EVIDENCE: { bg: 'bg-gray-100', text: 'text-gray-800', border: 'border-gray-200', icon: '○' },
    NEEDS_HUMAN_REVIEW: { bg: 'bg-purple-100', text: 'text-purple-800', border: 'border-purple-200', icon: '⚖' },
  };

  const style = verdictStyles[verdict] || verdictStyles.INSUFFICIENT_EVIDENCE;

  const sizes = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-3 py-1 text-sm',
    lg: 'px-4 py-1.5 text-base',
  };

  return (
    <span className={cn(
      'inline-flex items-center gap-1.5 font-semibold rounded-lg border',
      style.bg,
      style.text,
      `dark:${style.bg.replace('100', '900/30')} dark:${style.text.replace('800', '300')} dark:${style.border.replace('200', '800')}`,
      sizes[size]
    )}>
      {showIcon && <span>{style.icon}</span>}
      <span>{verdict.replace('_', ' ')}</span>
    </span>
  );
}

// -----------------------------------------------------------------------------
// Stance Badge
// -----------------------------------------------------------------------------

interface StanceBadgeProps {
  stance: string;
  size?: 'sm' | 'md' | 'lg';
}

export function StanceBadge({ stance, size = 'md' }: StanceBadgeProps) {
  const stanceStyles: Record<string, { bg: string; text: string; border: string; label: string }> = {
    SUPPORTS: { bg: 'bg-green-100', text: 'text-green-800', border: 'border-green-200', label: 'Supports' },
    CONTRADICTS: { bg: 'bg-red-100', text: 'text-red-800', border: 'border-red-200', label: 'Contradicts' },
    MIXED: { bg: 'bg-amber-100', text: 'text-amber-800', border: 'border-amber-200', label: 'Mixed' },
    NEUTRAL: { bg: 'bg-blue-100', text: 'text-blue-800', border: 'border-blue-200', label: 'Neutral' },
    INSUFFICIENT: { bg: 'bg-gray-100', text: 'text-gray-800', border: 'border-gray-200', label: 'Insufficient' },
  };

  const style = stanceStyles[stance] || stanceStyles.INSUFFICIENT;

  const sizes = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-xs',
    lg: 'px-3 py-1.5 text-sm',
  };

  return (
    <span className={cn(
      'inline-flex items-center font-medium rounded-full border',
      style.bg,
      style.text,
      `dark:${style.bg.replace('100', '900/30')} dark:${style.text.replace('800', '300')} dark:${style.border.replace('200', '800')}`,
      sizes[size]
    )}>
      {style.label}
    </span>
  );
}

// -----------------------------------------------------------------------------
// Source Type Badge
// -----------------------------------------------------------------------------

interface SourceTypeBadgeProps {
  sourceType: string;
  size?: 'sm' | 'md' | 'lg';
}

export function SourceTypeBadge({ sourceType, size = 'md' }: SourceTypeBadgeProps) {
  const sourceStyles: Record<string, { bg: string; text: string; border: string; label: string }> = {
    official: { bg: 'bg-blue-100', text: 'text-blue-800', border: 'border-blue-200', label: 'Official' },
    fact_checker: { bg: 'bg-green-100', text: 'text-green-800', border: 'border-green-200', label: 'Fact-Checker' },
    news: { bg: 'bg-purple-100', text: 'text-purple-800', border: 'border-purple-200', label: 'News' },
    social: { bg: 'bg-orange-100', text: 'text-orange-800', border: 'border-orange-200', label: 'Social' },
    unknown: { bg: 'bg-gray-100', text: 'text-gray-800', border: 'border-gray-200', label: 'Unknown' },
  };

  const style = sourceStyles[sourceType] || sourceStyles.unknown;

  const sizes = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-xs',
    lg: 'px-3 py-1.5 text-sm',
  };

  return (
    <span className={cn(
      'inline-flex items-center font-medium rounded-full border',
      style.bg,
      style.text,
      `dark:${style.bg.replace('100', '900/30')} dark:${style.text.replace('800', '300')} dark:${style.border.replace('200', '800')}`,
      sizes[size]
    )}>
      {style.label}
    </span>
  );
}

// -----------------------------------------------------------------------------
// Status Indicator
// -----------------------------------------------------------------------------

interface StatusIndicatorProps {
  status: 'online' | 'offline' | 'busy' | 'away' | 'checking' | 'degraded';
  size?: 'sm' | 'md' | 'lg';
  label?: string;
}

export function StatusIndicator({ status, size = 'md', label }: StatusIndicatorProps) {
  const statusStyles: Record<string, { bg: string; pulse: boolean }> = {
    online: { bg: 'bg-green-500', pulse: false },
    offline: { bg: 'bg-gray-400', pulse: false },
    busy: { bg: 'bg-red-500', pulse: false },
    away: { bg: 'bg-amber-500', pulse: false },
    checking: { bg: 'bg-blue-500', pulse: true },
    degraded: { bg: 'bg-amber-500', pulse: false },
  };

  const style = statusStyles[status] || statusStyles.offline;

  const sizes = {
    sm: 'w-2 h-2',
    md: 'w-3 h-3',
    lg: 'w-4 h-4',
  };

  return (
    <span className="inline-flex items-center gap-2">
      <span className={cn(
        'rounded-full',
        style.bg,
        sizes[size],
        style.pulse && 'animate-pulse'
      )} />
      {label && <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{label}</span>}
    </span>
  );
}