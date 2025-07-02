'use client';

import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { BuildingOfficeIcon, UserCircleIcon, ChartBarIcon, ClockIcon } from '@heroicons/react/24/outline';
import { ArrowUpIcon, ArrowDownIcon, ArrowRightIcon } from '@heroicons/react/20/solid';
import Link from 'next/link';

interface CEO {
  id: string;
  name: string;
  leadership: number;
  risk_intelligence: number;
  market_acumen: number;
  regulatory_mastery: number;
  innovation_capacity: number;
  deal_making: number;
  financial_expertise: number;
  crisis_command: number;
  university_name: string;
  academic_background: string;
}

interface Employee {
  id: string;
  position: string;
  name: string;
  skill_level: number;
  salary: number;
  satisfaction: number;
  effectiveness: number;
}

interface CompanyDetails {
  id: string;
  name: string;
  founded_date: string;
  current_capital: number;
  solvency_ratio: number;
  home_state: {
    id: string;
    code: string;
    name: string;
  };
  ceo: CEO;
  employees: Employee[];
  authorized_states: Array<{
    state: {
      id: string;
      code: string;
      name: string;
    };
    authorization_date: string;
    is_home_state: boolean;
  }>;
  active_products: Array<{
    state_code: string;
    line_of_business_code: string;
    tier: string;
    active_policies: number;
  }>;
}

interface TurnResult {
  turn_number: number;
  week_number: number;
  processing_completed_at: string;
  financial_results: {
    starting_capital: number;
    ending_capital: number;
    total_premiums: number;
    total_claims: number;
    total_expenses: number;
    investment_income: number;
    loss_ratio: number;
    expense_ratio: number;
    combined_ratio: number;
  };
  market_results?: {
    total_policies: number;
    new_policies: number;
    market_share_changes: Record<string, number>;
  };
  special_events?: Array<{
    type: string;
    description: string;
    impact: number;
  }>;
}

interface CurrentTurn {
  turn_number: number;
  week_number: number;
  status: string;
  deadline: string;
  has_submitted_decisions: boolean;
}

