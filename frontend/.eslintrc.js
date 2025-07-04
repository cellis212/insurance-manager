module.exports = {
  extends: ['next/core-web-vitals', 'prettier'],
  rules: {
    // Add any custom rules here
    'react/prop-types': 'off', // We use TypeScript for prop validation
    // Removed problematic TypeScript rule that was causing conflicts
  },
}; 