// ============================================================
// TruthLens - Table Components
// ============================================================

import { useState, useMemo } from 'react';
import { cn } from '../../lib/utils';
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react';
import { Button } from './Button';

// -----------------------------------------------------------------------------
// Column Definition
// -----------------------------------------------------------------------------

export interface Column<T> {
  key: string;
  header: string;
  accessor: (row: T) => React.ReactNode;
  sortable?: boolean;
  width?: string;
  align?: 'left' | 'center' | 'right';
  className?: string;
  headerClassName?: string;
  render?: (value: unknown, row: T) => React.ReactNode;
}

// -----------------------------------------------------------------------------
// Table
// -----------------------------------------------------------------------------

interface TableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (row: T) => string;
  loading?: boolean;
  emptyMessage?: string;
  striped?: boolean;
  hoverable?: boolean;
  bordered?: boolean;
  compact?: boolean;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
  onSort?: (key: string, order: 'asc' | 'desc') => void;
  selection?: {
    enabled: boolean;
    selectedKeys: Set<string>;
    onSelectionChange: (keys: Set<string>) => void;
    selectAll?: boolean;
  };
  rowClassName?: (row: T) => string;
  onRowClick?: (row: T) => void;
}

export function Table<T>({
  columns,
  data,
  keyExtractor,
  loading = false,
  emptyMessage = 'No data available',
  striped = true,
  hoverable = true,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  bordered = true,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  compact = false,
  sortBy,
  sortOrder,
  onSort,
  selection,
  rowClassName,
  onRowClick,
}: TableProps<T>) {
  const [sortConfig, setSortConfig] = useState<{ key: string; order: 'asc' | 'desc' } | null>(
    sortBy && sortOrder ? { key: sortBy, order: sortOrder } : null
  );

  const handleSort = (key: string) => {
    const column = columns.find((c) => c.key === key);
    if (!column?.sortable) return;

    let newOrder: 'asc' | 'desc' = 'asc';
    if (sortConfig?.key === key && sortConfig.order === 'asc') {
      newOrder = 'desc';
    }
    setSortConfig({ key, order: newOrder });
    onSort?.(key, newOrder);
  };

  const sortedData = useMemo(() => {
    if (!sortConfig) return data;
    return [...data].sort((a, b) => {
      const aVal = columns.find((c) => c.key === sortConfig.key)?.accessor(a);
      const bVal = columns.find((c) => c.key === sortConfig.key)?.accessor(b);
      if (aVal === bVal) return 0;
      const comparison = String(aVal).localeCompare(String(bVal));
      return sortConfig.order === 'asc' ? comparison : -comparison;
    });
  }, [data, sortConfig, columns]);

  const isAllSelected = selection?.selectAll && data.length > 0 && data.every((row) => selection.selectedKeys.has(keyExtractor(row)));
  const isIndeterminate = selection?.enabled && data.some((row) => selection.selectedKeys.has(keyExtractor(row))) && !isAllSelected;

  if (loading) {
    return (
      <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
        <table className="w-full" role="grid">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col.key} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  <div className="flex items-center gap-2 animate-pulse">
                    <div className="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded" />
                    {col.sortable && <div className="w-4 h-4 bg-gray-200 dark:bg-gray-700 rounded" />}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[...Array(5)].map((_, i) => (
              <tr key={i}>
                {columns.map(() => (
                  <td key={Math.random()} className="px-4 py-3">
                    <div className="h-4 w-3/4 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
      <table className="w-full" role="grid">
        <thead className="bg-gray-50 dark:bg-gray-800/50">
          <tr className="border-b border-gray-200 dark:border-gray-700">
            {selection?.enabled && (
              <th className="px-4 py-3 w-12">
                <input
                  type="checkbox"
                  checked={isAllSelected ?? false}
                  ref={(el) => { if (el) el.indeterminate = isIndeterminate ?? false; }}
                  onChange={() => {
                    if (isAllSelected) {
                      selection.onSelectionChange(new Set());
                    } else {
                      const newSelection = new Set(selection.selectedKeys);
                      data.forEach((row) => newSelection.add(keyExtractor(row)));
                      selection.onSelectionChange(newSelection);
                    }
                  }}
                  className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-2 focus:ring-blue-500"
                  aria-label="Select all rows"
                />
              </th>
            )}
            {columns.map((col) => (
              <th
                key={col.key}
                scope="col"
                className={cn(
                  'px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider',
                  col.align === 'center' && 'text-center',
                  col.align === 'right' && 'text-right',
                  col.sortable && 'cursor-pointer select-none hover:bg-gray-100 dark:hover:bg-gray-700/50',
                  col.headerClassName
                )}
                style={{ width: col.width }}
                onClick={() => col.sortable && handleSort(col.key)}
              >
                <div className="flex items-center justify-center gap-1.5">
                  <span>{col.header}</span>
                  {col.sortable && (
                    <span className="flex-shrink-0">
                      {sortConfig?.key === col.key ? (
                        sortConfig.order === 'asc' ? <ChevronUp className="w-4 h-4 text-blue-600" /> : <ChevronDown className="w-4 h-4 text-blue-600" />
                      ) : (
                        <ChevronsUpDown className="w-4 h-4 text-gray-400" />
                      )}
                    </span>
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
          {sortedData.length === 0 ? (
            <tr>
              <td colSpan={columns.length + (selection?.enabled ? 1 : 0)} className="px-4 py-12 text-center">
                <p className="text-gray-500 dark:text-gray-400">{emptyMessage}</p>
              </td>
            </tr>
          ) : (
            sortedData.map((row, rowIndex) => (
              <tr
                key={keyExtractor(row)}
                className={cn(
                  'transition-colors',
                  striped && rowIndex % 2 === 1 && 'bg-gray-50 dark:bg-gray-800/50',
                  hoverable && 'hover:bg-gray-50 dark:hover:bg-gray-800/50',
                  onRowClick && 'cursor-pointer',
                  rowClassName?.(row)
                )}
                onClick={() => onRowClick?.(row)}
              >
                {selection?.enabled && (
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selection.selectedKeys.has(keyExtractor(row))}
                      onChange={(e) => {
                        const newSelection = new Set(selection.selectedKeys);
                        if (e.target.checked) {
                          newSelection.add(keyExtractor(row));
                        } else {
                          newSelection.delete(keyExtractor(row));
                        }
                        selection.onSelectionChange(newSelection);
                      }}
                      className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-2 focus:ring-blue-500"
                      aria-label="Select row"
                    />
                  </td>
                )}
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={cn(
                      'px-4 py-3 text-sm text-gray-700 dark:text-gray-300',
                      col.align === 'center' && 'text-center',
                      col.align === 'right' && 'text-right',
                      col.className
                    )}
                    style={{ width: col.width }}
                  >
                    {col.render ? col.render(col.accessor(row), row) : col.accessor(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Pagination
// -----------------------------------------------------------------------------

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (size: number) => void;
  pageSizeOptions?: number[];
  showPageSizeSelector?: boolean;
}

export function Pagination({
  currentPage,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 50, 100],
  showPageSizeSelector = true,
}: PaginationProps) {
  const startItem = (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, totalItems);

  if (totalPages <= 1 && !showPageSizeSelector) return null;

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-4 p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 rounded-b-lg">
      <div className="text-sm text-gray-600 dark:text-gray-400">
        Showing <span className="font-medium">{startItem}</span> to <span className="font-medium">{endItem}</span> of <span className="font-medium">{totalItems}</span> results
      </div>

      <div className="flex items-center gap-2">
        {showPageSizeSelector && onPageSizeChange && (
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {pageSizeOptions.map((size) => (
              <option key={size} value={size}>
                {size} per page
              </option>
            ))}
          </select>
        )}

        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(currentPage - 1)}
            disabled={currentPage <= 1}
            aria-label="Previous page"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </Button>

          <div className="flex items-center gap-1">
            {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
              let pageNum: number;
              if (totalPages <= 5) {
                pageNum = i + 1;
              } else if (currentPage <= 3) {
                pageNum = i + 1;
              } else if (currentPage >= totalPages - 2) {
                pageNum = totalPages - 4 + i;
              } else {
                pageNum = currentPage - 2 + i;
              }
              return (
                <Button
                  key={pageNum}
                  variant={currentPage === pageNum ? 'primary' : 'ghost'}
                  size="sm"
                  onClick={() => onPageChange(pageNum)}
                  className="w-8 h-8"
                >
                  {pageNum}
                </Button>
              );
            })}
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(currentPage + 1)}
            disabled={currentPage >= totalPages}
            aria-label="Next page"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </Button>
        </div>
      </div>
    </div>
  );
}