/**
 * Fallback data helper
 *
 * Returns the mock JSON for a given endpoint when ClickHouse is unavailable.
 * The same `public/mocks/<path>.json` files power both:
 *   - the Vite dev plugin (`vite-plugins/mock-api.ts`) so `npm run dev` works
 *     without ClickHouse, and
 *   - the production fallback path when the Workers Function can't reach CH.
 *
 * Mocks are full API-response objects (not JSONEachRow rows), so the response
 * shape is already correct — callers just return it as-is.
 *
 * Workers `fetch` requires absolute URLs; we rebuild the URL against the
 * incoming request's origin so the fetch loops back through the Pages router
 * and hits the static asset.
 */

/**
 * Fetch the mock for an endpoint. `endpoint` is the API path without the
 * `/api/` prefix or `.json` suffix, e.g. `'spotify/summary'`.
 */
export async function getFallbackData<T>(endpoint: string, request: Request): Promise<T | null> {
  try {
    const url = new URL(`/mocks/${endpoint}.json`, request.url);
    const response = await fetch(url.toString());

    if (!response.ok) {
      console.warn(`Mock data not found for ${endpoint} (HTTP ${response.status})`);
      return null;
    }

    return (await response.json()) as T;
  } catch (error) {
    console.error(`Error loading mock data for ${endpoint}:`, error);
    return null;
  }
}

/**
 * Query ClickHouse with automatic fallback to the matching mock.
 *
 * @param queryFn - Function that performs the ClickHouse query and returns
 *                  the final API response object (post-transformation).
 * @param fallbackEndpoint - API path without /api/ prefix, e.g. 'spotify/summary'.
 *                           Used to look up `public/mocks/<path>.json`.
 * @param request - The incoming Request (needed to resolve the absolute URL).
 * @param defaultFallback - Last-resort value if even the mock fails to load.
 */
export async function queryWithFallback<T>(
  queryFn: () => Promise<T>,
  fallbackEndpoint: string,
  request: Request,
  defaultFallback?: T
): Promise<{ data: T; isFromCache: boolean; error?: string }> {
  try {
    const data = await queryFn();
    return { data, isFromCache: false };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.warn(`ClickHouse query failed (${fallbackEndpoint}): ${errorMessage}`);

    const cached = await getFallbackData<T>(fallbackEndpoint, request);
    if (cached !== null) {
      return { data: cached, isFromCache: true, error: errorMessage };
    }

    if (defaultFallback !== undefined) {
      return { data: defaultFallback, isFromCache: true, error: errorMessage };
    }

    throw error;
  }
}

/**
 * Add cache metadata + cache-control headers to a response.
 *
 * For object responses, `_meta` is spread inline (the frontend reads it to
 * show a "cached" badge). For array responses, `_meta` would break the
 * contract — callers rely on `X-Data-Source: cache|live` header instead.
 */
export function addCacheHeaders(
  data: any,
  isFromCache: boolean,
  error?: string,
  cacheControl?: string
): { body: any; headers: Record<string, string> } {
  const body = Array.isArray(data)
    ? data
    : {
        ...data,
        _meta: {
          cached: isFromCache,
          timestamp: new Date().toISOString(),
          ...(error && { error: 'ClickHouse unavailable, using cached data' }),
        },
      };

  const headers = {
    'Cache-Control': cacheControl ?? (isFromCache ? 'public, max-age=300' : 'public, max-age=60'),
    'X-Data-Source': isFromCache ? 'cache' : 'live',
    ...(error && { 'X-Error': error }),
  };

  return { body, headers };
}
