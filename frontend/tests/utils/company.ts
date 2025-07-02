import { Page, expect } from '@playwright/test';

export interface TestCompany {
  name: string;
  academicBackground: {
    primary: string;
    secondary?: string;
  };
  almaMater: string;
  lineOfBusiness: string;
  ceoName: string;
}

export const testCompanies = {
  basic: {
    name: 'Test Insurance Corp',
    academicBackground: {
      primary: 'Risk Management and Insurance',
      secondary: 'Finance'
    },
    almaMater: 'University of Georgia',
    lineOfBusiness: 'Personal Auto',
    ceoName: 'Test CEO'
  },
  advanced: {
    name: 'Advanced Test Insurance',
    academicBackground: {
      primary: 'Risk Management and Insurance',
      secondary: 'Business Administration'
    },
    almaMater: 'Georgia State University',
    lineOfBusiness: 'Commercial Property',
    ceoName: 'Advanced CEO'
  }
};

/**
 * Create a new company through the company creation wizard
 */
export async function createCompany(page: Page, company: TestCompany) {
  await page.goto('/company/create');
  
  // Step 1: Academic Background
  await page.selectOption('[data-testid="primary-major"]', company.academicBackground.primary);
  if (company.academicBackground.secondary) {
    await page.selectOption('[data-testid="secondary-major"]', company.academicBackground.secondary);
  }
  await page.click('[data-testid="next-button"]');
  
  // Step 2: Alma Mater
  await page.selectOption('[data-testid="alma-mater"]', company.almaMater);
  await page.click('[data-testid="next-button"]');
  
  // Step 3: Company Details
  await page.fill('[data-testid="company-name"]', company.name);
  await page.selectOption('[data-testid="line-of-business"]', company.lineOfBusiness);
  await page.click('[data-testid="next-button"]');
  
  // Step 4: CEO Details
  await page.fill('[data-testid="ceo-name"]', company.ceoName);
  await page.click('[data-testid="create-company-button"]');
  
  // Wait for company creation to complete
  await expect(page).toHaveURL('/dashboard');
  
  // Verify company was created successfully
  await expect(page.locator('[data-testid="company-name"]')).toContainText(company.name);
}

/**
 * Navigate to a specific executive office
 */
export async function navigateToOffice(page: Page, office: string) {
  const officeMap: Record<string, string> = {
    'ceo': '/dashboard/ceo',
    'expansion': '/dashboard/expansion', 
    'products': '/dashboard/products',
    'employees': '/dashboard/employees',
    'investments': '/dashboard/investments',
    'company': '/dashboard/company',
    'decisions': '/dashboard/decisions'
  };
  
  const url = officeMap[office.toLowerCase()];
  if (!url) {
    throw new Error(`Unknown office: ${office}`);
  }
  
  await page.goto(url);
  await expect(page).toHaveURL(url);
}

/**
 * Submit turn decisions
 */
export async function submitTurnDecisions(page: Page) {
  await page.goto('/dashboard/decisions');
  
  // Verify we can see the decision summary
  await expect(page.locator('[data-testid="decisions-summary"]')).toBeVisible();
  
  // Submit decisions
  await page.click('[data-testid="submit-decisions-button"]');
  
  // Wait for confirmation
  await expect(page.locator('[data-testid="submission-success"]')).toBeVisible();
}

/**
 * Verify home state advantages are applied
 */
export async function verifyHomeStateAdvantages(page: Page, expectedState: string) {
  await page.goto('/dashboard/expansion');
  
  // Check that home state is highlighted/marked
  const homeStateElement = page.locator(`[data-testid="state-${expectedState}"]`);
  await expect(homeStateElement).toHaveClass(/home-state/);
  
  // Verify starting capital ($5M)
  await page.goto('/dashboard/company');
  const capitalElement = page.locator('[data-testid="current-capital"]');
  await expect(capitalElement).toContainText('$5,000,000');
}