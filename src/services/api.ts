const BASE_URL = import.meta.env.VITE_API_URL || 'https://atticus-demo.onrender.com';

// Add error handling for environment variables
if (!import.meta.env.VITE_API_URL) {
  console.warn('VITE_API_URL not set, using fallback URL');
} 