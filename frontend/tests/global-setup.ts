import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  console.log('🚀 Global Setup: Starting Insurance Manager test environment...');
  
  // Wait for backend to be available
  const backendUrl = 'http://localhost:8000';
  let backendReady = false;
  let attempts = 0;
  const maxAttempts = 30; // 30 seconds
  
  while (!backendReady && attempts < maxAttempts) {
    try {
      const response = await fetch(`${backendUrl}/health`);
      if (response.ok) {
        backendReady = true;
        console.log('✅ Backend is ready');
      }
    } catch (error) {
      attempts++;
      if (attempts < maxAttempts) {
        console.log(`⏳ Waiting for backend... (attempt ${attempts}/${maxAttempts})`);
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    }
  }
  
  if (!backendReady) {
    console.warn('⚠️  Backend is not available - some tests may fail');
  }
  
  // Log test configuration
  console.log(`📊 Running tests with ${config.workers} worker(s)`);
  console.log(`🎯 Base URL: http://localhost:3000`);
  
  return {};
}

export default globalSetup;