// ============================================================
// TruthLens - Card Components
// ============================================================

import { cn } from '../../lib/utils';
import { ReactNode } from 'react';

// -----------------------------------------------------------------------------
// Card
// -----------------------------------------------------------------------------

interface CardProps {
  children: ReactNode;
  className?: string;
  variant?: 'default' | 'outlined' | 'elevated' | 'interactive';
  padding?: 'none' | 'sm' | 'md' | 'lg';
  onClick?: () => void;
}

export function Card({ children, className, variant = 'default', padding = 'md', onClick }: CardProps) {
  const variants = {
    default: 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700',
    outlined: 'bg-transparent border-2 border-gray-200 dark:border-gray-700',
    elevated: 'bg-white dark:bg-gray-800 shadow-lg border-none',
    interactive: 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:shadow-md hover:border-blue-300 dark:hover:border-blue-700 transition-all duration-200 cursor-pointer',
  };

  const paddings = {
    none: '',
    sm: 'p-4',
    md: 'p-6',
    lg: 'p-8',
  };

  return (
    <div
      className={cn(
        'rounded-xl',
        variants[variant],
        paddings[padding],
        className
      )}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); }} : undefined}
    >
      {children}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Card Header
// -----------------------------------------------------------------------------

interface CardHeaderProps {
  children: ReactNode;
  className?: string;
  action?: ReactNode;
}

export function CardHeader({ children, className, action }: CardHeaderProps) {
  return (
    <div className={cn('flex items-center justify-between mb-4', className)}>
      <div>{children}</div>
      {action && <div className="flex-shrink-0 ml-4">{action}</div>}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Card Title
// -----------------------------------------------------------------------------

interface CardTitleProps {
  children: ReactNode;
  className?: string;
  subtitle?: string;
}

export function CardTitle({ children, className, subtitle }: CardTitleProps) {
  return (
    <div>
      <h3 className={cn('text-lg font-semibold text-gray-900 dark:text-white', className)}>
        {children}
      </h3>
      {subtitle && (
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{subtitle}</p>
      )}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Card Content
// -----------------------------------------------------------------------------

interface CardContentProps {
  children: ReactNode;
  className?: string;
}

export function CardContent({ children, className }: CardContentProps) {
  return <div className={cn('text-gray-700 dark:text-gray-300', className)}>{children}</div>;
}

// -----------------------------------------------------------------------------
// Card Footer
// -----------------------------------------------------------------------------

interface CardFooterProps {
  children: ReactNode;
  className?: string;
}

export function CardFooter({ children, className }: CardFooterProps) {
  return (
    <div className={cn('flex items-center justify-end gap-3 mt-4 pt-4 border-t border-gray-200 dark:border-gray-700', className)}>
      {children}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Stats Card
// -----------------------------------------------------------------------------

interface StatsCardProps {
  title: string;
  value: string | number;
  icon: ReactNode;
  trend?: {
    value: number;
    label: string;
    positive: boolean;
  };
  color?: 'blue' | 'green' | 'red' | 'amber' | 'purple' | 'gray';
  className?: string;
}

export function StatsCard({ title, value, icon, trend, color = 'blue', className }: StatsCardProps) {
  const colors = {
    blue: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-200 dark:border-blue-800',
    green: 'bg-green-500/10 text-green-600 dark:text-green-400 border-green-200 dark:border-green-800',
    red: 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-200 dark:border-red-800',
    amber: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-800',
    purple: 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-200 dark:border-purple-800',
    gray: 'bg-gray-500/10 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-800',
  };

  return (
    <Card className={className}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{title}</p>
          <p className="text-3xl font-bold text-gray-900 dark:text-white mt-1">{value}</p>
          {trend && (
            <div className="flex items-center gap-1 mt-2">
              <span className={cn('text-sm font-medium', trend.positive ? 'text-green-600' : 'text-red-600')}>
                {trend.positive ? '↑' : '↓'} {Math.abs(trend.value)}%
              </span>
              <span className="text-sm text-gray-500 dark:text-gray-400">{trend.label}</span>
            </div>
          )}
        </div>
        <div className={cn('p-3 rounded-xl', colors[color])}>
          {icon}
        </div>
      </div>
    </Card>
  );
}