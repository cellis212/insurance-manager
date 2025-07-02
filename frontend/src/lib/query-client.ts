import { QueryClient } from '@tanstack/react-query';

// Cache duration constants
const CACHE_DURATIONS = {
  // Static data - rarely changes (24 hours)
  STATIC: {
    staleTime: 24 * 60 * 60 * 1000,
    gcTime: 48 * 60 * 60 * 1000,
  },
  // Semi-static data - changes occasionally (1 hour)
  SEMI_STATIC: {
    staleTime: 60 * 60 * 1000,
    gcTime: 2 * 60 * 60 * 1000,
  },
  // Dynamic data - changes frequently (5 minutes)
  DYNAMIC: {
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  },
  // Real-time data - always fresh (30 seconds)
  REAL_TIME: {
    staleTime: 30 * 1000,
    gcTime: 60 * 1000,
  },
} as const;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Default to dynamic caching for most data
      ...CACHE_DURATIONS.DYNAMIC,
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

// Query key factory for consistent key generation with cache hints
export const queryKeys = {
  all: ['insurance-manager'] as const,
  
  // Authentication - dynamic caching
  auth: () => [...queryKeys.all, 'auth'] as const,
  currentUser: () => [...queryKeys.auth(), 'current'] as const,
  
  // Company data - dynamic caching
  companies: () => [...queryKeys.all, 'companies'] as const,
  company: (id: string) => [...queryKeys.companies(), id] as const,
  companyFinancials: (id: string) => [...queryKeys.company(id), 'financials'] as const,
  companyEmployees: (id: string) => [...queryKeys.company(id), 'employees'] as const,
  
  // Turn data - real-time caching
  turns: () => [...queryKeys.all, 'turns'] as const,
  currentTurn: () => [...queryKeys.turns(), 'current'] as const,
  turnResults: (id: string) => [...queryKeys.turns(), id, 'results'] as const,
  turnDecisions: () => [...queryKeys.turns(), 'decisions'] as const,
  
  // Market data - semi-static caching
  markets: () => [...queryKeys.all, 'markets'] as const,
  marketConditions: () => [...queryKeys.markets(), 'conditions'] as const,
  competitors: () => [...queryKeys.markets(), 'competitors'] as const,
  
  // Investment data - dynamic caching
  investments: () => [...queryKeys.all, 'investments'] as const,
  portfolio: (companyId: string) => [...queryKeys.investments(), companyId, 'portfolio'] as const,
  
  // Static reference data - long caching
  states: () => [...queryKeys.all, 'states'] as const,
  linesOfBusiness: () => [...queryKeys.all, 'lines-of-business'] as const,
  universities: () => [...queryKeys.all, 'universities'] as const,
  gameConfig: () => [...queryKeys.all, 'game-config'] as const,
  
  // Semi-static data
  employeeCandidates: () => [...queryKeys.all, 'employee-candidates'] as const,
  products: (companyId: string) => [...queryKeys.all, 'products', companyId] as const,
  expansions: (companyId: string) => [...queryKeys.all, 'expansions', companyId] as const,
};

// Cache configuration overrides for specific query types
export const queryCacheConfigs = {
  // Static data queries
  static: CACHE_DURATIONS.STATIC,
  // Semi-static data queries
  semiStatic: CACHE_DURATIONS.SEMI_STATIC,
  // Dynamic data queries (default)
  dynamic: CACHE_DURATIONS.DYNAMIC,
  // Real-time data queries
  realTime: CACHE_DURATIONS.REAL_TIME,
};

// Custom hooks for cache invalidation
export const invalidateCompanyData = async (companyId: string) => {
  await queryClient.invalidateQueries({ queryKey: queryKeys.company(companyId) });
};

export const invalidateTurnData = async () => {
  await queryClient.invalidateQueries({ queryKey: queryKeys.turns() });
};

// Prefetch static data on app initialization
export const prefetchStaticData = async () => {
  // These queries will be cached for 24 hours
  const staticQueries = [
    { queryKey: queryKeys.states() },
    { queryKey: queryKeys.linesOfBusiness() },
    { queryKey: queryKeys.universities() },
    { queryKey: queryKeys.gameConfig() },
  ];
  
  // Prefetch all static data in parallel
  await Promise.all(
    staticQueries.map(query => 
      queryClient.prefetchQuery({
        ...query,
        // Apply static cache configuration
        ...queryCacheConfigs.static,
      })
    )
  );
}; 