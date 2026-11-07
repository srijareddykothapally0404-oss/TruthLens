// ============================================================
// TruthLens - Main Layout Component
// ============================================================

import { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { Footer } from './Footer';
import { useUIStore, useAuthStore } from '../../lib/stores';
import { cn } from '../../lib/utils';

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { theme } = useUIStore();
  const { isAuthenticated, isLoading } = useAuthStore();

  // Initialize theme on mount
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  // Handle keyboard shortcut for sidebar
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === '[' && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        setSidebarOpen(!sidebarOpen);
      }
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [sidebarOpen]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
          <p className="text-gray-600 dark:text-gray-400">Initializing TruthLens...</p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('min-h-screen bg-gray-50 dark:bg-gray-900', `data-theme-${theme}`)}>
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <Header onMenuClick={() => setSidebarOpen(true)} />
      <main className="pt-16 pb-12 lg:ml-64 min-h-screen">
        <div className="p-4 lg:p-6">
          <Outlet />
        </div>
      </main>
      <Footer />
    </div>
  );
}

// Auth Layout (for login/register pages)
export function AuthLayout() {
  const { theme } = useUIStore();

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center p-4">
      <Outlet />
    </div>
  );
}

// Simple Layout (for pages without sidebar)
export function SimpleLayout() {
  const { theme } = useUIStore();
  const { isAuthenticated } = useAuthStore();

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {isAuthenticated && <Header onMenuClick={() => {}} />}
      <main className={cn('pt-16', isAuthenticated ? 'lg:ml-64' : '')}>
        <div className="p-4 lg:p-6">
          <Outlet />
        </div>
      </main>
      {isAuthenticated && <Footer />}
    </div>
  );
}