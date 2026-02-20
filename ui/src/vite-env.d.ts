/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_APP_PROFILE?: "dev" | "stage" | "prod" | "production";
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_USE_MOCK?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

