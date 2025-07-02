'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface User {
  id: string;
  email: string;
  hasCompany?: boolean;
  companyId?: string;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  
  // Actions
  setAuth: (user: User, accessToken: string, refreshToken: string) => void;
  updateTokens: (accessToken: string, refreshToken: string) => void;
  logout: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,

      setAuth: (user, accessToken, refreshToken) => {
        set({ user, accessToken, refreshToken });
      },

      updateTokens: (accessToken, refreshToken) => {
        set({ accessToken, refreshToken });
      },

      logout: () => {
        set({ user: null, accessToken: null, refreshToken: null });
      },

      isAuthenticated: () => {
        return !!get().accessToken;
      },
    }),
    {
      name: 'auth-storage',
    }
  )
); 