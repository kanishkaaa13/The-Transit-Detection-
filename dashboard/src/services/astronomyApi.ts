/**
 * astronomyApi.ts
 * Client-side service for fetching AstronomyAPI star-chart snapshots.
 *
 * All calls go through the /api/sky-snapshot Vite dev-server proxy so that
 * the Application Secret never appears in browser network traffic.
 */

// In-memory cache keyed by TIC ID — survives React re-renders within a session
const chartCache = new Map<string, string>();

/**
 * Returns a URL to the AstronomyAPI-generated star chart image for the given
 * sky position.  Returns null on any failure (missing creds, rate limit, network
 * error, etc.) so callers can fall back gracefully.
 */
export async function fetchStarChartImage(
  ticId: string,
  ra: number,
  dec: number
): Promise<string | null> {
  // Cache hit
  if (chartCache.has(ticId)) {
    return chartCache.get(ticId)!;
  }

  try {
    const response = await fetch('/api/sky-snapshot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticId, ra, dec }),
      signal: AbortSignal.timeout(15_000), // 15-second hard timeout
    });

    if (!response.ok) return null;

    const json = await response.json();

    if (json?.imageUrl) {
      chartCache.set(ticId, json.imageUrl);
      return json.imageUrl;
    }

    // Treat missing credentials as a quiet non-error
    if (json?.error === 'credentials_not_configured') return null;

    return null;
  } catch {
    return null;
  }
}

/**
 * Resolves RA/Dec for a given TIC ID by querying the existing catalog endpoint.
 * Returns null if the star is not found.
 */
let _starsCache: { id: string; ra: number; dec: number }[] | null = null;

export async function resolveStarCoords(
  ticId: string
): Promise<{ ra: number; dec: number } | null> {
  try {
    if (!_starsCache) {
      const res = await fetch('/api/sky-map-stars');
      if (!res.ok) return null;
      _starsCache = await res.json();
    }
    const star = (_starsCache ?? []).find((s) => s.id === ticId);
    return star ? { ra: star.ra, dec: star.dec } : null;
  } catch {
    return null;
  }
}
