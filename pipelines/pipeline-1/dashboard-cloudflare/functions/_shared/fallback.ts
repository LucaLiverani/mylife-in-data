/**
 * Fallback data helper
 * Returns static cached data when ClickHouse is unavailable
 */

/**
 * Fetch fallback data from static files
 */
export async function getFallbackData<T>(endpoint: string): Promise<T[]> {
  try {
    // Fetch from static fallback files deployed with the site
    const response = await fetch(`/fallback-data/${endpoint}.json`);

    if (!response.ok) {
      console.warn(`Fallback data not found for ${endpoint}`);
      return [];
    }

    const text = await response.text();

    // Parse JSONEachRow format (newline-delimited JSON)
    if (!text.trim()) {
      return [];
    }

    const data = text
      .trim()
      .split('\n')
      .filter(Boolean)
      .map(line => JSON.parse(line));

    return data as T[];
  } catch (error) {
    console.error(`Error loading fallback data for ${endpoint}:`, error);
    return [];
  }
}

/**
 * Query ClickHouse with automatic fallback to static data
 *
 * @param queryFn - Function that performs the ClickHouse query
 * @param fallbackEndpoint - Name of the fallback file (without .json)
 * @param defaultFallback - Optional default data if fallback file also fails
 * @returns Object with data, isFromCache flag, and optional error
 */
export async function queryWithFallback<T>(
  queryFn: () => Promise<T>,
  fallbackEndpoint: string,
  defaultFallback?: T
): Promise<{ data: T; isFromCache: boolean; error?: string }> {
  try {
    // Try ClickHouse first
    const data = await queryFn();
    return { data, isFromCache: false };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.warn(`ClickHouse query failed: ${errorMessage}`);
    console.log(`Attempting to use fallback data: ${fallbackEndpoint}`);

    try {
      // Try static fallback files
      const cachedData = await getFallbackData<any>(fallbackEndpoint);

      if (cachedData && (Array.isArray(cachedData) ? cachedData.length > 0 : cachedData)) {
        console.log(`✅ Using fallback data for ${fallbackEndpoint}`);
        return {
          data: cachedData as T,
          isFromCache: true,
          error: errorMessage,
        };
      }
    } catch (fallbackError) {
      console.error(`Failed to load fallback data: ${fallbackError}`);
    }

    // Last resort: use provided default fallback data
    if (defaultFallback !== undefined) {
      console.log(`Using default fallback data for ${fallbackEndpoint}`);
      return {
        data: defaultFallback,
        isFromCache: true,
        error: errorMessage,
      };
    }

    // If everything fails, throw the original error
    throw error;
  }
}

/**
 * Add cache metadata to response
 */
export function addCacheHeaders(
  data: any,
  isFromCache: boolean,
  error?: string
): { body: any; headers: Record<string, string> } {
  const body = {
    ...data,
    _meta: {
      cached: isFromCache,
      timestamp: new Date().toISOString(),
      ...(error && { error: 'ClickHouse unavailable, using cached data' }),
    },
  };

  const headers = {
    'Cache-Control': isFromCache ? 'public, max-age=300' : 'public, max-age=60',
    'X-Data-Source': isFromCache ? 'cache' : 'live',
    ...(error && { 'X-Error': error }),
  };

  return { body, headers };
}
