const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || '';

// Map of API paths → static pre-built JSON (used when no backend is configured)
const STATIC_OVERRIDES: Record<string, string> = {
  '/api/tic-ids':       '/data/tic-ids.json',
  '/api/sky-map-stars': '/data/sky-map-stars.json',
};

export function apiPath(path: string): string {
  if (API_BASE_URL) return `${API_BASE_URL}${path}`;
  // On Vercel static hosting, redirect API calls to pre-built JSON files
  return STATIC_OVERRIDES[path] ?? path;
}
