import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

// Types for different decision categories
interface ProductDecisions {
  [stateId: string]: {
    [lineId: string]: {
      tier: 'basic' | 'standard' | 'premium';
      priceMultiplier: number;
    };
  };
}

interface ExpansionDecisions {
  targetStates: string[];
  withdrawStates: string[];
}

interface EmployeeDecisions {
  hires: Array<{
    position: string;
    candidateId: string;
  }>;
  terminations: string[];
}

interface InvestmentDecisions {
  portfolioCharacteristics: {
    risk: number;
    duration: number;
    liquidity: number;
    credit: number;
    diversification: number;
  };
}

interface MarketingDecisions {
  budgetAllocation: {
    brand: number;
    directMarketing: number;
    agentIncentives: number;
    digitalMarketing: number;
  };
}

interface DecisionsState {
  // All decision categories
  productDecisions: ProductDecisions;
  expansionDecisions: ExpansionDecisions;
  employeeDecisions: EmployeeDecisions;
  investmentDecisions: InvestmentDecisions;
  marketingDecisions: MarketingDecisions;
  
  // Validation state
  hasUnsavedChanges: boolean;
  validationErrors: Record<string, string>;
  
  // Actions
  setProductDecision: (stateId: string, lineId: string, decision: ProductDecisions[string][string]) => void;
  setExpansionDecisions: (decisions: ExpansionDecisions) => void;
  setEmployeeDecisions: (decisions: EmployeeDecisions) => void;
  setInvestmentDecisions: (decisions: InvestmentDecisions) => void;
  setMarketingDecisions: (decisions: MarketingDecisions) => void;
  setValidationError: (field: string, error: string | null) => void;
  markAsSaved: () => void;
  resetDecisions: () => void;
}

const initialDecisions = {
  productDecisions: {},
  expansionDecisions: {
    targetStates: [],
    withdrawStates: [],
  },
  employeeDecisions: {
    hires: [],
    terminations: [],
  },
  investmentDecisions: {
    portfolioCharacteristics: {
      risk: 50,
      duration: 50,
      liquidity: 50,
      credit: 50,
      diversification: 50,
    },
  },
  marketingDecisions: {
    budgetAllocation: {
      brand: 25,
      directMarketing: 25,
      agentIncentives: 25,
      digitalMarketing: 25,
    },
  },
  hasUnsavedChanges: false,
  validationErrors: {},
};

export const useDecisionsStore = create<DecisionsState>()(
  devtools(
    (set) => ({
      ...initialDecisions,
      
      setProductDecision: (stateId, lineId, decision) =>
        set((state) => ({
          productDecisions: {
            ...state.productDecisions,
            [stateId]: {
              ...state.productDecisions[stateId],
              [lineId]: decision,
            },
          },
          hasUnsavedChanges: true,
        })),
      
      setExpansionDecisions: (expansionDecisions) =>
        set({ expansionDecisions, hasUnsavedChanges: true }),
      
      setEmployeeDecisions: (employeeDecisions) =>
        set({ employeeDecisions, hasUnsavedChanges: true }),
      
      setInvestmentDecisions: (investmentDecisions) =>
        set({ investmentDecisions, hasUnsavedChanges: true }),
      
      setMarketingDecisions: (marketingDecisions) =>
        set({ marketingDecisions, hasUnsavedChanges: true }),
      
      setValidationError: (field, error) =>
        set((state) => ({
          validationErrors: error
            ? { ...state.validationErrors, [field]: error }
            : Object.fromEntries(
                Object.entries(state.validationErrors).filter(([k]) => k !== field)
              ),
        })),
      
      markAsSaved: () =>
        set({ hasUnsavedChanges: false }),
      
      resetDecisions: () => set(initialDecisions),
    }),
    {
      name: 'insurance-manager-decisions',
    }
  )
); 