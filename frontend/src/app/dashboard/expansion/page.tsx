'use client';

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryClient } from '@/lib/query-client';
import { CheckCircleIcon, ClockIcon } from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';

interface State {
  id: string;
  code: string;
  name: string;
  regulatory_category: string;
}

interface ExpansionOpportunity {
  state: State;
  is_authorized: boolean;
  is_pending: boolean;
  estimated_cost: number;
  estimated_weeks: number;
  cost_breakdown: {
    base_cost: number;
    distance_cost: number;
    market_size_multiplier: number;
    regulatory_multiplier: number;
  };
  distance_miles: number;
  is_home_state: boolean;
  is_adjacent: boolean;
}

export default function ExpansionPage() {
  const [selectedState, setSelectedState] = useState<ExpansionOpportunity | null>(null);

  const { data: opportunities, isLoading } = useQuery({
    queryKey: ['expansion-opportunities'],
    queryFn: () => apiClient.get<ExpansionOpportunity[]>('/expansion/opportunities'),
  });

  const expansionMutation = useMutation({
    mutationFn: (stateId: string) => 
      apiClient.post(`/expansion/request/${stateId}`),
    onSuccess: (_, stateId) => {
      queryClient.invalidateQueries({ queryKey: ['expansion-opportunities'] });
      const stateName = selectedState?.state.name || 'the state';
      toast.success(`Expansion request for ${stateName} submitted! Approval expected in ${selectedState?.estimated_weeks || 4} weeks.`);
      setSelectedState(null);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to submit expansion request');
    },
  });

  const formatCurrency = (amount: number) => 
    new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'strict': return 'text-red-600 bg-red-50';
      case 'moderate': return 'text-yellow-600 bg-yellow-50';
      case 'light': return 'text-green-600 bg-green-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-8"></div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="bg-white p-6 rounded-lg shadow">
                <div className="h-6 bg-gray-200 rounded w-3/4 mb-2"></div>
                <div className="h-4 bg-gray-200 rounded w-1/2"></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const authorizedStates = opportunities?.filter(o => o.is_authorized) || [];
  const pendingStates = opportunities?.filter(o => o.is_pending) || [];
  const availableStates = opportunities?.filter(o => !o.is_authorized && !o.is_pending) || [];

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-900">Geographic Expansion</h1>
        <p className="mt-1 text-sm text-gray-600">
          Expand your insurance operations to new states
        </p>
      </div>

      {/* Authorized States */}
      {authorizedStates.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Authorized States</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {authorizedStates.map((opp) => (
              <div key={opp.state.id} className="bg-white p-6 rounded-lg shadow">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-medium text-gray-900">
                      {opp.state.name} ({opp.state.code})
                    </h3>
                    {opp.is_home_state && (
                      <p className="text-sm text-indigo-600">Home State</p>
                    )}
                  </div>
                  <CheckCircleIcon className="h-6 w-6 text-green-500" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Pending Approvals */}
      {pendingStates.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Pending Approvals</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {pendingStates.map((opp) => (
              <div key={opp.state.id} className="bg-white p-6 rounded-lg shadow">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-medium text-gray-900">
                      {opp.state.name} ({opp.state.code})
                    </h3>
                    <p className="text-sm text-gray-600">
                      ~{opp.estimated_weeks} weeks remaining
                    </p>
                  </div>
                  <ClockIcon className="h-6 w-6 text-yellow-500" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Available States */}
      <div className="mb-8">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Available for Expansion</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {availableStates.map((opp) => (
            <div 
              key={opp.state.id} 
              className="bg-white p-6 rounded-lg shadow cursor-pointer hover:shadow-lg transition-shadow"
              onClick={() => setSelectedState(opp)}
            >
              <h3 className="text-lg font-medium text-gray-900">
                {opp.state.name} ({opp.state.code})
              </h3>
              <div className="mt-2">
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getCategoryColor(opp.state.regulatory_category)}`}>
                  {opp.state.regulatory_category} regulation
                </span>
              </div>
              <div className="mt-4 space-y-1">
                <p className="text-sm text-gray-600">
                  Cost: {formatCurrency(opp.estimated_cost)}
                </p>
                <p className="text-sm text-gray-600">
                  Approval: ~{opp.estimated_weeks} weeks
                </p>
                {opp.is_adjacent && (
                  <p className="text-sm text-green-600">Adjacent state discount</p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Expansion Details Modal */}
      {selectedState && (
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              Expand to {selectedState.state.name}
            </h3>
            
            <div className="space-y-3 mb-6">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Base Cost:</span>
                <span className="text-sm font-medium">
                  {formatCurrency(selectedState.cost_breakdown.base_cost)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Distance ({Math.round(selectedState.distance_miles)} miles):</span>
                <span className="text-sm font-medium">
                  {formatCurrency(selectedState.cost_breakdown.distance_cost)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Market Size Adjustment:</span>
                <span className="text-sm font-medium">
                  {selectedState.cost_breakdown.market_size_multiplier.toFixed(1)}x
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Regulatory Adjustment:</span>
                <span className="text-sm font-medium">
                  {selectedState.cost_breakdown.regulatory_multiplier.toFixed(1)}x
                </span>
              </div>
              <div className="border-t pt-3 flex justify-between">
                <span className="text-sm font-medium text-gray-900">Total Cost:</span>
                <span className="text-lg font-semibold text-gray-900">
                  {formatCurrency(selectedState.estimated_cost)}
                </span>
              </div>
            </div>

            <div className="bg-blue-50 rounded-md p-4 mb-6">
              <p className="text-sm text-blue-800">
                Approval will take approximately {selectedState.estimated_weeks} weeks.
                You will be charged immediately upon submission.
              </p>
            </div>

            <div className="flex space-x-3">
              <button
                onClick={() => {
                  expansionMutation.mutate(selectedState.state.id);
                }}
                disabled={expansionMutation.isPending}
                className="flex-1 px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {expansionMutation.isPending ? 'Submitting...' : 'Request Expansion'}
              </button>
              <button
                onClick={() => setSelectedState(null)}
                className="flex-1 px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
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