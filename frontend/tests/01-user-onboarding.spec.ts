import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { registerUser, loginUser, generateTestUser } from './utils/auth';
import { createCompany, testCompanies, verifyHomeStateAdvantages } from './utils/company';

test.describe('User Onboarding Flow', () => {
  test('complete new player onboarding journey', async ({ page }) => {
    // Generate unique test user
    const testUser = generateTestUser('onboarding');
    const testCompany = testCompanies.basic;

    // Step 1: User Registration
    await test.step('User Registration', async () => {
      await registerUser(page, testUser);
      
      // Verify we're redirected to login
      await expect(page).toHaveURL('/auth/login');
    });

    // Step 2: User Login
    await test.step('User Login', async () => {
      await loginUser(page, testUser);
      
      // Should redirect to company creation since no company exists
      await expect(page).toHaveURL('/company/create');
    });

    // Step 3: Company Creation Wizard
    await test.step('Company Creation', async () => {
      await createCompany(page, testCompany);
      
      // Should now be on dashboard
      await expect(page).toHaveURL('/dashboard');
      
      // Verify company details are displayed
      await expect(page.locator('[data-testid="company-name"]')).toContainText(testCompany.name);
      await expect(page.locator('[data-testid="ceo-name"]')).toContainText(testCompany.ceoName);
    });

    // Step 4: Verify Home State Advantages
    await test.step('Home State Advantages', async () => {
      // University of Georgia -> Georgia should be home state
      await verifyHomeStateAdvantages(page, 'Georgia');
    });

    // Step 5: Verify All Dashboard Pages Load
    await test.step('Dashboard Navigation', async () => {
      const offices = ['ceo', 'expansion', 'products', 'employees', 'investments', 'company', 'decisions'];
      
      for (const office of offices) {
        await page.goto(`/dashboard/${office}`);
        await expect(page).toHaveURL(`/dashboard/${office}`);
        
        // Verify page loads without errors
        const errorElements = page.locator('[data-testid="error-message"]');
        await expect(errorElements).toHaveCount(0);
        
        // Verify loading states are not stuck
        const loadingElements = page.locator('[data-testid="loading"]');
        await expect(loadingElements).toHaveCount(0, { timeout: 10000 });
      }
    });

    // Step 6: Accessibility Check
    await test.step('Accessibility Compliance', async () => {
      const accessibilityScanResults = await new AxeBuilder({ page }).analyze();
      expect(accessibilityScanResults.violations).toEqual([]);
    });
  });

  test('user login with existing account', async ({ page }) => {
    // Create user first (this would typically be done in beforeEach or fixture)
    const testUser = generateTestUser('existing');
    await registerUser(page, testUser);
    
    // Now test login flow
    await loginUser(page, testUser);
    
    // Should redirect to company creation since no company exists yet
    await expect(page).toHaveURL('/company/create');
  });

  test('form validation on registration', async ({ page }) => {
    await page.goto('/auth/register');

    // Test empty form submission
    await page.click('[data-testid="register-button"]');
    
    // Should show validation errors
    await expect(page.locator('[data-testid="email-error"]')).toBeVisible();
    await expect(page.locator('[data-testid="password-error"]')).toBeVisible();
    
    // Test password mismatch
    await page.fill('[data-testid="email"]', 'test@example.com');
    await page.fill('[data-testid="password"]', 'Password123!');
    await page.fill('[data-testid="confirm-password"]', 'DifferentPassword123!');
    await page.click('[data-testid="register-button"]');
    
    await expect(page.locator('[data-testid="confirm-password-error"]')).toContainText('match');
  });

  test('form validation on company creation', async ({ page }) => {
    const testUser = generateTestUser('validation');
    await registerUser(page, testUser);
    await loginUser(page, testUser);
    
    // Should be on company creation page
    await expect(page).toHaveURL('/company/create');
    
    // Try to proceed without selecting academic background
    await page.click('[data-testid="next-button"]');
    
    // Should show validation error
    await expect(page.locator('[data-testid="primary-major-error"]')).toBeVisible();
    
    // Fill in required field and proceed
    await page.selectOption('[data-testid="primary-major"]', 'Risk Management and Insurance');
    await page.click('[data-testid="next-button"]');
    
    // Try to proceed without alma mater
    await page.click('[data-testid="next-button"]');
    await expect(page.locator('[data-testid="alma-mater-error"]')).toBeVisible();
  });
});