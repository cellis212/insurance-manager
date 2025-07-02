'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { useAuthStore } from '@/stores/auth-store';

interface RegisterResponse {
  id: string;
  email: string;
  is_active: boolean;
  is_verified: boolean;
  last_login: string | null;
  created_at: string;
}

export default function RegisterPage() {
  const router = useRouter();
  const setAuth = useAuthStore((state) => state.setAuth);
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [passwordErrors, setPasswordErrors] = useState<string[]>([]);
  const [emailError, setEmailError] = useState('');
  const [confirmPasswordError, setConfirmPasswordError] = useState('');

  const validatePassword = (pwd: string): string[] => {
    const errors: string[] = [];
    if (pwd.length < 8) errors.push('At least 8 characters');
    if (!/[A-Z]/.test(pwd)) errors.push('One uppercase letter');
    if (!/[a-z]/.test(pwd)) errors.push('One lowercase letter');
    if (!/[0-9]/.test(pwd)) errors.push('One number');
    return errors;
  };

  const registerMutation = useMutation({
    mutationFn: async (data: { email: string; password: string; first_name: string; last_name: string }) => {
      return apiClient.post<RegisterResponse>('/auth/register', data, { skipAuth: true });
    },
    onSuccess: (data) => {
      // Registration successful, redirect to login page
      router.push('/auth/login');
    },
    onError: (error: Error) => {
      setError(error.message || 'Registration failed');
    },
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setEmailError('');
    setConfirmPasswordError('');
    setPasswordErrors([]);

    let hasErrors = false;

    // Validate required fields and set individual errors
    if (!firstName.trim()) {
      setError('First name is required');
      hasErrors = true;
    }

    if (!lastName.trim()) {
      if (!hasErrors) setError('Last name is required');
      hasErrors = true;
    }

    if (!email.trim()) {
      setEmailError('Email is required');
      hasErrors = true;
    }

    if (!password.trim()) {
      setPasswordErrors(['Password is required']);
      hasErrors = true;
    } else {
      // Validate password strength
      const pwdErrors = validatePassword(password);
      if (pwdErrors.length > 0) {
        setPasswordErrors(pwdErrors);
        hasErrors = true;
      }
    }

    if (!confirmPassword.trim()) {
      setConfirmPasswordError('Please confirm your password');
      hasErrors = true;
    } else if (password !== confirmPassword) {
      setConfirmPasswordError('Passwords do not match');
      hasErrors = true;
    }

    if (hasErrors) {
      return;
    }

    registerMutation.mutate({ 
      email, 
      password, 
      first_name: firstName,
      last_name: lastName 
    });
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            Insurance Manager
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Create your account
          </p>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="space-y-4">
            <div>
              <label htmlFor="first-name" className="block text-sm font-medium text-gray-700">
                First Name
              </label>
              <input
                id="first-name"
                name="first-name"
                type="text"
                autoComplete="given-name"
                required
                data-testid="first-name"
                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                placeholder="Enter your first name"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="last-name" className="block text-sm font-medium text-gray-700">
                Last Name
              </label>
              <input
                id="last-name"
                name="last-name"
                type="text"
                autoComplete="family-name"
                required
                data-testid="last-name"
                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                placeholder="Enter your last name"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="email-address" className="block text-sm font-medium text-gray-700">
                Email address
              </label>
              <input
                id="email-address"
                name="email"
                type="email"
                autoComplete="email"
                required
                data-testid="email"
                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                placeholder="Enter your email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              {emailError && (
                <p className="mt-2 text-sm text-red-600" data-testid="email-error">{emailError}</p>
              )}
            </div>
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="new-password"
                required
                data-testid="password"
                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                placeholder="Create a password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  setPasswordErrors(validatePassword(e.target.value));
                }}
              />
              {passwordErrors.length > 0 && (
                <ul className="mt-2 text-sm text-gray-600" data-testid="password-error">
                  <li className="font-medium">Password must contain:</li>
                  {passwordErrors.map((err) => (
                    <li key={err} className="ml-4">• {err}</li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <label htmlFor="confirm-password" className="block text-sm font-medium text-gray-700">
                Confirm Password
              </label>
              <input
                id="confirm-password"
                name="confirm-password"
                type="password"
                autoComplete="new-password"
                required
                data-testid="confirm-password"
                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                placeholder="Confirm your password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
              {confirmPasswordError && (
                <p className="mt-2 text-sm text-red-600" data-testid="confirm-password-error">{confirmPasswordError}</p>
              )}
            </div>
          </div>

          {error && (
            <div className="rounded-md bg-red-50 p-4">
              <div className="flex">
                <div className="ml-3">
                  <h3 className="text-sm font-medium text-red-800">{error}</h3>
                </div>
              </div>
            </div>
          )}

          <div>
            <button
              type="submit"
              disabled={registerMutation.isPending || passwordErrors.length > 0}
              data-testid="register-button"
              className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {registerMutation.isPending ? 'Creating account...' : 'Sign up'}
            </button>
          </div>

          <div className="flex items-center justify-between">
            <div className="text-sm">
              <Link
                href="/auth/login"
                className="font-medium text-indigo-600 hover:text-indigo-500"
              >
                Already have an account? Sign in
              </Link>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
} 