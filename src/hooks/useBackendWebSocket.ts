const WEBSOCKET_URL = import.meta.env.VITE_WS_URL || 'wss://atticus-demo.onrender.com/ws';

// Add error handling for environment variables
if (!import.meta.env.VITE_WS_URL) {
  console.warn('VITE_WS_URL not set, using fallback URL');
} 