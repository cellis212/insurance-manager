import { test, expect } from '@playwright/test';
import { registerUser, loginUser, generateTestUser } from './utils/auth';
import { createCompany, testCompanies, navigateToOffice, submitTurnDecisions } from './utils/company';

test.describe('Core Gameplay Mechanics', () => {
  let testUser: any;
  let testCompany: any;
  
  test.beforeEach(async ({ page }) => {
    // Set up test user and company for each test
    testUser = generateTestUser('gameplay');
    testCompany = testCompanies.basic;
    
    await registerUser(page, testUser);
    await loginUser(page, testUser);
    await createCompany(page, testCompany);
  });

  test('expansion to neighboring states', async ({ page }) => {
    await navigateToOffice(page, 'expansion');
    
    // Verify Georgia is the home state
    const georgiaElement = page.locator('[data-testid="state-Georgia"]');
    await expect(georgiaElement).toHaveClass(/home-state/);
    
    // Verify neighboring states are available for expansion
    const neighboringStates = ['Florida', 'Alabama', 'Tennessee', 'North Carolina', 'South Carolina'];
    
    for (const state of neighboringStates) {
      const stateElement = page.locator(`[data-testid="state-${state}"]`);
      await expect(stateElement).toBeVisible();
      
      // Check if state is available for expansion (not already owned)
      const expandButton = stateElement.locator('[data-testid="expand-button"]');
      if (await expandButton.isVisible()) {
        // Try to expand to this state
        await expandButton.click();
        
        // Should show expansion details modal
        await expect(page.locator('[data-testid="expansion-modal"]')).toBeVisible();
        
        // Cancel for now
        await page.click('[data-testid="cancel-expansion"]');
        break;
      }
    }
  });

  test('product creation in different tiers', async ({ page }) => {
    await navigateToOffice(page, 'products');
    
    // Create a Tier 1 product (Basic)
    await page.click('[data-testid="create-product-button"]');
    
    // Should show product creation modal
    await expect(page.locator('[data-testid="product-modal"]')).toBeVisible();
    
    // Fill product details
    await page.fill('[data-testid="product-name"]', 'Basic Auto Coverage');
    await page.selectOption('[data-testid="product-tier"]', '1');
    await page.selectOption('[data-testid="product-line"]', 'Personal Auto');
    
    // Set basic pricing
    await page.fill('[data-testid="base-price"]', '1200');
    
    // Save product
    await page.click('[data-testid="save-product"]');
    
    // Verify product appears in list
    await expect(page.locator('[data-testid="product-list"]')).toContainText('Basic Auto Coverage');
    
    // Verify it's marked as Tier 1
    const productElement = page.locator('[data-testid="product-Basic Auto Coverage"]');
    await expect(productElement.locator('[data-testid="product-tier"]')).toContainText('Tier 1');
  });

  test('hire C-suite executives', async ({ page }) => {
    await navigateToOffice(page, 'employees');
    
    // Should see CEO already exists
    await expect(page.locator('[data-testid="ceo-card"]')).toBeVisible();
    await expect(page.locator('[data-testid="ceo-name"]')).toContainText(testCompany.ceoName);
    
    // Hire CFO
    await page.click('[data-testid="hire-cfo-button"]');
    
    // Should show hiring modal
    await expect(page.locator('[data-testid="hiring-modal"]')).toBeVisible();
    
    // Select a CFO candidate
    const cfoCandidate = page.locator('[data-testid="candidate-0"]');
    await expect(cfoCandidate).toBeVisible();
    
    // Check candidate details
    await expect(cfoCandidate.locator('[data-testid="candidate-name"]')).toBeVisible();
    await expect(cfoCandidate.locator('[data-testid="candidate-skill"]')).toBeVisible();
    await expect(cfoCandidate.locator('[data-testid="candidate-salary"]')).toBeVisible();
    
    // Hire the candidate
    await cfoCandidate.locator('[data-testid="hire-candidate"]').click();
    
    // Should close modal and show CFO in employee list
    await expect(page.locator('[data-testid="hiring-modal"]')).not.toBeVisible();
    await expect(page.locator('[data-testid="cfo-card"]')).toBeVisible();
  });

  test('investment portfolio management', async ({ page }) => {
    await navigateToOffice(page, 'investments');
    
    // Should see investment sliders
    await expect(page.locator('[data-testid="investment-sliders"]')).toBeVisible();
    
    // Test different asset classes
    const assetClasses = ['stocks', 'bonds', 'real-estate', 'cash'];
    
    for (const assetClass of assetClasses) {
      const slider = page.locator(`[data-testid="slider-${assetClass}"]`);
      await expect(slider).toBeVisible();
      
      // Get current value
      const currentValue = await slider.inputValue();
      
      // Adjust allocation
      await slider.fill('25'); // Set to 25%
      
      // Verify the change
      await expect(slider).toHaveValue('25');
    }
    
    // Verify total allocation adds up to 100%
    const totalAllocation = page.locator('[data-testid="total-allocation"]');
    await expect(totalAllocation).toContainText('100%');
    
    // Save portfolio changes
    await page.click('[data-testid="save-portfolio"]');
    
    // Should show success message
    await expect(page.locator('[data-testid="portfolio-saved"]')).toBeVisible();
  });

  test('turn decision submission flow', async ({ page }) => {
    // Make some decisions first
    await navigateToOffice(page, 'products');
    
    // Create a basic product if none exists
    const productCount = await page.locator('[data-testid="product-item"]').count();
    if (productCount === 0) {
      await page.click('[data-testid="create-product-button"]');
      await page.fill('[data-testid="product-name"]', 'Test Product');
      await page.selectOption('[data-testid="product-tier"]', '1');
      await page.selectOption('[data-testid="product-line"]', 'Personal Auto');
      await page.fill('[data-testid="base-price"]', '1000');
      await page.click('[data-testid="save-product"]');
    }
    
    // Now go to decisions page
    await navigateToOffice(page, 'decisions');
    
    // Should see decision summary
    await expect(page.locator('[data-testid="decisions-summary"]')).toBeVisible();
    
    // Should show current state of all decisions
    await expect(page.locator('[data-testid="product-decisions"]')).toBeVisible();
    await expect(page.locator('[data-testid="investment-decisions"]')).toBeVisible();
    
    // Submit decisions
    await submitTurnDecisions(page);
    
    // Verify submission success
    await expect(page.locator('[data-testid="submission-success"]')).toContainText('submitted');
  });

  test('information asymmetry in investments', async ({ page }) => {
    // This test verifies that CFO skill affects what investment information is shown
    await navigateToOffice(page, 'employees');
    
    // Check if we have a CFO
    const cfoExists = await page.locator('[data-testid="cfo-card"]').isVisible();
    
    if (!cfoExists) {
      // Hire a CFO first
      await page.click('[data-testid="hire-cfo-button"]');
      await page.locator('[data-testid="candidate-0"] [data-testid="hire-candidate"]').click();
    }
    
    // Go to investments page
    await navigateToOffice(page, 'investments');
    
    // Get CFO skill level
    const cfoSkillElement = page.locator('[data-testid="cfo-skill"]');
    
    if (await cfoSkillElement.isVisible()) {
      const cfoSkillText = await cfoSkillElement.textContent();
      const cfoSkill = parseInt(cfoSkillText?.match(/\d+/)?.[0] || '0');
      
      // Check investment information visibility based on CFO skill
      if (cfoSkill >= 60) {
        // Expert CFO should see detailed investment information
        await expect(page.locator('[data-testid="detailed-returns"]')).toBeVisible();
        await expect(page.locator('[data-testid="risk-analysis"]')).toBeVisible();
      } else {
        // Novice CFO should see limited information
        await expect(page.locator('[data-testid="basic-returns"]')).toBeVisible();
        // Detailed information should be hidden or limited
        const detailedInfo = page.locator('[data-testid="detailed-returns"]');
        if (await detailedInfo.isVisible()) {
          // Should show less precise information
          await expect(detailedInfo).toContainText('~'); // Approximate values
        }
      }
    }
  });
});