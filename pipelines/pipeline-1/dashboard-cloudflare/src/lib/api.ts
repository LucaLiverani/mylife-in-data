/**
 * Client-side API utilities
 * Wrapper functions for calling Cloudflare Workers Functions
 */

async function fetchAPI<T>(endpoint: string): Promise<T> {
  const response = await fetch(endpoint);

  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
  }

  return response.json();
}

export const overviewAPI = {
  getStats: () => fetchAPI('/api/overview/stats'),
};

export const spotifyAPI = {
  getData: () => fetchAPI('/api/spotify/data'),
  getRecent: () => fetchAPI('/api/spotify/recent'),
  getSummary: () => fetchAPI('/api/spotify/summary'),
  getCurrent: () => fetchAPI('/api/spotify/current'),
};

export const travelAPI = {
  getData: () => fetchAPI('/api/travel/data'),
};

export const youtubeAPI = {
  getData: () => fetchAPI('/api/youtube/data'),
};
