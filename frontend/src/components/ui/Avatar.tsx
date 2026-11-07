// ============================================================
// TruthLens - Avatar Components
// ============================================================

import { cn } from '../../lib/utils';
import { User as UserIcon } from 'lucide-react';

// -----------------------------------------------------------------------------
// Avatar
// -----------------------------------------------------------------------------

interface AvatarProps {
  src?: string | null;
  alt?: string;
  name?: string;
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl';
  shape?: 'circle' | 'square';
  status?: 'online' | 'offline' | 'busy' | 'away';
  className?: string;
}

export function Avatar({ src, alt, name, size = 'md', shape = 'circle', status, className }: AvatarProps) {
  const sizes = {
    xs: 'w-6 h-6 text-xs',
    sm: 'w-8 h-8 text-sm',
    md: 'w-10 h-10 text-base',
    lg: 'w-12 h-12 text-lg',
    xl: 'w-16 h-16 text-xl',
    '2xl': 'w-24 h-24 text-2xl',
  };

  const statusSizes = {
    xs: 'w-1.5 h-1.5',
    sm: 'w-2 h-2',
    md: 'w-2.5 h-2.5',
    lg: 'w-3 h-3',
    xl: 'w-3.5 h-3.5',
    '2xl': 'w-4 h-4',
  };

  const statusColors = {
    online: 'bg-green-500',
    offline: 'bg-gray-400',
    busy: 'bg-red-500',
    away: 'bg-amber-500',
  };

  // Generate consistent color from name
  const getColorFromName = (str: string) => {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const hue = hash % 360;
    return `hsl(${hue}, 70%, 45%)`;
  };

  const getInitials = (str: string) => {
    return str
      .split(' ')
      .map((part) => part[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  const backgroundColor = name ? getColorFromName(name) : '#6366f1';

  return (
    <div className={cn('relative inline-flex shrink-0', className)}>
      {src ? (
        <img
          src={src}
          alt={alt || name || 'Avatar'}
          className={cn(
            'object-cover',
            sizes[size],
            shape === 'circle' ? 'rounded-full' : 'rounded-lg'
          )}
        />
      ) : (
        <div
          className={cn(
            'flex items-center justify-center font-medium text-white',
            sizes[size],
            shape === 'circle' ? 'rounded-full' : 'rounded-lg'
          )}
          style={{ backgroundColor }}
        >
          {name ? getInitials(name) : <UserIcon className="w-full h-full" />}
        </div>
      )}
      {status && (
        <span
          className={cn(
            'absolute bottom-0 right-0 border-2 border-white dark:border-gray-900 rounded-full',
            statusSizes[size],
            statusColors[status]
          )}
          aria-label={status}
        />
      )}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Avatar Group
// -----------------------------------------------------------------------------

interface AvatarGroupProps {
  avatars: Array<{
    src?: string;
    name: string;
    alt?: string;
  }>;
  max?: number;
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

export function AvatarGroup({ avatars, max = 5, size = 'md', className }: AvatarGroupProps) {
  const visibleAvatars = avatars.slice(0, max);
  const remainingCount = avatars.length - max;

  const sizes = {
    xs: 'w-6 h-6 -ml-1',
    sm: 'w-8 h-8 -ml-2',
    md: 'w-10 h-10 -ml-3',
    lg: 'w-12 h-12 -ml-4',
    xl: 'w-16 h-16 -ml-5',
  };

  return (
    <div className={cn('flex items-center', className)} role="group" aria-label={`${avatars.length} users`}>
      <div className="flex -space-x-2" aria-hidden="true">
        {visibleAvatars.map((avatar, index) => (
          <Avatar
            key={avatar.name}
            src={avatar.src}
            name={avatar.name}
            alt={avatar.alt}
            size={size}
            className={index === 0 ? '' : sizes[size]}
          />
        ))}
        {remainingCount > 0 && (
          <div
            className={cn(
              'flex items-center justify-center font-medium text-white bg-gray-500',
              sizes[size].replace('-ml-', ''),
              'rounded-full border-2 border-white dark:border-gray-900'
            )}
            style={{ marginLeft: sizes[size].match(/-ml-(\d+)/)?.[1] ? `-${sizes[size].match(/-ml-(\d+)/)?.[1]}px` : 0 }}
          >
            +{remainingCount}
          </div>
        )}
      </div>
    </div>
  );
}