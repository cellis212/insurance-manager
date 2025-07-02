import { test, expect } from '@playwright/test';

test.describe('Form Validation Debug', () => {
  test('check empty form submission behavior', async ({ page }) => {
    await page.goto('/auth/register');

    // Click submit without filling anything
    await page.click('[data-testid="register-button"]');
    
    // Wait a moment for any async validation
    await page.waitForTimeout(2000);
    
    // Check specific error elements by data-testid
    const emailError = page.locator('[data-testid="email-error"]');
    const passwordError = page.locator('[data-testid="password-error"]');
    
    console.log('Email error visible:', await emailError.isVisible());
    console.log('Password error visible:', await passwordError.isVisible());
    
    if (await emailError.isVisible()) {
      console.log('Email error text:', await emailError.textContent());
    }
    
    if (await passwordError.isVisible()) {
      console.log('Password error text:', await passwordError.textContent());
    }
    
    // Also check for any general error messages
    const generalError = page.locator('.text-red-800, .text-red-600');
    const errorCount = await generalError.count();
    console.log(`Found ${errorCount} general error messages`);
    
    for (let i = 0; i < errorCount; i++) {
      const errorText = await generalError.nth(i).textContent();
      console.log(`General error ${i}: ${errorText}`);
    }
  });
  
  test('check password mismatch behavior', async ({ page }) => {
    await page.goto('/auth/register');

    // Fill different passwords
    await page.fill('[data-testid="email"]', 'test@example.com');
    await page.fill('[data-testid="password"]', 'Password123!');
    await page.fill('[data-testid="confirm-password"]', 'DifferentPassword123!');
    await page.click('[data-testid="register-button"]');
    
    // Wait for validation
    await page.waitForTimeout(1000);
    
    // Check for password mismatch error
    const confirmPasswordError = page.locator('[data-testid="confirm-password-error"]');
    console.log('Confirm password error visible:', await confirmPasswordError.isVisible());
    
    if (await confirmPasswordError.isVisible()) {
      console.log('Confirm password error text:', await confirmPasswordError.textContent());
    }
  });
});