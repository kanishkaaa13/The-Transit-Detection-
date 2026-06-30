const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || '';

export function apiPath(path: string): string {
  return API_BASE_URL ? `${API_BASE_URL}${path}` : path;
}
