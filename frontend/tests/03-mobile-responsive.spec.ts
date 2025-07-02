import { test, expect, devices } from '@playwright/test';
import { registerUser, loginUser, generateTestUser } from './utils/auth';
import { createCompany, testCompanies, navigateToOffice } from './utils/company';

// Create separate test projects for different devices
const mobileTest = test.extend({});
mobileTest.use(devices['iPhone 12']);

const landscapeTest = test.extend({});
landscapeTest.use({
  ...devices['iPhone 12'],
  viewport: { width: 844, height: 390 }, // Landscape orientation
});

const tabletTest = test.extend({});
tabletTest.use(devices['iPad Pro']);

test.describe('Mobile Responsiveness', () => {
  let testUser: any;
  let testCompany: any;
  
  mobileTest.beforeEach(async ({ page }) => {
    // Set up test user and company for mobile tests
    testUser = generateTestUser('mobile');
    testCompany = testCompanies.basic;
    
    await registerUser(page, testUser);
    await loginUser(page, testUser);
    await createCompany(page, testCompany);
  });

  mobileTest('mobile navigation through executive offices', async ({ page }) => {
    // Test hamburger menu functionality on mobile
    await page.goto('/dashboard');
    
    // Should see mobile navigation toggle
    const navToggle = page.locator('[data-testid="mobile-nav-toggle"]');
    await expect(navToggle).toBeVisible();
    
    // Open mobile menu
    await navToggle.click();
    
    // Should see navigation menu
    const mobileMenu = page.locator('[data-testid="mobile-menu"]');
    await expect(mobileMenu).toBeVisible();
    
    // Test navigation to each office
    const offices = ['ceo', 'expansion', 'products', 'employees', 'investments', 'company', 'decisions'];
    
    for (const office of offices) {
      // Open menu if it's closed
      if (!(await mobileMenu.isVisible())) {
        await navToggle.click();
      }
      
      // Click office link
      await page.click(`[data-testid="nav-${office}"]`);
      
      // Verify navigation
      await expect(page).toHaveURL(`/dashboard/${office}`);
      
      // Verify page content is visible and readable on mobile
      await expect(page.locator('[data-testid="page-content"]')).toBeVisible();
    }
  });

  mobileTest('touch-based slider controls on investments page', async ({ page }) => {
    await navigateToOffice(page, 'investments');
    
    // Test touch interactions with investment sliders
    const assetClasses = ['stocks', 'bonds', 'real-estate', 'cash'];
    
    for (const assetClass of assetClasses) {
      const slider = page.locator(`[data-testid="slider-${assetClass}"]`);
      await expect(slider).toBeVisible();
      
      // Test touch drag (simulate touch interaction)
      const sliderBounds = await slider.boundingBox();
      if (sliderBounds) {
        // Touch at different positions to test responsiveness
        await page.touchscreen.tap(sliderBounds.x + sliderBounds.width * 0.25, sliderBounds.y + sliderBounds.height / 2);
        
        // Verify slider responded to touch
        const value = await slider.inputValue();
        expect(parseInt(value)).toBeGreaterThan(0);
      }
    }
    
    // Test save button is accessible on mobile
    const saveButton = page.locator('[data-testid="save-portfolio"]');
    await expect(saveButton).toBeVisible();
    await expect(saveButton).toBeEnabled();
  });

  mobileTest('decision forms are usable on mobile', async ({ page }) => {
    await navigateToOffice(page, 'products');
    
    // Test product creation form on mobile
    await page.click('[data-testid="create-product-button"]');
    
    const modal = page.locator('[data-testid="product-modal"]');
    await expect(modal).toBeVisible();
    
    // Verify form elements are properly sized for mobile
    const nameInput = modal.locator('[data-testid="product-name"]');
    const tierSelect = modal.locator('[data-testid="product-tier"]');
    const priceInput = modal.locator('[data-testid="base-price"]');
    
    await expect(nameInput).toBeVisible();
    await expect(tierSelect).toBeVisible();
    await expect(priceInput).toBeVisible();
    
    // Test form submission on mobile
    await nameInput.fill('Mobile Test Product');
    await tierSelect.selectOption('1');
    await priceInput.fill('1500');
    
    const saveButton = modal.locator('[data-testid="save-product"]');
    await expect(saveButton).toBeVisible();
    await saveButton.click();
    
    // Verify modal closes and product is created
    await expect(modal).not.toBeVisible();
    await expect(page.locator('[data-testid="product-list"]')).toContainText('Mobile Test Product');
  });

  mobileTest('financial reports readability on mobile', async ({ page }) => {
    await navigateToOffice(page, 'company');
    
    // Verify financial data is readable on mobile
    const financialSections = [
      '[data-testid="current-capital"]',
      '[data-testid="revenue-summary"]',
      '[data-testid="expense-summary"]'
    ];
    
    for (const section of financialSections) {
      const element = page.locator(section);
      if (await element.isVisible()) {
        // Check if text is not too small
        const fontSize = await element.evaluate(el => window.getComputedStyle(el).fontSize);
        const fontSizeValue = parseInt(fontSize);
        expect(fontSizeValue).toBeGreaterThanOrEqual(14); // Minimum readable font size
        
        // Check if element is not cut off
        const boundingBox = await element.boundingBox();
        expect(boundingBox?.width).toBeLessThanOrEqual(390); // iPhone 12 width
      }
    }
  });
});

