'use client';

import { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryClient, queryKeys, queryCacheConfigs } from '@/lib/query-client';
import { 
  DocumentCheckIcon, 
  ExclamationTriangleIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  BuildingOfficeIcon,
  MapIcon,
  CubeIcon,
  ChartBarIcon,
  UserGroupIcon,
  CurrencyDollarIcon
} from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';

interface TurnStatus {
  turn_number: number;
  week_number: number;
  status: string;
  start_date: string;
  end_date: string;
  decisions_submitted: boolean;
  time_remaining_hours: number;
}

interface CurrentDecisions {
  turn_number: number;
  submitted: boolean;
  submitted_at?: string;
  decisions?: {
    expansion: string[];
    products: {
      new: Array<{
        state_id: string;
        line_of_business_id: string;
        tier: string;
        base_premium: number;
      }>;
      tier_switches: Record<string, string>;
    };
    pricing: Record<string, number>;
    investments: Record<string, number> | null;
    employees: {
      hire: Array<{ position: string; candidate_id: string }>;
      fire: string[];
    };
  };
  validation_status: string;
}

interface ExpansionOpportunity {
  state: { id: string; code: string; name: string };
  estimated_cost: number;
  estimated_weeks: number;
}

interface Product {
  id: string;
  state_code: string;
  line_of_business_code: string;
  tier: string;
  base_premium: number;
}

interface Employee {
  id: string;
  name: string;
  position: string;
  skill_level: number;
  annual_salary: number;
}

