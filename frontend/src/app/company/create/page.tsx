'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery, useMutation } from '@tanstack/react-query';
import { gameApi, University, AcademicBackground } from '@/lib/api-services';
import { useAuthStore } from '@/stores/auth-store';

export default function CreateCompanyPage() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    companyName: '',
    ceoName: '',
    academicBackgroundId: '',
    universityId: '',
  });
  const [selectedBackground, setSelectedBackground] = useState<AcademicBackground | null>(null);
  const [selectedUniversity, setSelectedUniversity] = useState<University | null>(null);

  // Fetch data
  const { data: backgrounds } = useQuery({
    queryKey: ['academic-backgrounds'],
    queryFn: gameApi.getAcademicBackgrounds,
  });

  const { data: universities } = useQuery({
    queryKey: ['universities'],
    queryFn: gameApi.getUniversities,
  });

  // Create company mutation
  const createCompanyMutation = useMutation({
    mutationFn: gameApi.createCompany,
    onSuccess: () => {
      router.push('/dashboard');
    },
  });

  const handleNext = () => {
    if (step === 1 && formData.companyName && formData.ceoName) {
      setStep(2);
    } else if (step === 2 && formData.academicBackgroundId) {
      setStep(3);
    }
  };

  const handleBack = () => {
    setStep(step - 1);
  };

  const handleSubmit = () => {
    createCompanyMutation.mutate({
      company_name: formData.companyName,
      ceo_name: formData.ceoName,
      academic_background_id: formData.academicBackgroundId,
      university_id: formData.universityId,
    });
  };

  const formatBonuses = (bg: AcademicBackground) => {
    const bonuses = [];
    if (bg.leadership_bonus > 0) bonuses.push(`Leadership +${bg.leadership_bonus}`);
    if (bg.risk_intelligence_bonus > 0) bonuses.push(`Risk Intelligence +${bg.risk_intelligence_bonus}`);
    if (bg.market_acumen_bonus > 0) bonuses.push(`Market Acumen +${bg.market_acumen_bonus}`);
    if (bg.regulatory_mastery_bonus > 0) bonuses.push(`Regulatory Mastery +${bg.regulatory_mastery_bonus}`);
    if (bg.innovation_capacity_bonus > 0) bonuses.push(`Innovation +${bg.innovation_capacity_bonus}`);
    if (bg.deal_making_bonus > 0) bonuses.push(`Deal Making +${bg.deal_making_bonus}`);
    if (bg.financial_expertise_bonus > 0) bonuses.push(`Financial Expertise +${bg.financial_expertise_bonus}`);
    if (bg.crisis_command_bonus > 0) bonuses.push(`Crisis Command +${bg.crisis_command_bonus}`);
    return bonuses;
  };

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto">
        <div className="bg-white shadow-sm rounded-lg p-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-8">Create Your Insurance Company</h1>

          {/* Progress indicator */}
          <div className="mb-8">
            <div className="flex items-center">
              <div className={`flex-1 ${step >= 1 ? 'bg-indigo-600' : 'bg-gray-200'} h-2 rounded`} />
              <div className={`flex-1 ${step >= 2 ? 'bg-indigo-600' : 'bg-gray-200'} h-2 rounded mx-2`} />
              <div className={`flex-1 ${step >= 3 ? 'bg-indigo-600' : 'bg-gray-200'} h-2 rounded`} />
            </div>
            <div className="flex justify-between mt-2 text-sm text-gray-600">
              <span>Company & CEO</span>
              <span>Education</span>
              <span>University</span>
            </div>
          </div>

          {/* Step 1: Basic Info */}
          {step === 1 && (
            <div className="space-y-6">
              <div>
                <label htmlFor="company-name" className="block text-sm font-medium text-gray-700">
                  Company Name
                </label>
                <input
                  type="text"
                  id="company-name"
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                  placeholder="e.g., Midwest Insurance Group"
                  value={formData.companyName}
                  onChange={(e) => setFormData({ ...formData, companyName: e.target.value })}
                />
              </div>

              <div>
                <label htmlFor="ceo-name" className="block text-sm font-medium text-gray-700">
                  CEO Name
                </label>
                <input
                  type="text"
                  id="ceo-name"
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                  placeholder="e.g., John Smith"
                  value={formData.ceoName}
                  onChange={(e) => setFormData({ ...formData, ceoName: e.target.value })}
                />
              </div>

              <div className="flex justify-end">
                <button
                  onClick={handleNext}
                  disabled={!formData.companyName || !formData.ceoName}
                  className="px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            </div>
          )}

          {/* Step 2: Academic Background */}
          {step === 2 && (
            <div className="space-y-6">
              <h2 className="text-lg font-medium text-gray-900">Select Academic Background</h2>
              <p className="text-sm text-gray-600">
                Your CEO's education will provide permanent bonuses to their attributes.
              </p>

              <div className="space-y-3">
                {backgrounds?.map((bg) => (
                  <label
                    key={bg.id}
                    className={`relative flex cursor-pointer rounded-lg border p-4 hover:bg-gray-50 ${
                      formData.academicBackgroundId === bg.id
                        ? 'border-indigo-500 bg-indigo-50'
                        : 'border-gray-300'
                    }`}
                  >
                    <input
                      type="radio"
                      name="background"
                      value={bg.id}
                      checked={formData.academicBackgroundId === bg.id}
                      onChange={() => {
                        setFormData({ ...formData, academicBackgroundId: bg.id });
                        setSelectedBackground(bg);
                      }}
                      className="sr-only"
                    />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-900">
                        {bg.primary_major} + {bg.secondary_major}
                      </p>
                      <p className="mt-1 text-sm text-gray-600">
                        {formatBonuses(bg).join(', ')}
                      </p>
                    </div>
                  </label>
                ))}
              </div>

              <div className="flex justify-between">
                <button
                  onClick={handleBack}
                  className="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                >
                  Back
                </button>
                <button
                  onClick={handleNext}
                  disabled={!formData.academicBackgroundId}
                  className="px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            </div>
          )}

          {/* Step 3: University Selection */}
          {step === 3 && (
            <div className="space-y-6">
              <h2 className="text-lg font-medium text-gray-900">Select Your Alma Mater</h2>
              <p className="text-sm text-gray-600">
                Your home state will be determined by your university location, giving you immediate market access and regulatory advantages.
              </p>

              <div className="space-y-3">
                <input
                  type="text"
                  placeholder="Search universities..."
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                  onChange={(e) => {
                    // Simple filter - in production would use better search
                    const searchTerm = e.target.value.toLowerCase();
                    // Filter universities based on search
                  }}
                />

                <div className="max-h-96 overflow-y-auto space-y-2">
                  {universities?.map((uni) => (
                    <label
                      key={uni.id}
                      className={`relative flex cursor-pointer rounded-lg border p-4 hover:bg-gray-50 ${
                        formData.universityId === uni.id
                          ? 'border-indigo-500 bg-indigo-50'
                          : 'border-gray-300'
                      }`}
                    >
                      <input
                        type="radio"
                        name="university"
                        value={uni.id}
                        checked={formData.universityId === uni.id}
                        onChange={() => {
                          setFormData({ ...formData, universityId: uni.id });
                          setSelectedUniversity(uni);
                        }}
                        className="sr-only"
                      />
                      <div className="flex-1">
                        <p className="text-sm font-medium text-gray-900">{uni.name}</p>
                        <p className="text-sm text-gray-600">
                          {uni.city}, {uni.state_code}
                          {uni.is_major && ' • Major University'}
                        </p>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              <div className="flex justify-between">
                <button
                  onClick={handleBack}
                  className="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                >
                  Back
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={!formData.universityId || createCompanyMutation.isPending}
                  className="px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {createCompanyMutation.isPending ? 'Creating...' : 'Create Company'}
                </button>
              </div>
            </div>
          )}

          {createCompanyMutation.isError && (
            <div className="mt-4 rounded-md bg-red-50 p-4">
              <p className="text-sm text-red-800">
                {createCompanyMutation.error?.message || 'Failed to create company'}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
} 