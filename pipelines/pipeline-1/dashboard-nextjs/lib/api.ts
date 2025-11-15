/**
 * API client for fetching data from Next.js API routes
 * These routes query ClickHouse directly (no FastAPI needed)
 */

export async function fetchAPI<T>(endpoint: string): Promise<T> {
  const response = await fetch(endpoint, {
    next: { revalidate: 60 }, // Revalidate every minute
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.statusText}`);
  }

  return response.json();
}

// Spotify API
export const spotifyAPI = {
  getSummary: () => fetchAPI('/api/spotify/summary'),
  getData: () => fetchAPI('/api/spotify/data'),
  getRecent: () => fetchAPI('/api/spotify/recent'),
};

// Travel API
export const travelAPI = {
  getData: () => fetchAPI('/api/travel/data'),
};

// Overview API
export const overviewAPI = {
  getStats: () => fetchAPI('/api/overview/stats'),
};
