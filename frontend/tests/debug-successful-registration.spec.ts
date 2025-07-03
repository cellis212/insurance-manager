import { test, expect } from '@playwright/test';

test.describe('Successful Registration Debug', () => {
  test('check if valid registration works', async ({ page }) => {
    await page.goto('/auth/register');

    // Generate unique email to avoid conflicts
    const uniqueEmail = `test${Date.now()}@example.com`;

    // Fill out the form completely with valid data
    await page.fill('[data-testid="first-name"]', 'Test');
    await page.fill('[data-testid="last-name"]', 'User');
    await page.fill('[data-testid="email"]', uniqueEmail);
    await page.fill('[data-testid="password"]', 'TestPassword123!');
    await page.fill('[data-testid="confirm-password"]', 'TestPassword123!');
    
    console.log('Form filled with valid data, email:', uniqueEmail);
    
    // Check if button is enabled
    const button = page.locator('[data-testid="register-button"]');
    console.log('Button enabled:', await button.isEnabled());
    
    // Submit the form
    await page.click('[data-testid="register-button"]');
    
    // Wait to see what happens
    await page.waitForTimeout(5000);
    
    // Check current URL
    const currentUrl = page.url();
    console.log('Current URL after submission:', currentUrl);
    
    // Check for any error messages
    const errorElements = page.locator('.text-red-800, .text-red-600');
    const errorCount = await errorElements.count();
    console.log(`Found ${errorCount} error messages after submission`);
    
    for (let i = 0; i < errorCount; i++) {
      const errorText = await errorElements.nth(i).textContent();
      console.log(`Error ${i}: ${errorText}`);
    }
    
    // Check for loading state
    const loadingText = page.locator('text="Creating account..."');
    console.log('Loading state visible:', await loadingText.isVisible());
  });
});