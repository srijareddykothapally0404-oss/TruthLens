// ============================================================
// TruthLens - Dropdown Component
// ============================================================

import { useState, useRef, useEffect } from 'react';
import { cn } from '../../lib/utils';
import { createPortal } from 'react-dom';
import { ChevronDown, Check } from 'lucide-react';

// -----------------------------------------------------------------------------
// Dropdown
// -----------------------------------------------------------------------------

interface DropdownItem {
  label: string;
  value: string;
  icon?: React.ReactNode;
  disabled?: boolean;
  danger?: boolean;
  divider?: boolean;
  shortcut?: string;
}

interface DropdownProps {
  trigger: React.ReactNode;
  items: DropdownItem[];
  onSelect: (value: string) => void;
  align?: 'left' | 'right';
  width?: number | 'trigger';
  maxHeight?: number;
  closeOnSelect?: boolean;
}

export function Dropdown({
  trigger,
  items,
  onSelect,
  align = 'right',
  width = 'trigger',
  maxHeight = 300,
  closeOnSelect = true,
}: DropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (!isOpen) return;
      if (event.key === 'Escape') {
        setIsOpen(false);
        triggerRef.current?.focus();
      }
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  const dropdownContent = isOpen ? (
    <div
      ref={dropdownRef}
      className={cn(
        'fixed z-50 mt-1.5 rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-lg',
        'py-1 min-w-[160px]',
        align === 'right' ? 'right-0' : 'left-0',
        typeof width === 'number' ? `w-[${width}px]` : width === 'trigger' ? 'w-auto' : ''
      )}
      style={{ maxHeight, overflow: 'auto' }}
      role="menu"
      aria-orientation="vertical"
    >
      {items.map((item, index) => (
        item.divider ? (
          <hr key={`divider-${index}`} className="my-1 border-gray-200 dark:border-gray-700" />
        ) : (
          <button
            key={item.value}
            onClick={() => {
              onSelect(item.value);
              if (closeOnSelect) setIsOpen(false);
            }}
            disabled={item.disabled}
            className={cn(
              'w-full px-3 py-2 text-left text-sm flex items-center gap-2',
              'hover:bg-gray-50 dark:hover:bg-gray-700/50',
              'focus:outline-none focus:bg-gray-50 dark:focus:bg-gray-700/50',
              item.disabled ? 'opacity-50 cursor-not-allowed' : '',
              item.danger ? 'text-red-600 dark:text-red-400' : 'text-gray-700 dark:text-gray-300'
            )}
            role="menuitem"
            tabIndex={-1}
          >
            {item.icon && <span className="w-4 h-4 flex-shrink-0">{item.icon}</span>}
            <span className="flex-1">{item.label}</span>
            {item.shortcut && <span className="text-xs text-gray-400 dark:text-gray-500">{item.shortcut}</span>}
          </button>
        )
      ))}
    </div>
  ) : null;

  return (
    <div className="relative inline-block">
      <button
        ref={triggerRef}
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1"
        aria-haspopup="menu"
        aria-expanded={isOpen}
      >
        {trigger}
        <ChevronDown className={cn('w-4 h-4 transition-transform', isOpen && 'rotate-180')} />
      </button>
      {createPortal(dropdownContent, document.body)}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Select Dropdown (for form selects)
// -----------------------------------------------------------------------------

interface SelectDropdownProps {
  value: string;
  placeholder: string;
  options: { value: string; label: string; disabled?: boolean }[];
  onChange: (value: string) => void;
  disabled?: boolean;
  error?: boolean;
  className?: string;
}

export function SelectDropdown({
  value,
  placeholder,
  options,
  onChange,
  disabled,
  error,
  className,
}: SelectDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className={cn(
          'w-full px-4 py-2.5 text-left rounded-lg border bg-white dark:bg-gray-800',
          'transition-colors duration-200',
          'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          error
            ? 'border-red-500 focus:ring-red-500'
            : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
        )}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <span className={cn('flex-1 truncate', value ? 'text-gray-900 dark:text-white' : 'text-gray-400 dark:text-gray-500')}>
          {value ? options.find(o => o.value === value)?.label || value : placeholder}
        </span>
        <ChevronDown className={cn('w-4 h-4 text-gray-400 flex-shrink-0 transition-transform', isOpen && 'rotate-180')} />
      </button>

      {isOpen && (
        <div
          className={cn(
            'fixed z-50 mt-1.5 rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-lg',
            'py-1 max-h-60 overflow-auto',
            'w-full left-0'
          )}
          role="listbox"
        >
          {options.map((option) => (
            <button
              key={option.value}
              onClick={() => {
                if (!option.disabled) {
                  onChange(option.value);
                  setIsOpen(false);
                }
              }}
              disabled={option.disabled}
              className={cn(
                'w-full px-4 py-2 text-left text-sm',
                'hover:bg-gray-50 dark:hover:bg-gray-700/50',
                'focus:outline-none focus:bg-gray-50 dark:focus:bg-gray-700/50',
                option.disabled ? 'opacity-50 cursor-not-allowed' : '',
                value === option.value ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300' : 'text-gray-700 dark:text-gray-300'
              )}
              role="option"
              aria-selected={value === option.value}
            >
              <span className="flex-1">{option.label}</span>
              {value === option.value && <Check className="w-4 h-4 flex-shrink-0" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}