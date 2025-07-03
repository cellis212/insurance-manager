import { FullConfig } from '@playwright/test';

async function globalTeardown(config: FullConfig) {
  console.log('🧹 Global Teardown: Cleaning up Insurance Manager test environment...');
  
  // Any cleanup tasks can go here
  // For now, just log completion
  console.log('✅ Test environment cleanup completed');
}

export default globalTeardown;