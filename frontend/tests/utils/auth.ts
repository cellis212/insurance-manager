import { Page, expect } from '@playwright/test';

export interface TestUser {
  email: string;
  password: string;
  firstName: string;
  lastName: string;
}

export const testUsers = {
  student1: {
    email: 'test.student1@example.com',
    password: 'TestPassword123!',
    firstName: 'Test',
    lastName: 'Student'
  },
  student2: {
    email: 'test.student2@example.com', 
    password: 'TestPassword123!',
    firstName: 'Test',
    lastName: 'Student2'
  }
};

/**
 * Register a new test user
 */
export async function registerUser(page: Page, user: TestUser) {
  await page.goto('/auth/register');
  
  // Fill registration form
  await page.fill('[data-testid="first-name"]', user.firstName);
  await page.fill('[data-testid="last-name"]', user.lastName);
  await page.fill('[data-testid="email"]', user.email);
  await page.fill('[data-testid="password"]', user.password);
  await page.fill('[data-testid="confirm-password"]', user.password);
  
  // Submit registration
  await page.click('[data-testid="register-button"]');
  
  // Wait for successful registration
  await expect(page).toHaveURL('/auth/login');
}

/**
 * Login with existing user credentials
 */
export async function loginUser(page: Page, user: TestUser) {
  await page.goto('/auth/login');
  
  // Fill login form
  await page.fill('[data-testid="email"]', user.email);
  await page.fill('[data-testid="password"]', user.password);
  
  // Submit login
  await page.click('[data-testid="login-button"]');
  
  // Wait for successful login (should redirect to dashboard or company creation)
  await page.waitForURL(url => url.pathname === '/dashboard' || url.pathname === '/company/create');
}

/**
 * Logout current user
 */
export async function logoutUser(page: Page) {
  // Look for logout button in navigation
  await page.click('[data-testid="logout-button"]');
  
  // Should redirect to login page
  await expect(page).toHaveURL('/auth/login');
}

/**
 * Generate unique test user data
 */
export function generateTestUser(suffix?: string): TestUser {
  const timestamp = Date.now();
  const uniqueSuffix = suffix ? `${suffix}.${timestamp}` : timestamp;
  
  return {
    email: `test.user.${uniqueSuffix}@example.com`,
    password: 'TestPassword123!',
    firstName: 'Test',
    lastName: `User${uniqueSuffix}`
  };
}