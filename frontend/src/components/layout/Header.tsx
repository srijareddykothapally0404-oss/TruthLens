// ============================================================
// TruthLens - Header Component
// ============================================================

import { useState, useRef, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { Menu, Sun, Moon, Bell, ChevronDown, Shield, Wifi, WifiOff, Loader2, User, Settings, LogOut, HelpCircle, Activity } from 'lucide-react';
import { useAuthStore, useHealthStore, useUIStore } from '../../lib/stores';
import { cn, formatRelativeTime, getRoleLabel, getRoleColor, getClearanceLabel, getClearanceColor } from '../../lib/utils';
import type { NavItem } from './types';

interface HeaderProps {
  onMenuClick: () => void;
}

export function Header({ onMenuClick }: HeaderProps) {
  const location = useLocation();
  const { user, logout, hasRole } = useAuthStore();
  const { health, checking } = useHealthStore();
  const { theme, toggleTheme, addToast } = useUIStore();
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const notificationsRef = useRef<HTMLDivElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (notificationsRef.current && !notificationsRef.current.contains(event.target as Node)) {
        setNotificationsOpen(false);
      }
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const pageTitles: Record<string, string> = {
    '/': 'Dashboard',
    '/verify': 'Verify News',
    '/history': 'Verification History',
    '/monitoring': 'Live Monitoring',
    '/api-docs': 'API Reference',
    '/settings': 'Settings',
    '/admin': 'Administration',
    '/about': 'About TruthLens',
    '/status': 'System Status',
  };

  const title = pageTitles[location.pathname] || 'TruthLens';

  const handleLogout = () => {
    logout();
    addToast({ type: 'info', message: 'You have been signed out' });
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-30 h-16 bg-white/95 dark:bg-gray-900/95 backdrop-blur-sm border-b border-gray-200 dark:border-gray-700 lg:ml-64">
      <div className="flex items-center justify-between h-full px-4 lg:px-6">
        {/* Left Side - Menu Button & Breadcrumbs */}
        <div className="flex items-center gap-4">
          <button
            className="lg:hidden p-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800"
            onClick={onMenuClick}
            aria-label="Open navigation menu"
          >
            <Menu className="w-5 h-5" />
          </button>

          <nav className="hidden md:flex items-center gap-1 text-sm" aria-label="Breadcrumb">
            <span className="text-gray-500 dark:text-gray-400">TruthLens</span>
            <ChevronDown className="w-4 h-4 text-gray-400" />
            <span className="font-medium text-gray-900 dark:text-white">{title}</span>
          </nav>
        </div>

        {/* Right Side - Actions */}
        <div className="flex items-center gap-2">
          {/* System Health Indicator */}
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-gray-50 dark:bg-gray-800/50">
            <div className={cn(
              'w-2 h-2 rounded-full',
              health?.status === 'ok' ? 'bg-green-500' :
              health?.status === 'degraded' ? 'bg-amber-500' :
              checking ? 'bg-blue-500 animate-pulse' : 'bg-red-500'
            )} />
            <span className="text-xs font-medium text-gray-700 dark:text-gray-300">
              {checking ? 'Checking...' : health?.status === 'ok' ? 'System Online' : health?.status === 'degraded' ? 'Degraded' : 'Offline'}
            </span>
          </div>

          {/* Theme Toggle */}
          <button
            onClick={toggleTheme}
            className="p-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            aria-label={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
          >
            {theme === 'light' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
          </button>

          {/* Notifications */}
          <div className="relative" ref={notificationsRef}>
            <button
              onClick={() => setNotificationsOpen(!notificationsOpen)}
              className="p-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors relative"
              aria-label="Notifications"
              aria-expanded={notificationsOpen}
            >
              <Bell className="w-5 h-5" />
              <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                3
              </span>
            </button>

            {notificationsOpen && (
              <div className="absolute right-0 top-full mt-2 w-80 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-2 z-50">
                <div className="px-4 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                  <h3 className="font-semibold text-gray-900 dark:text-white">Notifications</h3>
                  <button className="text-sm text-blue-600 hover:text-blue-700">Mark all read</button>
                </div>
                <div className="max-h-64 overflow-y-auto">
                  <div className="px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 border-b border-gray-100 dark:border-gray-700">
                    <p className="text-sm font-medium text-gray-900 dark:text-white">Verification completed</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Verification #VRF-2024-001234 completed with verdict: TRUE</p>
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">2 minutes ago</p>
                  </div>
                  <div className="px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 border-b border-gray-100 dark:border-gray-700">
                    <p className="text-sm font-medium text-gray-900 dark:text-white">Monitoring job alert</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Job "Election Monitoring" found 3 new claims requiring review</p>
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">15 minutes ago</p>
                  </div>
                  <div className="px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <p className="text-sm font-medium text-gray-900 dark:text-white">System maintenance scheduled</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Planned maintenance tonight 02:00-04:00 UTC</p>
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">1 hour ago</p>
                  </div>
                </div>
                <div className="px-4 py-2 border-t border-gray-200 dark:border-gray-700">
                  <button className="w-full text-center text-sm text-blue-600 hover:text-blue-700">View all notifications</button>
                </div>
              </div>
            )}
          </div>

          {/* User Menu */}
          <div className="relative" ref={userMenuRef}>
            <button
              onClick={() => setUserMenuOpen(!userMenuOpen)}
              className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
              aria-label="User menu"
              aria-expanded={userMenuOpen}
            >
              <div className="flex items-center justify-center w-8 h-8 rounded-full bg-gradient-to-br from-blue-600 to-indigo-700 text-white font-medium">
                {user?.full_name?.charAt(0).toUpperCase() || 'U'}
              </div>
              <div className="hidden md:block text-left">
                <div className="text-sm font-medium text-gray-900 dark:text-white">{user?.full_name || 'User'}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400">{getRoleLabel(user?.role || 'viewer')}</div>
              </div>
              <ChevronDown className="w-4 h-4 text-gray-500" />
            </button>

            {userMenuOpen && (
              <div className="absolute right-0 top-full mt-2 w-56 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-2 z-50">
                <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
                  <div className="flex items-center gap-3">
                    <div className="flex items-center justify-center w-10 h-10 rounded-full bg-gradient-to-br from-blue-600 to-indigo-700 text-white font-medium">
                      {user?.full_name?.charAt(0).toUpperCase() || 'U'}
                    </div>
                    <div>
                      <div className="font-medium text-gray-900 dark:text-white">{user?.full_name || 'User'}</div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">{user?.email || ''}</div>
                    </div>
                  </div>
                  <div className="mt-2 flex gap-1.5 flex-wrap">
                    <span className={cn('text-xs px-2 py-0.5 rounded-full', getRoleColor(user?.role || 'viewer'))}>
                      {getRoleLabel(user?.role || 'viewer')}
                    </span>
                    <span className={cn('text-xs px-2 py-0.5 rounded-full', getClearanceColor(user?.clearance_level || 'public'))}>
                      {getClearanceLabel(user?.clearance_level || 'public')}
                    </span>
                  </div>
                </div>
                <nav className="px-2 py-1">
                  <a href="/settings/profile" className="flex items-center gap-3 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700">
                    <User className="w-4 h-4" />
                    Profile
                  </a>
                  <a href="/settings" className="flex items-center gap-3 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700">
                    <Settings className="w-4 h-4" />
                    Settings
                  </a>
                  <a href="/help" className="flex items-center gap-3 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700">
                    <HelpCircle className="w-4 h-4" />
                    Help & Docs
                  </a>
                  {hasRole(['admin']) && (
                    <a href="/admin" className="flex items-center gap-3 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700">
                      <Shield className="w-4 h-4" />
                      Administration
                    </a>
                  )}
                </nav>
                <div className="border-t border-gray-200 dark:border-gray-700 pt-2 px-2">
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-3 px-3 py-2 text-sm text-red-600 dark:text-red-400 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20"
                  >
                    <LogOut className="w-4 h-4" />
                    Sign Out
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}