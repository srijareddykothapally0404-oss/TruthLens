// ============================================================
// TruthLens - Footer Component
// ============================================================

import { Shield, Github, BookOpen, Mail, ExternalLink } from 'lucide-react';

export function Footer() {
  return (
    <footer className="fixed bottom-0 left-0 right-0 z-20 bg-white/95 dark:bg-gray-900/95 backdrop-blur-sm border-t border-gray-200 dark:border-gray-700 lg:ml-64">
      <div className="flex items-center justify-between px-4 lg:px-6 h-12">
        <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
          <span className="flex items-center gap-1.5">
            <Shield className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            TruthLens Government Platform
          </span>
          <span className="hidden sm:inline">v2.0.0</span>
        </div>

        <div className="flex items-center gap-4 text-sm">
          <a href="/docs" className="flex items-center gap-1.5 text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors">
            <BookOpen className="w-4 h-4" />
            Documentation
          </a>
          <a href="https://github.com/truthlens" target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors">
            <Github className="w-4 h-4" />
            GitHub
          </a>
          <a href="mailto:support@truthlens.gov" className="flex items-center gap-1.5 text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors">
            <Mail className="w-4 h-4" />
            Support
          </a>
        </div>

        <div className="flex items-center gap-2 text-xs text-gray-400 dark:text-gray-500">
          <span>Government Use Authorized</span>
          <ExternalLink className="w-3 h-3" />
        </div>
      </div>
    </footer>
  );
}