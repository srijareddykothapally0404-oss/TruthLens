// ============================================================
// TruthLens - Sidebar Navigation Component
// ============================================================

import { useLocation, NavLink, useNavigate } from 'react-router-dom';
import {
  House,
  Search,
  Clock3,
  CircleHelp,
  Activity,
  Shield,
  Users,
  Settings,
  BarChart2,
  FileText,
  LogOut,
  Menu,
  X,
  ChevronDown,
  Bell,
  History,
  Database,
  Wifi,
  Zap,
} from 'lucide-react';
import { useAuthStore } from '../../lib/stores';
import { cn, getRoleLabel, getRoleColor } from '../../lib/utils';
import type { NavItem } from './types';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

const navigationItems: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: House, roles: ['admin', 'analyst', 'reviewer', 'viewer'] },
  { to: '/verify', label: 'Verify News', icon: Search, roles: ['admin', 'analyst', 'reviewer', 'viewer'], badge: 'NEW' },
  { to: '/history', label: 'Verification History', icon: History, roles: ['admin', 'analyst', 'reviewer', 'viewer'] },
  { to: '/monitoring', label: 'Live Monitoring', icon: Activity, roles: ['admin', 'analyst'] },
  { to: '/api-docs', label: 'API Reference', icon: FileText, roles: ['admin', 'analyst', 'reviewer'] },
  { to: '/settings', label: 'Settings', icon: Settings, roles: ['admin', 'analyst', 'reviewer', 'viewer'] },
  { to: '/admin', label: 'Administration', icon: Shield, roles: ['admin'] },
];

const bottomItems: NavItem[] = [
  { to: '/about', label: 'About TruthLens', icon: CircleHelp, roles: ['admin', 'analyst', 'reviewer', 'viewer'] },
  { to: '/status', label: 'System Status', icon: Wifi, roles: ['admin', 'analyst', 'reviewer', 'viewer'] },
];

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, hasRole, logout } = useAuthStore();

  const filteredItems = navigationItems.filter((item) => hasRole(item.roles));
  const filteredBottomItems = bottomItems.filter((item) => hasRole(item.roles));

  const handleNavClick = (to: string) => {
    navigate(to);
    onClose();
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed top-0 left-0 z-50 h-screen w-64 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700',
          'transform transition-transform duration-300 ease-in-out lg:translate-x-0',
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}
        aria-label="Main navigation"
      >
        <div className="flex flex-col h-full">
          {/* Header / Brand */}
          <div className="flex items-center justify-between h-16 px-4 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-700">
                <Shield className="w-5 h-5 text-white" />
              </div>
              <div>
                <div className="font-bold text-xl text-gray-900 dark:text-white">TruthLens</div>
                <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">GOV Platform</div>
              </div>
            </div>
            <button
              className="lg:hidden p-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800"
              onClick={onClose}
              aria-label="Close navigation"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1" aria-label="Main navigation">
            {/* Main Navigation */}
            <div>
              <h3 className="px-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                Workspace
              </h3>
              {filteredItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={() => handleNavClick(item.to)}
                  end={item.to === '/'}
                  className={({ isActive }) => cn(
                    'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-300'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50 dark:text-gray-300 dark:hover:text-white dark:hover:bg-gray-800'
                  )}
                  aria-current={item.to === location.pathname ? 'page' : undefined}
                >
                  <item.icon className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
                  <span className="flex-1 truncate">{item.label}</span>
                  {item.badge && (
                    <span className="text-xs px-1.5 py-0.5 bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 rounded-full">
                      {item.badge}
                    </span>
                  )}
                </NavLink>
              ))}
            </div>

            {/* Divider */}
            <div className="my-4 border-t border-gray-200 dark:border-gray-700" />

            {/* Bottom Navigation */}
            <div>
              <h3 className="px-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                System
              </h3>
              {filteredBottomItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={() => handleNavClick(item.to)}
                  className={({ isActive }) => cn(
                    'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-300'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50 dark:text-gray-300 dark:hover:text-white dark:hover:bg-gray-800'
                  )}
                >
                  <item.icon className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
                  <span className="flex-1 truncate">{item.label}</span>
                </NavLink>
              ))}
            </div>
          </nav>

          {/* User Section */}
          <div className="p-3 border-t border-gray-200 dark:border-gray-700">
            {user && (
              <div className="flex items-center gap-3 p-2 rounded-lg bg-gray-50 dark:bg-gray-800/50">
                <div className="flex items-center justify-center w-8 h-8 rounded-full bg-gradient-to-br from-blue-600 to-indigo-700 text-white font-medium">
                  {user.full_name.charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-900 dark:text-white truncate">{user.full_name}</div>
                  <div className="flex items-center gap-1.5">
                    <span className={cn('text-xs px-1.5 py-0.5 rounded-full', getRoleColor(user.role))}>
                      {getRoleLabel(user.role)}
                    </span>
                    {user.clearance_level !== 'public' && (
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        {user.clearance_level.toUpperCase()}
                      </span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => { logout(); navigate('/login'); }}
                  className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                  aria-label="Sign out"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}