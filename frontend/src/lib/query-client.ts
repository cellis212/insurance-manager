import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Default stale time of 5 minutes for most data
      staleTime: 5 * 60 * 1000,
      // Cache time of 10 minutes
      gcTime: 10 * 60 * 1000,
      // Retry failed requests up to 3 times
      retry: 3,
      // Retry delay exponential backoff
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      // Refetch on window focus to ensure fresh data
      refetchOnWindowFocus: true,
      // Don't refetch on reconnect since game state is server-controlled
      refetchOnReconnect: false,
    },
    mutations: {
      // Retry mutations once on failure
      retry: 1,
    },
  },
});

// Query key factory for consistent key generation
export const queryKeys = {
  all: ['insurance-manager'] as const,
  auth: () => [...queryKeys.all, 'auth'] as const,
  currentUser: () => [...queryKeys.auth(), 'current'] as const,
  
  companies: () => [...queryKeys.all, 'companies'] as const,
  company: (id: string) => [...queryKeys.companies(), id] as const,
  companyFinancials: (id: string) => [...queryKeys.company(id), 'financials'] as const,
  companyEmployees: (id: string) => [...queryKeys.company(id), 'employees'] as const,
  
  turns: () => [...queryKeys.all, 'turns'] as const,
  currentTurn: () => [...queryKeys.turns(), 'current'] as const,
  turnResults: (id: string) => [...queryKeys.turns(), id, 'results'] as const,
  
  markets: () => [...queryKeys.all, 'markets'] as const,
  marketConditions: () => [...queryKeys.markets(), 'conditions'] as const,
  competitors: () => [...queryKeys.markets(), 'competitors'] as const,
  
  investments: () => [...queryKeys.all, 'investments'] as const,
  portfolio: (companyId: string) => [...queryKeys.investments(), companyId, 'portfolio'] as const,
};

// Custom hooks for cache invalidation
export const invalidateCompanyData = async (companyId: string) => {
  await queryClient.invalidateQueries({ queryKey: queryKeys.company(companyId) });
};

export const invalidateTurnData = async () => {
  await queryClient.invalidateQueries({ queryKey: queryKeys.turns() });
}; 