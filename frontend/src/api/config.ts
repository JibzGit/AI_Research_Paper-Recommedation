/**
 * VITE_API_BASE_URL is the only backend-related value the frontend reads.
 * It is a plain host URL, never a secret -- API keys, database credentials,
 * and other backend secrets must never be placed in frontend code or env
 * files, since anything under VITE_* is bundled into the client build and
 * shipped to the browser in plain text.
 */
const RAW_API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

function stripTrailingSlash(url: string): string {
  return url.endsWith('/') ? url.slice(0, -1) : url
}

export const API_BASE_URL = stripTrailingSlash(RAW_API_BASE_URL.trim())
