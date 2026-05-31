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

export const homeAPI = {
  getRecentEvents: () => fetchAPI('/api/home/recent-events'),
};

export const spotifyAPI = {
  getData: () => fetchAPI('/api/spotify/data'),
  getRecent: () => fetchAPI('/api/spotify/recent'),
  getSummary: () => fetchAPI('/api/spotify/summary'),
  getCurrent: () => fetchAPI('/api/spotify/current'),
};

export interface TripLabelBody {
  trip_key: string;
  label: 'confirm' | 'reject' | 'edit';
  edited_title?: string;
  edited_destination?: string;
  edited_trip_type?: string;
  note?: string;
}

export const travelAPI = {
  getData: () => fetchAPI('/api/travel/data'),
  /** Owner-only: write a confirm/reject/edit label. Throws on non-2xx. */
  postTripLabel: async (token: string, body: TripLabelBody) => {
    const response = await fetch('/api/travel/trip-label', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-trip-label-token': token },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error((data as { error?: string }).error || `HTTP ${response.status}`);
    }
    return data as { ok: boolean; trip_key: string; label: string };
  },
};

export const youtubeAPI = {
  getData: () => fetchAPI('/api/youtube/data'),
};

export const calendarAPI = {
  getData: () => fetchAPI('/api/google/calendar'),
};

export const systemAPI = {
  getHealth: () => fetchAPI('/api/system/health'),
};

export const nowAPI = {
  getTimeline: () => fetchAPI('/api/now/timeline'),
};
