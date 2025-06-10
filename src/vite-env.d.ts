/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_WS_URL: string
  // Add any other environment variables here
}

interface ImportMeta {
  readonly env: ImportMetaEnv
} 