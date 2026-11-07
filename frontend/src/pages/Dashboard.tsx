// ============================================================
// TruthLens - Dashboard Page
// ============================================================

import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Shield,
  Search,
  Clock,
  TrendingUp,
  Activity,
  AlertTriangle,
  CheckCircle,
  XCircle,
  HelpCircle,
  ExternalLink,
  Plus,
  BarChart2,
  Bell,
  Settings,
  User,
  LogOut,
  ChevronDown,
  MoreVertical,
} from 'lucide-react';
import { useAuthStore, useVerificationStore, useHealthStore, useUIStore } from '../lib/stores';
import { verificationApi, healthApi } from '../lib/api';
import {
  Button,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  StatsCard,
  Badge,
  VerdictBadge,
  Dropdown,
  Avatar,
  AvatarGroup,
} from '../components/ui';
import { formatRelativeTime, formatDateTime, getVerdictColor } from '../lib/utils';
import { cn } from '../lib/utils';

export function Dashboard() {
  const { user, fetchUser } = useAuthStore();
  const { fetchHistory, stats, isLoading } = useVerificationStore();
  const { fetchHealth, systemHealth, isLoading: healthLoading } = useHealthStore();
  const { sidebarOpen, toggleSidebar } = useUIStore();

  useEffect(() => {
    fetchUser();
    fetchHistory();
    fetchHealth();
  }, [fetchUser, fetchHistory, fetchHealth]);

  const recentVerifications = stats?.recent_verifications || [];

  const quickActions = [
    {
      title: 'Verify Text',
      description: 'Analyze text content for misinformation',
      icon: Search,
      href: '/verify?type=text',
      color: 'from-blue-500 to-blue-600',
    },
    {
      title: 'Verify URL',
      description: 'Extract and verify claims from a webpage',
      icon: ExternalLink,
      href: '/verify?type=url',
      color: 'from-green-500 to-green-600',
    },
    {
      title: 'Verify Image',
      description: 'OCR and verify text from images',
      icon: Shield,
      href: '/verify?type=image',
      color: 'from-purple-500 to-purple-600',
    },
    {
      title: 'View History',
      description: 'Browse all past verifications',
      icon: Clock,
      href: '/history',
      color: 'from-gray-500 to-gray-600',
    },
  ];

  const statsCards = [
    {
      title: 'Total Verifications',
      value: stats?.total_verifications || 0,
      icon: Shield,
      trend: stats?.verifications_change || 0,
      trendLabel: 'vs last month',
      color: 'blue',
    },
    {
      title: 'False Claims Detected',
      value: stats?.false_claims || 0,
      icon: AlertTriangle,
      trend: stats?.false_claims_change || 0,
      trendLabel: 'vs last month',
      color: 'red',
    },
    {
      title: 'True Claims Verified',
      value: stats?.true_claims || 0,
      icon: CheckCircle,
      trend: stats?.true_claims_change || 0,
      trendLabel: 'vs last month',
      color: 'green',
    },
    {
      title: 'Avg. Confidence',
      value: `${Math.round(stats?.avg_confidence || 0)}%`,
      icon: TrendingUp,
      trend: stats?.confidence_change || 0,
      trendLabel: 'vs last month',
      color: 'purple',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Dashboard</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Welcome back, {user?.first_name || 'Analyst'}. Here's your verification overview.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" leftIcon={<Bell className="w-4 h-4" />}>
            Notifications
          </Button>
          <Button variant="primary" size="sm" leftIcon={<Plus className="w-4 h-4" />} onClick={() => window.location.href = '/verify?type=text'}>
            New Verification
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statsCards.map((stat) => (
          <StatsCard
            key={stat.title}
            title={stat.title}
            value={stat.value}
            icon={stat.icon}
            trend={stat.trend}
            trendLabel={stat.trendLabel}
            color={stat.color as any}
          />
        ))}
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Quick Actions */}
        <div className="lg:col-span-1 space-y-4">
          <Card variant="outlined" padding="lg">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart2 className="w-5 h-5" />
                Quick Actions
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {quickActions.map((action) => (
                <Link
                  key={action.title}
                  to={action.href}
                  className="group flex items-center gap-3 p-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-700 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-all"
                >
                  <div className={cn('flex items-center justify-center w-10 h-10 rounded-lg', action.color)}>
                    <action.icon className="w-5 h-5 text-white" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400">{action.title}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{action.description}</p>
                  </div>
                  <ChevronDown className="w-4 h-4 text-gray-400" />
                </Link>
              ))}
            </CardContent>
          </Card>

          {/* System Health */}
          <Card variant="outlined" padding="lg">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="w-5 h-5" />
                System Status
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {healthLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="flex items-center justify-between animate-pulse">
                      <div className="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded" />
                      <div className="h-4 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
                    </div>
                  ))}
                </div>
              ) : systemHealth ? (
                <>
                  <div className="flex items-center gap-3">
                    <div
                      className={cn(
                        'w-3 h-3 rounded-full',
                        systemHealth.status === 'healthy' && 'bg-green-500',
                        systemHealth.status === 'degraded' && 'bg-yellow-500',
                        systemHealth.status === 'unhealthy' && 'bg-red-500'
                      )}
                    />
                    <span className="font-medium text-gray-900 dark:text-white capitalize">{systemHealth.status}</span>
                    <Badge variant={systemHealth.status === 'healthy' ? 'success' : systemHealth.status === 'degraded' ? 'warning' : 'error'} size="sm">
                      {systemHealth.status}
                    </Badge>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between text-gray-600 dark:text-gray-400">
                      <span>Uptime</span>
                      <span className="font-medium text-gray-900 dark:text-white">{systemHealth.uptime}</span>
                    </div>
                    <div className="flex justify-between text-gray-600 dark:text-gray-400">
                      <span>Version</span>
                      <span className="font-medium text-gray-900 dark:text-white">{systemHealth.version}</span>
                    </div>
                    <div className="flex justify-between text-gray-600 dark:text-gray-400">
                      <span>ML Model</span>
                      <span className="font-medium text-gray-900 dark:text-white">{systemHealth.ml_model_status}</span>
                    </div>
                    <div className="flex justify-between text-gray-600 dark:text-gray-400">
                      <span>Database</span>
                      <span className="font-medium text-gray-900 dark:text-white">{systemHealth.database_status}</span>
                    </div>
                  </div>
                </>
              ) : (
                <p className="text-gray-500 dark:text-gray-400 text-sm">Unable to load system status</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Recent Verifications */}
        <div className="lg:col-span-2 space-y-6">
          <Card variant="outlined" padding="none">
            <CardHeader className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <CardTitle className="flex items-center gap-2">
                  <Clock className="w-5 h-5" />
                  Recent Verifications
                </CardTitle>
                <Link to="/history" className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 font-medium">
                  View All →
                </Link>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {isLoading ? (
                <div className="space-y-4 p-6">
                  {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="animate-pulse flex items-center gap-4">
                      <div className="h-10 w-10 rounded-lg bg-gray-200 dark:bg-gray-700" />
                      <div className="flex-1 space-y-2">
                        <div className="h-4 w-3/4 bg-gray-200 dark:bg-gray-700 rounded" />
                        <div className="h-3 w-1/2 bg-gray-200 dark:bg-gray-700 rounded" />
                      </div>
                      <div className="h-6 w-24 bg-gray-200 dark:bg-gray-700 rounded" />
                    </div>
                  ))}
                </div>
              ) : recentVerifications.length === 0 ? (
                <div className="p-12 text-center">
                  <Shield className="w-12 h-12 mx-auto text-gray-300 dark:text-gray-600 mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">No verifications yet</h3>
                  <p className="text-gray-500 dark:text-gray-400 mb-6">Start by verifying your first claim</p>
                  <Button variant="primary" leftIcon={<Plus className="w-4 h-4" />} onClick={() => window.location.href = '/verify?type=text'}>
                    Create Verification
                  </Button>
                </div>
              ) : (
                <div className="divide-y divide-gray-200 dark:divide-gray-700">
                  {recentVerifications.map((verification) => (
                    <Link
                      key={verification.id}
                      to={`/history/${verification.id}`}
                      className="flex items-center gap-4 p-4 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
                    >
                      <div
                        className={cn(
                          'w-10 h-10 rounded-lg flex items-center justify-center',
                          getVerdictColor(verification.verdict).bg
                        )}
                      >
                        <VerdictBadge verdict={verification.verdict} size="sm" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-900 dark:text-white truncate">{verification.claim_text}</p>
                        <div className="flex items-center gap-3 mt-1 text-sm text-gray-500 dark:text-gray-400">
                          <span>{formatRelativeTime(verification.created_at)}</span>
                          <span className="text-gray-300 dark:text-gray-600">•</span>
                          <Badge variant="outline" size="sm">{verification.language}</Badge>
                          <Badge variant="outline" size="sm">{verification.input_type}</Badge>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="font-medium text-gray-900 dark:text-white">{Math.round(verification.confidence * 100)}%</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">Confidence</p>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}