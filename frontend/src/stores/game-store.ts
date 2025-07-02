import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

// Types for the game state
interface CEOAttributes {
  leadership: number;
  riskIntelligence: number;
  regulatoryCompliance: number;
  capitalEfficiency: number;
  marketSensing: number;
  distributionManagement: number;
  techInnovation: number;
  esgInitiatives: number;
}

interface Company {
  id: string;
  name: string;
  homeState: string;
  currentCapital: number;
  solvencyRatio: number;
  foundedDate: string;
}

interface GameState {
  // User and session
  userId: string | null;
  sessionId: string | null;
  semesterId: string | null;
  
  // Company data
  company: Company | null;
  ceoAttributes: CEOAttributes | null;
  
  // Current turn
  currentTurn: number;
  turnDeadline: Date | null;
  turnStatus: 'pending' | 'submitted' | 'processing' | 'completed';
  
  // UI state
  selectedOffice: string;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  setUser: (userId: string, sessionId: string, semesterId: string) => void;
  setCompany: (company: Company) => void;
  setCEOAttributes: (attributes: CEOAttributes) => void;
  setCurrentTurn: (turn: number, deadline: Date) => void;
  setTurnStatus: (status: GameState['turnStatus']) => void;
  setSelectedOffice: (office: string) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  resetGame: () => void;
}

const initialState = {
  userId: null,
  sessionId: null,
  semesterId: null,
  company: null,
  ceoAttributes: null,
  currentTurn: 0,
  turnDeadline: null,
  turnStatus: 'pending' as const,
  selectedOffice: 'ceo',
  isLoading: false,
  error: null,
};

export const useGameStore = create<GameState>()(
  devtools(
    persist(
      (set) => ({
        ...initialState,
        
        setUser: (userId, sessionId, semesterId) =>
          set({ userId, sessionId, semesterId }),
        
        setCompany: (company) => set({ company }),
        
        setCEOAttributes: (ceoAttributes) => set({ ceoAttributes }),
        
        setCurrentTurn: (currentTurn, turnDeadline) =>
          set({ currentTurn, turnDeadline }),
        
        setTurnStatus: (turnStatus) => set({ turnStatus }),
        
        setSelectedOffice: (selectedOffice) => set({ selectedOffice }),
        
        setLoading: (isLoading) => set({ isLoading }),
        
        setError: (error) => set({ error }),
        
        resetGame: () => set(initialState),
      }),
      {
        name: 'insurance-manager-game',
        partialize: (state) => ({
          // Only persist essential data
          userId: state.userId,
          sessionId: state.sessionId,
          semesterId: state.semesterId,
          selectedOffice: state.selectedOffice,
        }),
      }
    )
  )
); 