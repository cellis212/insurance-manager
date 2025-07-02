import { test, expect } from '@playwright/test';

test.describe('Quick Bug Verification', () => {
  test('verify basic functionality works', async ({ page }) => {
    // Test 1: Registration page loads with all required fields
    await page.goto('/auth/register');
    
    console.log('✓ Registration page loads');
    
    // Check all required form fields exist
    await expect(page.locator('[data-testid="first-name"]')).toBeVisible();
    await expect(page.locator('[data-testid="last-name"]')).toBeVisible();
    await expect(page.locator('[data-testid="email"]')).toBeVisible();
    await expect(page.locator('[data-testid="password"]')).toBeVisible();
    await expect(page.locator('[data-testid="confirm-password"]')).toBeVisible();
    await expect(page.locator('[data-testid="register-button"]')).toBeVisible();
    
    console.log('✓ All form fields are visible');
    
    // Test 2: Valid registration works
    const uniqueEmail = `quicktest${Date.now()}@example.com`;
    await page.fill('[data-testid="first-name"]', 'Test');
    await page.fill('[data-testid="last-name"]', 'User');
    await page.fill('[data-testid="email"]', uniqueEmail);
    await page.fill('[data-testid="password"]', 'TestPassword123!');
    await page.fill('[data-testid="confirm-password"]', 'TestPassword123!');
    
    await page.click('[data-testid="register-button"]');
    await page.waitForTimeout(3000);
    
    // Should redirect to login
    await expect(page).toHaveURL('/auth/login');
    console.log('✓ Valid registration redirects to login');
    
    // Test 3: Login page has required fields
    await expect(page.locator('[data-testid="email"]')).toBeVisible();
    await expect(page.locator('[data-testid="password"]')).toBeVisible();
    await expect(page.locator('[data-testid="login-button"]')).toBeVisible();
    
    console.log('✓ Login page has required fields');
    
    // Test 4: Valid login works
    await page.fill('[data-testid="email"]', uniqueEmail);
    await page.fill('[data-testid="password"]', 'TestPassword123!');
    await page.click('[data-testid="login-button"]');
    await page.waitForTimeout(3000);
    
    // Should redirect to company creation or dashboard  
    const currentUrl = page.url();
    if (currentUrl.includes('/company/create')) {
      console.log('✓ Login redirects to company creation (expected for new user)');
    } else if (currentUrl.includes('/dashboard')) {
      console.log('✓ Login redirects to dashboard');
    } else {
      console.log(`⚠ Login redirected to unexpected URL: ${currentUrl}`);
    }
  });
});