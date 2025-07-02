'use client';

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryClient } from '@/lib/query-client';
import { ChartBarIcon, ExclamationTriangleIcon, InformationCircleIcon } from '@heroicons/react/24/outline';

interface PortfolioCharacteristics {
  risk: number;
  duration: number;
  liquidity: number;
  credit: number;
  diversification: number;
}

interface PortfolioResponse {
  total_value: number;
  actual_characteristics: PortfolioCharacteristics;
  perceived_characteristics?: PortfolioCharacteristics;
  actual_returns: number;
  perceived_returns: number;
  information_quality: number;
  cfo_skill?: number;
  asset_allocation?: Record<string, number>;
}

interface InvestmentDecisionResponse {
  success: boolean;
  message: string;
  expected_return?: number;
  portfolio_risk?: number;
  sharpe_ratio?: number;
  optimization_notes?: string;
}

interface CFOInsightResponse {
  skill_category: string;
  confidence_level: string;
  analysis_depth: string;
  insights: string[];
  risks_identified: string[];
  recommendations?: string[];
  performance_assessment?: string;
}

interface InvestmentConstraints {
  min_investment_amount: number;
  max_investment_percentage: number;
  regulatory_constraints: {
    max_risk?: number;
    min_liquidity?: number;
    max_credit_risk?: number;
  };
  solvency_adjustments?: {
    min_liquidity?: number;
    max_risk?: number;
    reason: string;
  };
  size_adjustments?: {
    max_duration?: number;
    min_diversification?: number;
    reason: string;
  };
}

