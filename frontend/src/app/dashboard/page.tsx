'use client';

import { useQuery } from '@tanstack/react-query';
import { gameApi } from '@/lib/api-services';
import { ArrowUpIcon, ArrowDownIcon } from '@heroicons/react/20/solid';

function formatCurrency(amount: number) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function DashboardPage() {
  const { data: dashboard, isLoading, error } = useQuery({
    queryKey: ['dashboard'],
    queryFn: gameApi.getDashboard,
    refetchInterval: 60000, // Refresh every minute
  });

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-8"></div>
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="bg-white overflow-hidden shadow rounded-lg">
                <div className="p-5">
                  <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
                  <div className="h-8 bg-gray-200 rounded w-1/2"></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error || !dashboard) {
    return (
      <div className="p-8">
        <div className="rounded-md bg-red-50 p-4">
          <p className="text-sm text-red-800">
            Failed to load dashboard data. Please try refreshing the page.
          </p>
        </div>
      </div>
    );
  }

  const stats = [
    {
      name: 'Current Capital',
      value: formatCurrency(dashboard.financial_summary.current_capital),
      change: null,
    },
    {
      name: 'Total Premiums',
      value: formatCurrency(dashboard.financial_summary.total_premiums),
      change: null,
    },
    {
      name: 'Combined Ratio',
      value: `${dashboard.financial_summary.combined_ratio.toFixed(1)}%`,
      change: dashboard.financial_summary.combined_ratio > 100 ? 'increase' : 'decrease',
    },
    {
      name: 'Compliance Score',
      value: `${dashboard.compliance_score.toFixed(0)}%`,
      change: dashboard.compliance_score >= 80 ? 'increase' : 'decrease',
    },
  ];

  // Calculate time until deadline
  const deadline = new Date(dashboard.current_turn.deadline);
  const now = new Date();
  const hoursUntilDeadline = Math.floor((deadline.getTime() - now.getTime()) / (1000 * 60 * 60));
  const daysUntilDeadline = Math.floor(hoursUntilDeadline / 24);

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-900">{dashboard.company.name}</h1>
        <p className="mt-1 text-sm text-gray-600">
          Turn {dashboard.current_turn.turn_number} • {dashboard.current_turn.status}
        </p>
      </div>

      {/* Turn Status Alert */}
      {dashboard.current_turn.status === 'active' && (
        <div className="mb-6 rounded-md bg-blue-50 p-4">
          <div className="flex">
            <div className="ml-3">
              <h3 className="text-sm font-medium text-blue-800">
                Decision deadline: {formatDate(dashboard.current_turn.deadline)}
              </h3>
              <div className="mt-2 text-sm text-blue-700">
                <p>
                  {daysUntilDeadline > 0 
                    ? `${daysUntilDeadline} days and ${hoursUntilDeadline % 24} hours remaining`
                    : `${hoursUntilDeadline} hours remaining`
                  }
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <div key={stat.name} className="bg-white overflow-hidden shadow rounded-lg">
            <div className="p-5">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  {stat.change === 'increase' && (
                    <ArrowUpIcon className="h-5 w-5 text-green-500" aria-hidden="true" />
                  )}
                  {stat.change === 'decrease' && (
                    <ArrowDownIcon className="h-5 w-5 text-red-500" aria-hidden="true" />
                  )}
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">{stat.name}</dt>
                    <dd className="text-lg font-semibold text-gray-900">{stat.value}</dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Recent Events */}
      {dashboard.recent_events.length > 0 && (
        <div className="mt-8">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Recent Events</h2>
          <div className="bg-white shadow overflow-hidden sm:rounded-md">
            <ul className="divide-y divide-gray-200">
              {dashboard.recent_events.map((event) => (
                <li key={event.id} className="px-6 py-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        Turn {event.turn_number}: {event.description}
                      </p>
                      <p className="text-sm text-gray-500">
                        {event.category} • {event.severity}
                      </p>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
} 