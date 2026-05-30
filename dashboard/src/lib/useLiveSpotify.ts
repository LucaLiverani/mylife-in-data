import { useEffect, useRef, useState } from 'react';

export interface SpotifyPlaybackData {
  timestamp: string;
  track_id: string | null;
  track_name?: string;
  track_uri?: string;
  artists?: Array<{ id: string; name: string; uri: string }>;
  album?: {
    id: string;
    name: string;
    uri: string;
    images: Array<{ url: string; height: number; width: number }>;
  };
  is_playing: boolean;
  device?: { id: string; name: string; type: string; volume_percent: number };
  context?: { type: string; uri: string } | null;
}

interface LiveSpotifyState {
  /** Most recent playback object the poller has seen. */
  data: SpotifyPlaybackData | null;
  /** Cached "last known good" track (survives tab close via localStorage). */
  lastValidTrack: SpotifyPlaybackData | null;
  /** True when the poll has succeeded at least once recently. */
  isConnected: boolean;
  /** True when `data?.is_playing` is currently true. */
  isPlaying: boolean;
  /** Error message from the most recent failed poll, if any. */
  error: string | null;
}

// v2: invalidate any previously-cached track. Earlier builds could persist the
// mock "now playing" track (served when the live query failed) to localStorage,
// where it stuck as a fake current track. Bumping the key drops that stale cache.
const LAST_TRACK_KEY = 'spotify_last_track_v2';
const POLL_WHEN_PLAYING_MS = 5_000;
const POLL_WHEN_IDLE_MS = 30_000;

/**
 * Polls `/api/spotify/current` for live playback state.
 * - 5s cadence while playing, 30s while idle / paused
 * - Pauses entirely when the tab is hidden (Page Visibility API)
 * - Falls back to localStorage when the network is unavailable
 *
 * Shared between `SpotifyLiveStream` (full hero card) and `ChannelStrip`
 * (the compact Home tile).
 */
export function useLiveSpotify(): LiveSpotifyState {
  const [data, setData] = useState<SpotifyPlaybackData | null>(null);
  const [lastValidTrack, setLastValidTrack] = useState<SpotifyPlaybackData | null>(() => {
    if (typeof window === 'undefined') return null;
    try {
      const saved = localStorage.getItem(LAST_TRACK_KEY);
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isPlayingRef = useRef(false);

  useEffect(() => {
    let isActive = true;
    let timeoutId: number | undefined;

    const poll = async () => {
      if (!isActive) return;
      if (typeof document !== 'undefined' && document.hidden) {
        timeoutId = window.setTimeout(poll, POLL_WHEN_IDLE_MS);
        return;
      }

      try {
        const response = await fetch('/api/spotify/current');
        if (!response.ok) throw new Error('Failed to fetch current track');
        const body = (await response.json()) as
          | { type: 'current_track'; data: SpotifyPlaybackData }
          | { type: 'no_track'; data: Partial<SpotifyPlaybackData> };
        if (!isActive) return;

        if (body.type === 'current_track') {
          const trackData = body.data;
          setData(trackData);
          setIsConnected(true);
          setError(null);
          isPlayingRef.current = trackData.is_playing;
          if (trackData.track_id) {
            setLastValidTrack(trackData);
            try { localStorage.setItem(LAST_TRACK_KEY, JSON.stringify(trackData)); }
            catch (err) { console.error('Failed to save track to localStorage:', err); }
          }
        } else if (body.type === 'no_track') {
          setData({ ...(body.data as SpotifyPlaybackData), track_id: null });
          setIsConnected(true);
          isPlayingRef.current = false;
        }
      } catch (err) {
        if (!isActive) return;
        console.error('Spotify polling error:', err);
        setError('Failed to fetch current track');
        setIsConnected(false);
      }

      if (isActive) {
        const next = isPlayingRef.current ? POLL_WHEN_PLAYING_MS : POLL_WHEN_IDLE_MS;
        timeoutId = window.setTimeout(poll, next);
      }
    };

    const onVisibilityChange = () => {
      if (!document.hidden && isActive) {
        if (timeoutId) clearTimeout(timeoutId);
        poll();
      }
    };

    poll();
    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      isActive = false;
      if (timeoutId) clearTimeout(timeoutId);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, []);

  return {
    data,
    lastValidTrack,
    isConnected,
    isPlaying: Boolean(data?.is_playing),
    error,
  };
}