export default function InvestmentsPage() {
  const [targetCharacteristics, setTargetCharacteristics] = useState<PortfolioCharacteristics>({
    risk: 50,
    duration: 50,
    liquidity: 50,
    credit: 50,
    diversification: 50,
  });
  const [showConfirmModal, setShowConfirmModal] = useState(false);

  const { data: portfolio, isLoading: portfolioLoading } = useQuery({
    queryKey: ['portfolio'],
    queryFn: () => apiClient.get<PortfolioResponse>('/investments/portfolio'),
  });

  const { data: insights, isLoading: insightsLoading } = useQuery({
    queryKey: ['cfo-insights'],
    queryFn: () => apiClient.get<CFOInsightResponse>('/investments/insights'),
  });

  const { data: constraints } = useQuery({
    queryKey: ['investment-constraints'],
    queryFn: () => apiClient.get<InvestmentConstraints>('/investments/constraints'),
  });

  const updatePreferencesMutation = useMutation({
    mutationFn: (preferences: PortfolioCharacteristics) =>
      apiClient.post<InvestmentDecisionResponse>('/investments/preferences', preferences),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      queryClient.invalidateQueries({ queryKey: ['cfo-insights'] });
      setShowConfirmModal(false);
    },
  });

  const formatCurrency = (amount: number) =>
    new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);

  const formatPercent = (value: number) =>
    new Intl.NumberFormat('en-US', {
      style: 'percent',
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    }).format(value / 100);

  const getSkillCategoryColor = (category: string) => {
    switch (category) {
      case 'expert':
        return 'text-purple-600';
      case 'skilled':
        return 'text-blue-600';
      case 'intermediate':
        return 'text-green-600';
      case 'novice':
        return 'text-yellow-600';
      default:
        return 'text-gray-600';
    }
  };

  const getCharacteristicLabel = (key: string) => {
    const labels: Record<string, { name: string; low: string; high: string }> = {
      risk: { name: 'Risk', low: 'Conservative', high: 'Aggressive' },
      duration: { name: 'Duration', low: 'Short-term', high: 'Long-term' },
      liquidity: { name: 'Liquidity', low: 'Illiquid OK', high: 'Highly liquid' },
      credit: { name: 'Credit Quality', low: 'AAA only', high: 'High yield OK' },
      diversification: { name: 'Diversification', low: 'Concentrated', high: 'Highly diversified' },
    };
    return labels[key] || { name: key, low: 'Low', high: 'High' };
  };

  const isConstraintViolated = (characteristic: keyof PortfolioCharacteristics, value: number): boolean => {
    if (!constraints) return false;

    // Check regulatory constraints
    if (characteristic === 'risk' && constraints.regulatory_constraints.max_risk && value > constraints.regulatory_constraints.max_risk) return true;
    if (characteristic === 'liquidity' && constraints.regulatory_constraints.min_liquidity && value < constraints.regulatory_constraints.min_liquidity) return true;
    if (characteristic === 'credit' && constraints.regulatory_constraints.max_credit_risk && value > constraints.regulatory_constraints.max_credit_risk) return true;

    // Check solvency adjustments
    if (constraints.solvency_adjustments) {
      if (characteristic === 'risk' && constraints.solvency_adjustments.max_risk && value > constraints.solvency_adjustments.max_risk) return true;
      if (characteristic === 'liquidity' && constraints.solvency_adjustments.min_liquidity && value < constraints.solvency_adjustments.min_liquidity) return true;
    }

    // Check size adjustments
    if (constraints.size_adjustments) {
      if (characteristic === 'duration' && constraints.size_adjustments.max_duration && value > constraints.size_adjustments.max_duration) return true;
      if (characteristic === 'diversification' && constraints.size_adjustments.min_diversification && value < constraints.size_adjustments.min_diversification) return true;
    }

    return false;
  };

  if (portfolioLoading || insightsLoading) {
    return (
      <div className="p-8">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-8"></div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white p-6 rounded-lg shadow">
              <div className="h-6 bg-gray-200 rounded w-3/4 mb-4"></div>
              <div className="space-y-4">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="h-12 bg-gray-200 rounded"></div>
                ))}
              </div>
            </div>
            <div className="bg-white p-6 rounded-lg shadow">
              <div className="h-6 bg-gray-200 rounded w-3/4 mb-4"></div>
              <div className="space-y-2">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="h-4 bg-gray-200 rounded"></div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Initialize target characteristics from current portfolio if available
  if (portfolio && targetCharacteristics.risk === 50) {
    const current = portfolio.perceived_characteristics || portfolio.actual_characteristics;
    setTargetCharacteristics(current);
  }

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-900">Investment Portfolio Management</h1>
        <p className="mt-1 text-sm text-gray-600">
          Manage your investment portfolio characteristics. {portfolio?.cfo_skill ? `CFO Skill Level: ${portfolio.cfo_skill}` : 'No CFO hired'}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Portfolio Characteristics */}
        <div className="bg-white p-6 rounded-lg shadow">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-medium text-gray-900">Portfolio Characteristics</h2>
            <ChartBarIcon className="h-6 w-6 text-gray-400" />
          </div>

          <div className="space-y-6">
            {Object.entries(targetCharacteristics).map(([key, value]) => {
              const label = getCharacteristicLabel(key);
              const isViolated = isConstraintViolated(key as keyof PortfolioCharacteristics, value);
              const actualValue = portfolio?.actual_characteristics?.[key as keyof PortfolioCharacteristics];
              const perceivedValue = portfolio?.perceived_characteristics?.[key as keyof PortfolioCharacteristics];

              return (
                <div key={key}>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-gray-700">{label.name}</span>
                    <span className={`text-sm font-medium ${isViolated ? 'text-red-600' : 'text-gray-900'}`}>
                      {Math.round(value)}
                    </span>
                  </div>
                  
                  <div className="relative">
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={value}
                      onChange={(e) => setTargetCharacteristics(prev => ({
                        ...prev,
                        [key]: parseInt(e.target.value)
                      }))}
                      className={`w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer ${
                        isViolated ? 'accent-red-600' : 'accent-indigo-600'
                      }`}
                    />
                    <div className="flex justify-between text-xs text-gray-500 mt-1">
                      <span>{label.low}</span>
                      <span>{label.high}</span>
                    </div>
                  </div>

                  {portfolio && perceivedValue !== undefined && actualValue !== undefined && perceivedValue !== actualValue && (
                    <div className="mt-2 text-xs space-y-1">
                      <div className="flex justify-between">
                        <span className="text-gray-500">Perceived:</span>
                        <span className="text-gray-700">{Math.round(perceivedValue)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Actual:</span>
                        <span className="text-gray-700">{Math.round(actualValue)}</span>
                      </div>
                    </div>
                  )}

                  {isViolated && (
                    <p className="text-xs text-red-600 mt-1">
                      Exceeds constraint limits
                    </p>
                  )}
                </div>
              );
            })}
          </div>

          <button
            onClick={() => setShowConfirmModal(true)}
            className="mt-6 w-full px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
          >
            Apply Changes
          </button>
        </div>

        {/* Portfolio Summary & Insights */}
        <div className="space-y-6">
          {/* Portfolio Summary */}
          {portfolio && (
            <div className="bg-white p-6 rounded-lg shadow">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Current Portfolio</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">Total Value:</span>
                  <span className="text-sm font-medium">{formatCurrency(portfolio.total_value)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">Perceived Returns:</span>
                  <span className="text-sm font-medium">{formatPercent(portfolio.perceived_returns)}</span>
                </div>
                {portfolio.cfo_skill && portfolio.cfo_skill >= 70 && (
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Actual Returns:</span>
                    <span className="text-sm font-medium">{formatPercent(portfolio.actual_returns)}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">Information Quality:</span>
                  <span className="text-sm font-medium">{formatPercent(portfolio.information_quality * 100)}</span>
                </div>
              </div>
            </div>
          )}

          {/* CFO Insights */}
          {insights && (
            <div className="bg-white p-6 rounded-lg shadow">
              <div className="flex items-start justify-between mb-4">
                <h3 className="text-lg font-medium text-gray-900">CFO Analysis</h3>
                <span className={`text-sm font-medium ${getSkillCategoryColor(insights.skill_category)}`}>
                  {insights.skill_category} CFO
                </span>
              </div>

              <div className="space-y-4">
                {insights.insights.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Insights</h4>
                    <ul className="text-sm text-gray-600 space-y-1">
                      {insights.insights.map((insight, i) => (
                        <li key={i} className="flex items-start">
                          <InformationCircleIcon className="h-4 w-4 text-blue-500 mr-2 mt-0.5 flex-shrink-0" />
                          {insight}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {insights.risks_identified.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Risks Identified</h4>
                    <ul className="text-sm text-gray-600 space-y-1">
                      {insights.risks_identified.map((risk, i) => (
                        <li key={i} className="flex items-start">
                          <ExclamationTriangleIcon className="h-4 w-4 text-yellow-500 mr-2 mt-0.5 flex-shrink-0" />
                          {risk}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {insights.recommendations && insights.recommendations.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Recommendations</h4>
                    <ul className="text-sm text-gray-600 space-y-1">
                      {insights.recommendations.map((rec, i) => (
                        <li key={i}>• {rec}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Constraints */}
          {constraints && (constraints.solvency_adjustments || constraints.size_adjustments) && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
              <div className="flex items-start">
                <ExclamationTriangleIcon className="h-5 w-5 text-amber-600 mt-0.5 mr-3 flex-shrink-0" />
                <div>
                  <h4 className="text-sm font-medium text-amber-900">Investment Constraints</h4>
                  {constraints.solvency_adjustments && (
                    <p className="text-sm text-amber-800 mt-1">{constraints.solvency_adjustments.reason}</p>
                  )}
                  {constraints.size_adjustments && (
                    <p className="text-sm text-amber-800 mt-1">{constraints.size_adjustments.reason}</p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Confirmation Modal */}
      {showConfirmModal && (
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              Confirm Portfolio Changes
            </h3>

            <div className="space-y-3 mb-6">
              {Object.entries(targetCharacteristics).map(([key, value]) => {
                const label = getCharacteristicLabel(key);
                const currentValue = portfolio?.perceived_characteristics?.[key as keyof PortfolioCharacteristics] || 
                                   portfolio?.actual_characteristics?.[key as keyof PortfolioCharacteristics] || 50;
                const hasChanged = Math.round(currentValue) !== Math.round(value);

                if (!hasChanged) return null;

                return (
                  <div key={key} className="flex justify-between text-sm">
                    <span className="text-gray-600">{label.name}:</span>
                    <span className="font-medium">
                      {Math.round(currentValue)} → {Math.round(value)}
                    </span>
                  </div>
                );
              })}
            </div>

            {updatePreferencesMutation.data && updatePreferencesMutation.data.optimization_notes && (
              <div className="bg-blue-50 rounded-md p-3 mb-4">
                <p className="text-sm text-blue-800">{updatePreferencesMutation.data.optimization_notes}</p>
              </div>
            )}

            <div className="flex space-x-3">
              <button
                onClick={() => updatePreferencesMutation.mutate(targetCharacteristics)}
                disabled={updatePreferencesMutation.isPending}
                className="flex-1 px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {updatePreferencesMutation.isPending ? 'Applying...' : 'Confirm Changes'}
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