export default function DecisionsPage() {
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState<string>('');

  const { data: turnStatus, isLoading: isLoadingTurn } = useQuery({
    queryKey: queryKeys.currentTurn(),
    queryFn: () => apiClient.get<TurnStatus>('/game/current-turn'),
    ...queryCacheConfigs.realTime, // Real-time data - cache for only 30 seconds
  });

  const { data: currentDecisions, isLoading: isLoadingDecisions } = useQuery({
    queryKey: queryKeys.turnDecisions(),
    queryFn: () => apiClient.get<CurrentDecisions>('/game/decisions/current'),
    ...queryCacheConfigs.realTime, // Real-time data - cache for only 30 seconds
  });

  const { data: expansionOpportunities } = useQuery({
    queryKey: ['expansion-opportunities'],
    queryFn: () => apiClient.get<ExpansionOpportunity[]>('/expansion/opportunities'),
    enabled: !!(currentDecisions?.decisions?.expansion?.length),
  });

  const { data: products } = useQuery({
    queryKey: ['products'],
    queryFn: () => apiClient.get<Product[]>('/products'),
    enabled: !!(currentDecisions?.decisions?.products?.tier_switches && Object.keys(currentDecisions.decisions.products.tier_switches).length > 0),
  });

  const { data: employees } = useQuery({
    queryKey: ['employees'],
    queryFn: () => apiClient.get<Employee[]>('/employees'),
    enabled: !!(currentDecisions?.decisions?.employees?.fire?.length),
  });

  const submitDecisionsMutation = useMutation({
    mutationFn: () => apiClient.post('/game/decisions', {
      expansion_requests: currentDecisions?.decisions?.expansion || [],
      new_products: currentDecisions?.decisions?.products?.new || [],
      tier_switches: currentDecisions?.decisions?.products?.tier_switches || {},
      pricing: currentDecisions?.decisions?.pricing || {},
      portfolio_preferences: currentDecisions?.decisions?.investments || null,
      hire_employees: currentDecisions?.decisions?.employees?.hire || [],
      fire_employees: currentDecisions?.decisions?.employees?.fire || [],
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.turnDecisions() });
      queryClient.invalidateQueries({ queryKey: queryKeys.currentTurn() });
      setShowConfirmModal(false);
      toast.success('Turn decisions submitted successfully! They will be processed on Monday at midnight.');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to submit turn decisions');
    },
  });

  // Update countdown timer
  useEffect(() => {
    if (!turnStatus) return;

    const updateTimer = () => {
      const now = new Date();
      const deadline = new Date(turnStatus.end_date);
      const diff = deadline.getTime() - now.getTime();

      if (diff <= 0) {
        setTimeRemaining('Deadline passed');
        return;
      }

      const days = Math.floor(diff / (1000 * 60 * 60 * 24));
      const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

      if (days > 0) {
        setTimeRemaining(`${days}d ${hours}h ${minutes}m`);
      } else if (hours > 0) {
        setTimeRemaining(`${hours}h ${minutes}m`);
      } else {
        setTimeRemaining(`${minutes}m`);
      }
    };

    updateTimer();
    const interval = setInterval(updateTimer, 60000); // Update every minute

    return () => clearInterval(interval);
  }, [turnStatus]);

  const formatCurrency = (amount: number) => 
    new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);

  if (isLoadingTurn || isLoadingDecisions) {
    return (
      <div className="p-8">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-8"></div>
          <div className="space-y-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="bg-white p-6 rounded-lg shadow">
                <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
                <div className="h-4 bg-gray-200 rounded w-2/3"></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const hasAnyDecisions = currentDecisions?.decisions && (
    currentDecisions.decisions.expansion.length > 0 ||
    currentDecisions.decisions.products.new.length > 0 ||
    Object.keys(currentDecisions.decisions.products.tier_switches).length > 0 ||
    Object.keys(currentDecisions.decisions.pricing).length > 0 ||
    currentDecisions.decisions.investments !== null ||
    currentDecisions.decisions.employees.hire.length > 0 ||
    currentDecisions.decisions.employees.fire.length > 0
  );

  const isDeadlinePassed = turnStatus && new Date(turnStatus.end_date) < new Date();

  return (
    <div className="p-8">
      {/* Header with Timer */}
      <div className="mb-8 bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">Turn {turnStatus?.turn_number} Decisions</h1>
            <p className="mt-1 text-sm text-gray-600">
              Review and submit your decisions for this turn
            </p>
          </div>
          <div className="text-right">
            <div className={`flex items-center ${isDeadlinePassed ? 'text-red-600' : timeRemaining.includes('h') && !timeRemaining.includes('d') ? 'text-yellow-600' : 'text-gray-600'}`}>
              <ClockIcon className="h-5 w-5 mr-2" />
              <div>
                <p className="text-sm font-medium">Time Remaining</p>
                <p className="text-lg font-semibold">{timeRemaining}</p>
              </div>
            </div>
            {currentDecisions?.submitted && (
              <div className="mt-2 flex items-center text-green-600">
                <CheckCircleIcon className="h-4 w-4 mr-1" />
                <span className="text-sm">Submitted</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Warning if no decisions */}
      {!hasAnyDecisions && (
        <div className="mb-8 bg-yellow-50 border-l-4 border-yellow-400 p-4">
          <div className="flex">
            <ExclamationTriangleIcon className="h-5 w-5 text-yellow-400 mr-3 flex-shrink-0" />
            <div>
              <p className="text-sm text-yellow-700">
                You haven't made any decisions for this turn. If you don't submit decisions by the deadline, 
                the system will apply "no change" defaults.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Decision Sections */}
      <div className="space-y-6">
        {/* Expansion Decisions */}
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-center">
              <MapIcon className="h-6 w-6 text-gray-400 mr-3" />
              <h2 className="text-lg font-medium text-gray-900">Geographic Expansion</h2>
            </div>
          </div>
          <div className="p-6">
            {currentDecisions?.decisions?.expansion && currentDecisions.decisions.expansion.length > 0 ? (
              <div className="space-y-2">
                {currentDecisions.decisions.expansion.map((stateCode) => {
                  const opportunity = expansionOpportunities?.find(o => o.state.code === stateCode);
                  return (
                    <div key={stateCode} className="flex items-center justify-between py-2">
                      <span className="text-sm font-medium">{opportunity?.state.name || stateCode}</span>
                      <span className="text-sm text-gray-600">
                        {opportunity ? formatCurrency(opportunity.estimated_cost) : 'Loading...'}
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm text-gray-500">No expansion requests</p>
            )}
          </div>
        </div>

        {/* Product Decisions */}
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-center">
              <CubeIcon className="h-6 w-6 text-gray-400 mr-3" />
              <h2 className="text-lg font-medium text-gray-900">Product Changes</h2>
            </div>
          </div>
          <div className="p-6">
            <div className="space-y-4">
              {/* New Products */}
              {currentDecisions?.decisions?.products?.new && currentDecisions.decisions.products.new.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-2">New Products</h3>
                  <div className="space-y-1">
                    {currentDecisions.decisions.products.new.map((product, idx) => (
                      <div key={idx} className="text-sm text-gray-600">
                        {product.tier} tier product • {formatCurrency(product.base_premium)} premium
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Tier Switches */}
              {currentDecisions?.decisions?.products?.tier_switches && Object.keys(currentDecisions.decisions.products.tier_switches).length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Tier Switches</h3>
                  <div className="space-y-1">
                    {Object.entries(currentDecisions.decisions.products.tier_switches).map(([productId, newTier]) => {
                      const product = products?.find(p => p.id === productId);
                      return (
                        <div key={productId} className="text-sm text-gray-600">
                          {product ? `${product.state_code} - ${product.line_of_business_code}` : productId}: 
                          {' '}{product?.tier || '?'} → {newTier}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
              
              {(!currentDecisions?.decisions?.products?.new?.length && 
                !Object.keys(currentDecisions?.decisions?.products?.tier_switches || {}).length) && (
                <p className="text-sm text-gray-500">No product changes</p>
              )}
            </div>
          </div>
        </div>

        {/* Investment Decisions */}
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-center">
              <ChartBarIcon className="h-6 w-6 text-gray-400 mr-3" />
              <h2 className="text-lg font-medium text-gray-900">Investment Portfolio</h2>
            </div>
          </div>
          <div className="p-6">
            {currentDecisions?.decisions?.investments ? (
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                {Object.entries(currentDecisions.decisions.investments).map(([key, value]) => (
                  <div key={key}>
                    <p className="text-xs text-gray-500 capitalize">{key.replace('_', ' ')}</p>
                    <p className="text-sm font-medium">{(value * 100).toFixed(0)}%</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">No investment changes</p>
            )}
          </div>
        </div>

        {/* Employee Decisions */}
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-center">
              <UserGroupIcon className="h-6 w-6 text-gray-400 mr-3" />
              <h2 className="text-lg font-medium text-gray-900">Employee Changes</h2>
            </div>
          </div>
          <div className="p-6">
            <div className="space-y-4">
              {/* Hiring */}
              {currentDecisions?.decisions?.employees?.hire && currentDecisions.decisions.employees.hire.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-2">New Hires</h3>
                  <div className="space-y-1">
                    {currentDecisions.decisions.employees.hire.map((hire, idx) => (
                      <div key={idx} className="text-sm text-gray-600">
                        {hire.position}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Firing */}
              {currentDecisions?.decisions?.employees?.fire && currentDecisions.decisions.employees.fire.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Terminations</h3>
                  <div className="space-y-1">
                    {currentDecisions.decisions.employees.fire.map((employeeId) => {
                      const employee = employees?.find(e => e.id === employeeId);
                      return (
                        <div key={employeeId} className="text-sm text-gray-600">
                          {employee ? `${employee.name} (${employee.position})` : employeeId}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
              
              {(!currentDecisions?.decisions?.employees?.hire?.length && 
                !currentDecisions?.decisions?.employees?.fire?.length) && (
                <p className="text-sm text-gray-500">No employee changes</p>
              )}
            </div>
          </div>
        </div>

        {/* Pricing Decisions */}
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-center">
              <CurrencyDollarIcon className="h-6 w-6 text-gray-400 mr-3" />
              <h2 className="text-lg font-medium text-gray-900">Pricing Adjustments</h2>
            </div>
          </div>
          <div className="p-6">
            {currentDecisions?.decisions?.pricing && Object.keys(currentDecisions.decisions.pricing).length > 0 ? (
              <div className="space-y-1">
                {Object.entries(currentDecisions.decisions.pricing).map(([productId, multiplier]) => {
                  const product = products?.find(p => p.id === productId);
                  return (
                    <div key={productId} className="flex items-center justify-between py-1">
                      <span className="text-sm text-gray-600">
                        {product ? `${product.state_code} - ${product.line_of_business_code}` : productId}
                      </span>
                      <span className="text-sm font-medium">
                        {multiplier > 1 ? '+' : ''}{((multiplier - 1) * 100).toFixed(0)}%
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm text-gray-500">No pricing changes</p>
            )}
          </div>
        </div>
      </div>

      {/* Submit Button */}
      <div className="mt-8 flex justify-end">
        <button
          onClick={() => setShowConfirmModal(true)}
          disabled={isDeadlinePassed || currentDecisions?.submitted}
          className="inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <DocumentCheckIcon className="h-5 w-5 mr-2" />
          {currentDecisions?.submitted ? 'Already Submitted' : isDeadlinePassed ? 'Deadline Passed' : 'Submit Decisions'}
        </button>
      </div>

      {/* Confirmation Modal */}
      {showConfirmModal && (
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              Confirm Turn Submission
            </h3>
            
            <div className="mb-6">
              <p className="text-sm text-gray-600 mb-4">
                Are you sure you want to submit these decisions for Turn {turnStatus?.turn_number}?
              </p>
              
              {!hasAnyDecisions && (
                <div className="bg-yellow-50 rounded-md p-4">
                  <p className="text-sm text-yellow-800">
                    <strong>Warning:</strong> You haven't made any decisions. Submitting now will apply "no change" defaults for this turn.
                  </p>
                </div>
              )}
              
              <div className="mt-4 text-sm text-gray-600">
                <p>You can resubmit decisions multiple times before the deadline. The latest submission will be used.</p>
              </div>
            </div>

            <div className="flex space-x-3">
              <button
                onClick={() => {
                  submitDecisionsMutation.mutate();
                }}
                disabled={submitDecisionsMutation.isPending}
                className="flex-1 px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitDecisionsMutation.isPending ? 'Submitting...' : 'Confirm Submission'}
              </button>
              <button
                onClick={() => setShowConfirmModal(false)}
                className="flex-1 px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
} 