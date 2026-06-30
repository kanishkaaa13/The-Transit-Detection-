/**
 * Service to fetch real sky images from NASA's SkyView Virtual Observatory CGI.
 * Caches responses client-side and implements a timeout abort sequence.
 */

// Memory cache to prevent duplicate fetches for the same region and FOV
const imageCache = new Map<string, string>();

interface FetchSkyMapOptions {
  ra: number;
  dec: number;
  fov: number; // in degrees
  apiKey?: string; // Optional user NASA API key
}

/**
 * Queries NASA's SkyView CGI service and returns a local object URL of the JPEG image.
 * Falls back to null if the request fails, times out, or exceeds reasonable FOV limits.
 */
export async function fetchSkyMapImage({ ra, dec, fov, apiKey }: FetchSkyMapOptions): Promise<string | null> {
  // Capping FOV: SkyView struggles with massive fields of view.
  // Capping at 15 degrees prevents massive timeouts and triggers offline synthetic background.
  if (fov > 15 || fov <= 0) {
    return null;
  }

  // Generate a rounded cache key
  const cacheKey = `${ra.toFixed(3)},${dec.toFixed(3)},${fov.toFixed(3)},${apiKey || ''}`;
  if (imageCache.has(cacheKey)) {
    return imageCache.get(cacheKey)!;
  }

  // Build the SkyView CGI request URL
  // Uses Digitized Sky Survey (dss) survey and Tan (Tangent/Gnomonic) projection for grid alignment.
  let url = `https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?position=${ra.toFixed(5)}%2C${dec.toFixed(5)}&survey=dss&pixels=600%2C600&size=${fov.toFixed(4)}%2C${fov.toFixed(4)}&projection=Tan&coordinates=J2000.0&nofits=1&quicklook=jpeg&return=jpeg`;

  // If a NASA API key is provided, we append it to the request query parameters.
  // SkyView ignoring it does not impact retrieval, but it validates key wiring.
  if (apiKey) {
    url += `&api_key=${encodeURIComponent(apiKey)}`;
  }

  // Set up AbortController for a 5-second request timeout
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5000);

  try {
    const response = await fetch(url, { signal: controller.signal });
    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error(`NASA API HTTP error: ${response.status}`);
    }

    // Double-check the content-type is indeed an image/jpeg
    const contentType = response.headers.get('content-type');
    if (!contentType || !contentType.includes('image')) {
      throw new Error("Invalid response content type received from SkyView");
    }

    // Convert response to Blob and create a local object URL
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);

    // Save to cache
    imageCache.set(cacheKey, objectUrl);
    return objectUrl;
  } catch (err: any) {
    clearTimeout(timeoutId);
    console.warn(`[nasaSkyView] Failed to fetch SkyView image: ${err.message || err}`);
    return null; // Triggers fallback to synthetic background
  }
}
