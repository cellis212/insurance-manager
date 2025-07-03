import { test, expect } from '@playwright/test';

test.describe('Empty Form DOM Debug', () => {
  test('inspect DOM after empty form submission', async ({ page }) => {
    await page.goto('/auth/register');

    // Submit empty form
    await page.click('[data-testid="register-button"]');
    
    // Wait for any state changes
    await page.waitForTimeout(2000);
    
    // Check all elements with data-testid containing "error"
    const errorTestIds = await page.locator('[data-testid*="error"]').all();
    console.log(`Found ${errorTestIds.length} elements with error testids`);
    
    for (let i = 0; i < errorTestIds.length; i++) {
      const testId = await errorTestIds[i].getAttribute('data-testid');
      const text = await errorTestIds[i].textContent();
      const visible = await errorTestIds[i].isVisible();
      console.log(`Error element ${i}: testid="${testId}", visible=${visible}, text="${text}"`);
    }
    
    // Check all elements with text-red classes
    const redTextElements = await page.locator('[class*="text-red"]').all();
    console.log(`Found ${redTextElements.length} elements with red text classes`);
    
    for (let i = 0; i < redTextElements.length; i++) {
      const className = await redTextElements[i].getAttribute('class');
      const text = await redTextElements[i].textContent();
      const visible = await redTextElements[i].isVisible();
      console.log(`Red text element ${i}: class="${className}", visible=${visible}, text="${text}"`);
    }
  });
});