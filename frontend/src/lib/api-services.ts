import { apiClient } from './api-client';

// Types
export interface University {
  id: string;
  name: string;
  state_code: string;
  city: string;
  is_major: boolean;
}

export interface AcademicBackground {
  id: string;
  primary_major: string;
  secondary_major: string;
  leadership_bonus: number;
  risk_intelligence_bonus: number;
  market_acumen_bonus: number;
  regulatory_mastery_bonus: number;
  innovation_capacity_bonus: number;
  deal_making_bonus: number;
  financial_expertise_bonus: number;
  crisis_command_bonus: number;
}

export interface CreateCompanyRequest {
  company_name: string;
  ceo_name: string;
  academic_background_id: string;
  university_id: string;
}

export interface CreateCompanyResponse {
  company: {
    id: string;
    name: string;
    home_state_id: string;
    current_capital: number;
  };
  ceo: {
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
  };
}

export interface DashboardData {
  company: {
    id: string;
    name: string;
    current_capital: number;
    solvency_ratio: number;
    market_position: any;
  };
  financial_summary: {
    current_capital: number;
    total_premiums: number;
    total_claims: number;
    combined_ratio: number;
    investment_income: number;
  };
  current_turn: {
    turn_number: number;
    status: string;
    deadline: string;
  };
  recent_events: Array<{
    id: string;
    turn_number: number;
    category: string;
    severity: string;
    description: string;
    impact: any;
  }>;
  compliance_score: number;
}

// API Services
export const gameApi = {
  // CEO System
  getUniversities: () => apiClient.get<University[]>('/ceo/universities'),
  getAcademicBackgrounds: () => apiClient.get<AcademicBackground[]>('/ceo/academic-backgrounds'),
  
  // Game
  createCompany: (data: CreateCompanyRequest) => 
    apiClient.post<CreateCompanyResponse>('/game/create-company', data),
  getDashboard: () => apiClient.get<DashboardData>('/game/dashboard'),
  
  // Add more API calls as needed
}; 