test.describe('Mobile Landscape Mode', () => {
  landscapeTest('dashboard layout in landscape mode', async ({ page }) => {
    const testUser = generateTestUser('landscape');
    const testCompany = testCompanies.basic;
    
    await registerUser(page, testUser);
    await loginUser(page, testUser);
    await createCompany(page, testCompany);
    
    await page.goto('/dashboard');
    
    // Verify layout adapts to landscape orientation
    const dashboardGrid = page.locator('[data-testid="dashboard-grid"]');
    if (await dashboardGrid.isVisible()) {
      const gridStyle = await dashboardGrid.evaluate(el => window.getComputedStyle(el).gridTemplateColumns);
      // Should have more columns in landscape mode
      expect(gridStyle).not.toBe('1fr'); // Should not be single column
    }
    
    // Verify all office cards are visible
    const officeCards = page.locator('[data-testid^="office-card-"]');
    const cardCount = await officeCards.count();
    expect(cardCount).toBeGreaterThan(0);
    
    // All cards should be visible without scrolling horizontally
    for (let i = 0; i < cardCount; i++) {
      const card = officeCards.nth(i);
      await expect(card).toBeVisible();
      
      const boundingBox = await card.boundingBox();
      expect(boundingBox?.x).toBeGreaterThanOrEqual(0);
      expect(boundingBox?.x! + boundingBox?.width!).toBeLessThanOrEqual(844);
    }
  });
});

test.describe('Tablet Responsiveness', () => {
  tabletTest('tablet navigation and layout', async ({ page }) => {
    const testUser = generateTestUser('tablet');
    const testCompany = testCompanies.basic;
    
    await registerUser(page, testUser);
    await loginUser(page, testUser);
    await createCompany(page, testCompany);
    
    await page.goto('/dashboard');
    
    // Tablet should have different layout than mobile
    const navigation = page.locator('[data-testid="desktop-nav"]');
    
    // On tablet, desktop navigation should be visible (not hamburger menu)
    if (await navigation.isVisible()) {
      // Test direct navigation without menu toggle
      await page.click('[data-testid="nav-investments"]');
      await expect(page).toHaveURL('/dashboard/investments');
      
      // Verify investment sliders work well on tablet
      const slider = page.locator('[data-testid="slider-stocks"]');
      await expect(slider).toBeVisible();
      
      // Should have enough space for labels and controls
      const sliderContainer = page.locator('[data-testid="investment-sliders"]');
      const containerBox = await sliderContainer.boundingBox();
      expect(containerBox?.width).toBeGreaterThan(600); // Should have adequate width
    }
  });
});