function formatCurrency(amount: number) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatPercent(value: number) {
  return new Intl.NumberFormat('en-US', {
    style: 'percent',
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(value / 100);
}

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function getAttributeColor(value: number) {
  if (value >= 80) return 'text-green-600';
  if (value >= 60) return 'text-blue-600';
  if (value >= 40) return 'text-gray-600';
  return 'text-red-600';
}

export default function CompanyPage() {
  const { data: company, isLoading: companyLoading } = useQuery({
    queryKey: ['company-details'],
    queryFn: () => apiClient.get<CompanyDetails>('/game/company'),
  });

  const { data: currentTurn, isLoading: turnLoading } = useQuery({
    queryKey: ['current-turn'],
    queryFn: () => apiClient.get<CurrentTurn>('/game/current-turn'),
  });

  const { data: results, isLoading: resultsLoading } = useQuery({
    queryKey: ['turn-results'],
    queryFn: () => apiClient.get<TurnResult[]>('/game/history/results?limit=10'),
  });

  const isLoading = companyLoading || turnLoading || resultsLoading;

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-8"></div>
          
          {/* Company Info Skeleton */}
          <div className="bg-white shadow rounded-lg p-6 mb-6">
            <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
            <div className="space-y-3">
              <div className="h-4 bg-gray-200 rounded w-1/2"></div>
              <div className="h-4 bg-gray-200 rounded w-2/3"></div>
              <div className="h-4 bg-gray-200 rounded w-1/3"></div>
            </div>
          </div>

          {/* CEO Info Skeleton */}
          <div className="bg-white shadow rounded-lg p-6 mb-6">
            <div className="h-6 bg-gray-200 rounded w-1/4 mb-4"></div>
            <div className="grid grid-cols-2 gap-4">
              {[...Array(8)].map((_, i) => (
                <div key={i} className="h-4 bg-gray-200 rounded"></div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!company || !currentTurn) {
    return (
      <div className="p-8">
        <div className="rounded-md bg-red-50 p-4">
          <p className="text-sm text-red-800">
            Failed to load company data. Please try refreshing the page.
          </p>
        </div>
      </div>
    );
  }

  // Calculate time until deadline
  const deadline = new Date(currentTurn.deadline);
  const now = new Date();
  const hoursUntilDeadline = Math.floor((deadline.getTime() - now.getTime()) / (1000 * 60 * 60));
  const daysUntilDeadline = Math.floor(hoursUntilDeadline / 24);

  // Calculate capital change from results
  const latestResult = results?.[0];
  const capitalChange = latestResult 
    ? (latestResult.financial_results.ending_capital - latestResult.financial_results.starting_capital)
    : 0;
  const capitalChangePercent = latestResult && latestResult.financial_results.starting_capital > 0
    ? (capitalChange / latestResult.financial_results.starting_capital) * 100
    : 0;

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-900">Company Overview</h1>
        <p className="mt-1 text-sm text-gray-600">
          Comprehensive view of your insurance company's status and performance
        </p>
      </div>

      {/* Current Turn Status */}
      {currentTurn.status === 'active' && (
        <div className="mb-6 rounded-md bg-blue-50 p-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-blue-800">
                Turn {currentTurn.turn_number} • Week {currentTurn.week_number}
              </h3>
              <p className="mt-1 text-sm text-blue-700">
                {daysUntilDeadline > 0 
                  ? `${daysUntilDeadline} days and ${hoursUntilDeadline % 24} hours until deadline`
                  : `${hoursUntilDeadline} hours until deadline`
                }
              </p>
            </div>
            {!currentTurn.has_submitted_decisions && (
              <Link
                href="/dashboard/decisions"
                className="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
              >
                Submit Decisions
                <ArrowRightIcon className="ml-2 h-4 w-4" />
              </Link>
            )}
          </div>
        </div>
      )}

      {/* Company Information */}
      <div className="bg-white shadow rounded-lg mb-6">
        <div className="px-6 py-5 border-b border-gray-200">
          <div className="flex items-center">
            <BuildingOfficeIcon className="h-6 w-6 text-gray-400 mr-3" />
            <h2 className="text-lg font-medium text-gray-900">Company Information</h2>
          </div>
        </div>
        <div className="px-6 py-5">
          <dl className="grid grid-cols-1 gap-x-4 gap-y-6 sm:grid-cols-2">
            <div>
              <dt className="text-sm font-medium text-gray-500">Company Name</dt>
              <dd className="mt-1 text-sm text-gray-900">{company.name}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Home State</dt>
              <dd className="mt-1 text-sm text-gray-900">
                {company.home_state.name} ({company.home_state.code})
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Founded</dt>
              <dd className="mt-1 text-sm text-gray-900">{formatDate(company.founded_date)}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Current Capital</dt>
              <dd className="mt-1 text-sm text-gray-900 flex items-center">
                {formatCurrency(company.current_capital)}
                {capitalChange !== 0 && (
                  <span className={`ml-2 flex items-center text-xs ${capitalChange > 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {capitalChange > 0 ? <ArrowUpIcon className="h-3 w-3" /> : <ArrowDownIcon className="h-3 w-3" />}
                    {formatPercent(Math.abs(capitalChangePercent))}
                  </span>
                )}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Solvency Ratio</dt>
              <dd className="mt-1 text-sm text-gray-900">{formatPercent(company.solvency_ratio)}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Active States</dt>
              <dd className="mt-1 text-sm text-gray-900">{company.authorized_states.length}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Active Products</dt>
              <dd className="mt-1 text-sm text-gray-900">{company.active_products.length}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Total Active Policies</dt>
              <dd className="mt-1 text-sm text-gray-900">
                {company.active_products.reduce((sum, p) => sum + p.active_policies, 0).toLocaleString()}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      {/* CEO Information */}
      <div className="bg-white shadow rounded-lg mb-6">
        <div className="px-6 py-5 border-b border-gray-200">
          <div className="flex items-center">
            <UserCircleIcon className="h-6 w-6 text-gray-400 mr-3" />
            <h2 className="text-lg font-medium text-gray-900">CEO Profile</h2>
          </div>
        </div>
        <div className="px-6 py-5">
          <div className="mb-4">
            <h3 className="text-base font-medium text-gray-900">{company.ceo.name}</h3>
            <p className="text-sm text-gray-500">
              {company.ceo.academic_background} • {company.ceo.university_name}
            </p>
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Leadership</span>
                <span className={`text-sm font-medium ${getAttributeColor(company.ceo.leadership)}`}>
                  {company.ceo.leadership}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Risk Intelligence</span>
                <span className={`text-sm font-medium ${getAttributeColor(company.ceo.risk_intelligence)}`}>
                  {company.ceo.risk_intelligence}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Market Acumen</span>
                <span className={`text-sm font-medium ${getAttributeColor(company.ceo.market_acumen)}`}>
                  {company.ceo.market_acumen}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Regulatory Mastery</span>
                <span className={`text-sm font-medium ${getAttributeColor(company.ceo.regulatory_mastery)}`}>
                  {company.ceo.regulatory_mastery}
                </span>
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Innovation Capacity</span>
                <span className={`text-sm font-medium ${getAttributeColor(company.ceo.innovation_capacity)}`}>
                  {company.ceo.innovation_capacity}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Deal Making</span>
                <span className={`text-sm font-medium ${getAttributeColor(company.ceo.deal_making)}`}>
                  {company.ceo.deal_making}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Financial Expertise</span>
                <span className={`text-sm font-medium ${getAttributeColor(company.ceo.financial_expertise)}`}>
                  {company.ceo.financial_expertise}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Crisis Command</span>
                <span className={`text-sm font-medium ${getAttributeColor(company.ceo.crisis_command)}`}>
                  {company.ceo.crisis_command}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Historical Results */}
      {results && results.length > 0 && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-6 py-5 border-b border-gray-200">
            <div className="flex items-center">
              <ChartBarIcon className="h-6 w-6 text-gray-400 mr-3" />
              <h2 className="text-lg font-medium text-gray-900">Historical Performance</h2>
            </div>
          </div>
          <div className="overflow-hidden">
            <table className="min-w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Turn
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Capital
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Premiums
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Claims
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Combined Ratio
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Result
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {results.map((result) => {
                  const netResult = result.financial_results.ending_capital - result.financial_results.starting_capital;
                  const isProfit = netResult > 0;
                  
                  return (
                    <tr key={result.turn_number}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        Turn {result.turn_number}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {formatCurrency(result.financial_results.ending_capital)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {formatCurrency(result.financial_results.total_premiums)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {formatCurrency(result.financial_results.total_claims)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <span className={result.financial_results.combined_ratio > 100 ? 'text-red-600' : 'text-gray-900'}>
                          {formatPercent(result.financial_results.combined_ratio)}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <span className={`flex items-center ${isProfit ? 'text-green-600' : 'text-red-600'}`}>
                          {isProfit ? <ArrowUpIcon className="h-4 w-4 mr-1" /> : <ArrowDownIcon className="h-4 w-4 mr-1" />}
                          {formatCurrency(Math.abs(netResult))}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* No results yet */}
      {(!results || results.length === 0) && (
        <div className="bg-gray-50 rounded-lg p-6 text-center">
          <ClockIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No results yet</h3>
          <p className="mt-1 text-sm text-gray-500">
            Historical performance will appear here after your first turn is processed.
          </p>
        </div>
      )}
    </div>
  );
} 