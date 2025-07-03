import { test, expect } from '@playwright/test';

test.describe('Debug Tests', () => {
  test('can connect to app and visit registration page', async ({ page }) => {
    console.log('Starting debug test...');
    
    // Go to registration page
    await page.goto('/auth/register');
    
    // Check if page loads
    await expect(page.locator('h2')).toContainText('Insurance Manager');
    console.log('Page loaded successfully');
    
    // Check if form fields exist
    await expect(page.locator('[data-testid="first-name"]')).toBeVisible();
    await expect(page.locator('[data-testid="last-name"]')).toBeVisible();
    await expect(page.locator('[data-testid="email"]')).toBeVisible();
    await expect(page.locator('[data-testid="password"]')).toBeVisible();
    await expect(page.locator('[data-testid="confirm-password"]')).toBeVisible();
    await expect(page.locator('[data-testid="register-button"]')).toBeVisible();
    
    console.log('All form fields found');
  });

  test('can fill out registration form', async ({ page }) => {
    await page.goto('/auth/register');
    
    // Fill out the form
    await page.fill('[data-testid="first-name"]', 'Test');
    await page.fill('[data-testid="last-name"]', 'User');
    await page.fill('[data-testid="email"]', 'testuser@example.com');
    await page.fill('[data-testid="password"]', 'TestPassword123!');
    await page.fill('[data-testid="confirm-password"]', 'TestPassword123!');
    
    console.log('Form filled successfully');
    
    // Check if submit button is enabled
    await expect(page.locator('[data-testid="register-button"]')).toBeEnabled();
  });
});