'use client';

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryClient } from '@/lib/query-client';
import { UserGroupIcon, UserPlusIcon, UserMinusIcon } from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';

interface Employee {
  id: string;
  name: string;
  position: string;
  skill_level: number;
  base_salary: number;
  bonus_paid_ytd: number;
  special_bonus: string | null;
  hire_date: string;
  quarters_employed: number;
  annual_cost: number;
}

interface EmployeeCandidate {
  name: string;
  position: string;
  skill_level: number;
  base_salary: number;
  special_bonus: string | null;
  personality: Record<string, string>;
  background: Record<string, any>;
  availability_expires: number;
}

type HiringPool = Record<string, EmployeeCandidate[]>;

const POSITION_ORDER = [
  'CEO',
  'CFO',
  'CUO',
  'CMO',
  'CCO',
  'CTO',
  'CRO',
  'CAO',
  'Chief Actuary'
];

const POSITION_DESCRIPTIONS: Record<string, string> = {
  'CFO': 'Chief Financial Officer - Manages investments and capital',
  'CUO': 'Chief Underwriting Officer - Improves risk selection',
  'CMO': 'Chief Marketing Officer - Drives growth and acquisition',
  'CCO': 'Chief Compliance Officer - Reduces regulatory penalties',
  'CTO': 'Chief Technology Officer - Cuts operational costs',
  'CRO': 'Chief Risk Officer - Mitigates catastrophe losses',
  'CAO': 'Chief Accounting Officer - Improves reserve accuracy',
  'Chief Actuary': 'Chief Actuary - Enhances pricing precision'
};

