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
 * sky position. Returns null on any failure (missing creds, rate limit, network
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
    // Call the backend API route using query parameters. Default zoom for star detail is 3.
    const url = `/api/sky-chart?ra=${encodeURIComponent(ra.toString())}&dec=${encodeURIComponent(dec.toString())}&zoom=3`;
    const response = await fetch(url, {
      method: 'GET',
      signal: AbortSignal.timeout(40_000), // 40-second timeout
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

// -------------------------------------------------------------------
// Map-background chart: keyed by "ra,dec,zoom" (separate from per-star cache)
// -------------------------------------------------------------------
const mapBgCache = new Map<string, string>();

/**
 * Fetches an AstronomyAPI star chart image for use as a sky map background.
 * ra/dec are decimal degrees; zoom is 1 (widest field) to 6 (most zoomed).
 * Returns null on any failure so callers can show an error state.
 */
export async function fetchMapChartImage(
  ra: number,
  dec: number,
  zoom: number = 1
): Promise<string | null> {
  const cacheKey = `map:${ra.toFixed(1)},${dec.toFixed(1)},${zoom}`;
  if (mapBgCache.has(cacheKey)) {
    return mapBgCache.get(cacheKey)!;
  }

  try {
    // Call the backend API route using query parameters.
    const url = `/api/sky-chart?ra=${encodeURIComponent(ra.toString())}&dec=${encodeURIComponent(dec.toString())}&zoom=${encodeURIComponent(zoom.toString())}`;
    const response = await fetch(url, {
      method: 'GET',
      signal: AbortSignal.timeout(40_000), // 40-second timeout
    });

    if (!response.ok) return null;
    const json = await response.json();

    if (json?.error) {
      console.warn('[astronomyApi] fetchMapChartImage error:', json.error, json.detail ?? '');
      return null;
    }

    if (json?.imageUrl) {
      mapBgCache.set(cacheKey, json.imageUrl);
      return json.imageUrl;
    }
    return null;
  } catch (err) {
    console.warn('[astronomyApi] fetchMapChartImage threw:', err);
    return null;
  }
}
