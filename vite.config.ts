import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  define: {
    // Force environment variables to be replaced at build time
    'import.meta.env.VITE_API_URL': JSON.stringify('https://atticus-demo.onrender.com'),
    'import.meta.env.VITE_WS_URL': JSON.stringify('wss://atticus-demo.onrender.com'),
  },
  build: {
    // Force source maps for debugging
    sourcemap: true,
    // Ensure clean builds
    emptyOutDir: true,
    // Disable minification for debugging
    minify: false
  },
}); 