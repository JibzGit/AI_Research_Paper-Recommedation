/**
 * VITE_API_BASE_URL is the only backend-related value the frontend reads.
 * It is a plain host URL, never a secret -- API keys, database credentials,
 * and other backend secrets must never be placed in frontend code or env
 * files, since anything under VITE_* is bundled into the client build and
 * shipped to the browser in plain text.
 */
const DEV_DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000'

function stripTrailingSlash(url: string): string {
  return url.endsWith('/') ? url.slice(0, -1) : url
}

function isHttpUrl(value: string): boolean {
  try {
    const parsed = new URL(value)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

function resolveApiBaseUrl(): string {
  const trimmed = import.meta.env.VITE_API_BASE_URL?.trim()

  if (!trimmed) {
    // Dev-only convenience default so `npm run dev` works without a local
    // .env file (see .env.example). Production builds must set it
    // explicitly -- silently shipping a build pointed at localhost would be
    // a confusing, hard-to-diagnose failure for anyone deploying it.
    if (import.meta.env.DEV) return DEV_DEFAULT_API_BASE_URL
    throw new Error(
      'Configuration error: VITE_API_BASE_URL is not set. Define it in frontend/.env before building (see frontend/.env.example).',
    )
  }

  if (!isHttpUrl(trimmed)) {
    throw new Error(`Configuration error: VITE_API_BASE_URL is not a valid http(s) URL: "${trimmed}"`)
  }

  return stripTrailingSlash(trimmed)
}

export const API_BASE_URL = resolveApiBaseUrl()
