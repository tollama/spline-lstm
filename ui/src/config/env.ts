export type AppProfile = "dev" | "stage" | "prod";

const PROFILE_API_FALLBACK: Record<AppProfile, string> = {
  dev: "http://localhost:8000",
  stage: "http://localhost:18000",
  prod: "/",
};

export function normalizeProfile(raw: string | undefined): AppProfile {
  if (raw === "stage") return "stage";
  if (raw === "prod" || raw === "production") return "prod";
  return "dev";
}

function sanitizeApiBase(value: string | undefined): string | null {
  const trimmed = value?.trim();
  if (!trimmed) return null;

  if (trimmed.startsWith("/")) return trimmed;

  try {
    const url = new URL(trimmed);
    return url.origin + url.pathname.replace(/\/$/, "");
  } catch {
    return null;
  }
}

export function resolveApiBase(params: {
  runtimeBase?: string;
  configuredBase?: string;
  profile: AppProfile;
  originFallback?: string;
}): string {
  const runtime = sanitizeApiBase(params.runtimeBase);
  if (runtime) return runtime;

  const configured = sanitizeApiBase(params.configuredBase);
  if (configured) return configured;

  const profileFallback = sanitizeApiBase(PROFILE_API_FALLBACK[params.profile]);
  if (profileFallback) return profileFallback;

  return params.originFallback ?? "/";
}

export const APP_PROFILE: AppProfile = normalizeProfile(import.meta.env.VITE_APP_PROFILE);

const configuredBase = import.meta.env.VITE_API_BASE_URL?.trim();
const runtimeBase =
  typeof window !== "undefined"
    ? ((window as any).__API_BASE_URL__ as string | undefined)
    : ((globalThis as any).__API_BASE_URL__ as string | undefined);
const originFallback = typeof window !== "undefined" ? window.location.origin : undefined;

export const API_BASE = resolveApiBase({
  runtimeBase,
  configuredBase,
  profile: APP_PROFILE,
  originFallback,
});

export const API_PREFIX = "/api/v1";

export const APP_ENV_INFO = `${APP_PROFILE}:${API_BASE}${API_PREFIX}`;
