const BASE_URL = import.meta.env.VITE_API_URL || 'https://atticus-demo.onrender.com';

// Debug logging
console.log('API URL:', BASE_URL);
console.log('Environment Variables:', {
  VITE_API_URL: import.meta.env.VITE_API_URL,
  VITE_WS_URL: import.meta.env.VITE_WS_URL
});

// Add error handling for environment variables
if (!import.meta.env.VITE_API_URL) {
  console.warn('VITE_API_URL not set, using fallback URL:', BASE_URL);
}

// Add connection status monitoring
let isConnected = false;
let lastError = null;

export const getConnectionStatus = () => ({
  isConnected,
  lastError,
  baseUrl: BASE_URL
}); 