export default function EmployeesPage() {
  const [selectedPosition, setSelectedPosition] = useState<string | null>(null);
  const [confirmFire, setConfirmFire] = useState<string | null>(null);

  const { data: employees, isLoading: employeesLoading } = useQuery({
    queryKey: ['employees'],
    queryFn: () => apiClient.get<Employee[]>('/ceo/employees'),
  });

  const { data: hiringPool, isLoading: poolLoading } = useQuery({
    queryKey: ['hiring-pool'],
    queryFn: () => apiClient.get<HiringPool>('/ceo/hiring-pool'),
  });

  const hireMutation = useMutation({
    mutationFn: ({ candidateName, position }: { candidateName: string; position: string }) =>
      apiClient.post('/ceo/hire-employee', { 
        candidate_name: candidateName,
        position 
      }),
    onSuccess: (_, { candidateName, position }) => {
      queryClient.invalidateQueries({ queryKey: ['employees'] });
      queryClient.invalidateQueries({ queryKey: ['hiring-pool'] });
      setSelectedPosition(null);
      toast.success(`Successfully hired ${candidateName} as ${position}!`);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to hire employee');
    },
  });

  const fireMutation = useMutation({
    mutationFn: (employeeId: string) =>
      apiClient.delete(`/ceo/employees/${employeeId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employees'] });
      setConfirmFire(null);
      toast.success('Employee terminated successfully');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to terminate employee');
    },
  });

  const formatCurrency = (amount: number) =>
    new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);

  const getSkillColor = (skill: number) => {
    if (skill >= 80) return 'text-green-600';
    if (skill >= 60) return 'text-blue-600';
    if (skill >= 40) return 'text-gray-600';
    return 'text-red-600';
  };

  // Create a map of filled positions
  const filledPositions = new Map(
    employees?.map(emp => [emp.position, emp]) || []
  );

  // Get all positions (filled and vacant)
  const allPositions = POSITION_ORDER.filter(pos => pos !== 'CEO'); // CEO is managed separately

  if (employeesLoading || poolLoading) {
    return (
      <div className="p-8">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-8"></div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[...Array(8)].map((_, i) => (
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

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-900">Executive Management</h1>
        <p className="mt-1 text-sm text-gray-600">
          Hire and manage your C-suite executives to improve company performance
        </p>
      </div>

      {/* Employees Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {allPositions.map((position) => {
          const employee = filledPositions.get(position);
          const isVacant = !employee;

          return (
            <div key={position} className="bg-white p-6 rounded-lg shadow">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-lg font-medium text-gray-900">{position}</h3>
                  <p className="text-xs text-gray-500 mt-1">
                    {POSITION_DESCRIPTIONS[position]}
                  </p>
                </div>
                <UserGroupIcon className="h-6 w-6 text-gray-400" />
              </div>

              {isVacant ? (
                <div className="space-y-3">
                  <div className="text-center py-4">
                    <p className="text-gray-500 font-medium">Position Vacant</p>
                  </div>
                  <button
                    onClick={() => setSelectedPosition(position)}
                    className="w-full inline-flex items-center justify-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
                  >
                    <UserPlusIcon className="h-4 w-4 mr-2" />
                    Hire {position}
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Name:</span>
                    <span className="font-medium">{employee.name}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Skill Level:</span>
                    <span className={`font-medium ${getSkillColor(employee.skill_level)}`}>
                      {employee.skill_level}/100
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Base Salary:</span>
                    <span className="font-medium">{formatCurrency(employee.base_salary)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Total Cost:</span>
                    <span className="font-medium">{formatCurrency(employee.annual_cost)}</span>
                  </div>
                  {employee.special_bonus && (
                    <div className="mt-2 bg-purple-50 rounded-md p-2">
                      <p className="text-xs text-purple-800">
                        ⭐ {employee.special_bonus}
                      </p>
                    </div>
                  )}
                  <div className="mt-3 pt-3 border-t">
                    <p className="text-xs text-gray-500 mb-2">
                      Hired: {employee.hire_date} • {employee.quarters_employed} quarters
                    </p>
                    <button
                      onClick={() => setConfirmFire(employee.id)}
                      className="w-full inline-flex items-center justify-center px-3 py-2 border border-red-300 text-sm font-medium rounded-md text-red-700 bg-white hover:bg-red-50"
                    >
                      <UserMinusIcon className="h-4 w-4 mr-2" />
                      Fire Employee
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Hire Modal */}
      {selectedPosition && hiringPool && (
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[80vh] overflow-hidden">
            <div className="p-6 border-b">
              <h3 className="text-lg font-medium text-gray-900">
                Hire {selectedPosition}
              </h3>
              <p className="mt-1 text-sm text-gray-600">
                Select from available candidates for this position
              </p>
            </div>

            <div className="overflow-y-auto max-h-[calc(80vh-200px)] p-6">
              <div className="space-y-4">
                {hiringPool[selectedPosition]?.map((candidate, index) => (
                  <div key={index} className="border rounded-lg p-4 hover:bg-gray-50">
                    <div className="flex justify-between items-start mb-3">
                      <div>
                        <h4 className="font-medium text-gray-900">{candidate.name}</h4>
                        <div className="flex items-center space-x-4 mt-1">
                          <span className={`text-sm ${getSkillColor(candidate.skill_level)}`}>
                            Skill: {candidate.skill_level}/100
                          </span>
                          <span className="text-sm text-gray-600">
                            Salary: {formatCurrency(candidate.base_salary)}
                          </span>
                        </div>
                      </div>
                      <button
                        onClick={() => hireMutation.mutate({
                          candidateName: candidate.name,
                          position: selectedPosition
                        })}
                        disabled={hireMutation.isPending}
                        className="px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {hireMutation.isPending ? 'Hiring...' : 'Hire'}
                      </button>
                    </div>

                    {candidate.special_bonus && (
                      <div className="bg-purple-50 rounded-md p-2 mb-2">
                        <p className="text-xs text-purple-800">
                          ⭐ Special Bonus: {candidate.special_bonus}
                        </p>
                      </div>
                    )}

                    <div className="grid grid-cols-2 gap-4 text-xs">
                      <div>
                        <p className="text-gray-500">Background</p>
                        <p className="text-gray-700">
                          {candidate.background.previous_role} at {candidate.background.previous_company}
                        </p>
                        <p className="text-gray-700">
                          Education: {candidate.background.education}
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-500">Personality</p>
                        <p className="text-gray-700">
                          Style: {candidate.personality.management_style}
                        </p>
                        <p className="text-gray-700">
                          Focus: {candidate.personality.risk_appetite}
                        </p>
                      </div>
                    </div>

                    <p className="text-xs text-gray-500 mt-2">
                      Available for {candidate.availability_expires} more turns
                    </p>
                  </div>
                ))}

                {(!hiringPool[selectedPosition] || hiringPool[selectedPosition].length === 0) && (
                  <div className="text-center py-8">
                    <p className="text-gray-500">No candidates available for this position this week</p>
                  </div>
                )}
              </div>
            </div>

            <div className="p-6 border-t">
              <button
                onClick={() => setSelectedPosition(null)}
                className="w-full px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Fire Confirmation Modal */}
      {confirmFire && (
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              Confirm Termination
            </h3>
            <p className="text-sm text-gray-600 mb-6">
              Are you sure you want to fire this employee? This action cannot be undone.
            </p>
            <div className="flex space-x-3">
              <button
                onClick={() => fireMutation.mutate(confirmFire)}
                disabled={fireMutation.isPending}
                className="flex-1 px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {fireMutation.isPending ? 'Firing...' : 'Confirm Fire'}
              </button>
              <button
                onClick={() => setConfirmFire(null)}
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
