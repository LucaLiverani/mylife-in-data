'use client';

import { useEffect, useState, useRef } from 'react';
import { Music, Pause, Play } from 'lucide-react';

interface SpotifyPlaybackData {
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
  duration_ms?: number;
  progress_ms?: number;
  is_playing: boolean;
  device?: {
    id: string;
    name: string;
    type: string;
    volume_percent: number;
  };
  context?: {
    type: string;
    uri: string;
  } | null;
}

const LAST_TRACK_KEY = 'spotify_last_track';

export function SpotifyLiveStream() {
  // Load last track from localStorage on mount
  const [currentTrack, setCurrentTrack] = useState<SpotifyPlaybackData | null>(null);
  const [lastValidTrack, setLastValidTrack] = useState<SpotifyPlaybackData | null>(() => {
    if (typeof window !== 'undefined') {
      try {
        const saved = localStorage.getItem(LAST_TRACK_KEY);
        return saved ? JSON.parse(saved) : null;
      } catch {
        return null;
      }
    }
    return null;
  });
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const retryCountRef = useRef(0); // Use ref to avoid stale closure issues
  const [simulatedProgress, setSimulatedProgress] = useState<number>(() => {
    // Initialize with saved track progress if available
    if (typeof window !== 'undefined') {
      try {
        const saved = localStorage.getItem(LAST_TRACK_KEY);
        if (saved) {
          const track = JSON.parse(saved);
          return track.progress_ms || 0;
        }
      } catch {
        // Ignore errors
      }
    }
    return 0;
  });
  const [receivedAt, setReceivedAt] = useState<number>(Date.now());
  // Always start with isPlaying false to avoid animating before first real update
  const [isPlaying, setIsPlaying] = useState<boolean>(false);

  useEffect(() => {
    let eventSource: EventSource | null = null;

    const connect = () => {
      try {
        eventSource = new EventSource('/api/spotify/stream');

        eventSource.onopen = () => {
          setIsConnected(true);
          setError(null);
          retryCountRef.current = 0;
          setRetryCount(0); // Reset retry count on successful connection
          console.log('Connected to Spotify stream');
        };

        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data) as SpotifyPlaybackData;

            // Ignore connection messages
            if (data.type === 'connected') {
              console.log('Received connection confirmation');
              return;
            }

            // Handle actual track data
            const trackData = data;
            setCurrentTrack(trackData);

            // Save as last valid track if it has track info
            if (trackData.track_id) {
              setLastValidTrack(trackData);
              // Persist to localStorage
              try {
                localStorage.setItem(LAST_TRACK_KEY, JSON.stringify(trackData));
              } catch (error) {
                console.error('Failed to save track to localStorage:', error);
              }
            }

            // Update playing state
            setIsPlaying(trackData.is_playing);

            // Only update receivedAt and progress when track is playing
            // This prevents the useEffect from re-triggering unnecessarily for paused tracks
            if (trackData.is_playing && trackData.progress_ms !== undefined) {
              setReceivedAt(Date.now());
              setSimulatedProgress(trackData.progress_ms);
            } else if (!trackData.is_playing && trackData.progress_ms !== undefined) {
              // For paused tracks, just update the progress without changing receivedAt
              setSimulatedProgress(trackData.progress_ms);
            }
          } catch (err) {
            console.error('Failed to parse message:', err);
          }
        };

        eventSource.onerror = (err) => {
          retryCountRef.current += 1;
          const currentRetries = retryCountRef.current;
          setRetryCount(currentRetries);
          setIsConnected(false);

          // Only log to console after multiple retries to reduce noise
          if (currentRetries > 2) {
            console.error(`EventSource error (attempt ${currentRetries}):`, err);
          }

          // Don't show error UI on first few attempts - these are normal during initial connection
          if (currentRetries <= 3) {
            // Still connecting, don't show error yet
            setError(null);
          } else {
            // Multiple failures, show error to user
            if (eventSource && eventSource.readyState === EventSource.CONNECTING) {
              setError('Having trouble connecting to live stream...');
            } else if (eventSource && eventSource.readyState === EventSource.CLOSED) {
              setError('Connection lost. Reconnecting...');
            } else {
              setError(`Connection error (attempt ${currentRetries}). Retrying...`);
            }
          }

          eventSource?.close();

          // Reconnect after 5 seconds (or 2 seconds for first few retries)
          const retryDelay = currentRetries <= 3 ? 2000 : 5000;
          setTimeout(connect, retryDelay);
        };
      } catch (err) {
        console.error('Failed to connect:', err);
        setError('Failed to connect to stream');
      }
    };

    connect();

    return () => {
      eventSource?.close();
    };
  }, []);

  // Simulate progress for playing tracks only
  useEffect(() => {
    // Only run interval if track is playing
    if (!isPlaying) {
      return;
    }

    // Determine which track to use for progress simulation
    const trackToSimulate = currentTrack?.track_id ? currentTrack : lastValidTrack;

    if (!trackToSimulate || !trackToSimulate.duration_ms) {
      return;
    }

    // Capture values for the interval closure
    const initialProgress = trackToSimulate.progress_ms || 0;
    const duration = trackToSimulate.duration_ms;
    const startTime = receivedAt;

    const interval = setInterval(() => {
      const elapsedSinceReceived = Date.now() - startTime;
      const newProgress = initialProgress + elapsedSinceReceived;

      // Don't exceed track duration
      if (newProgress < duration) {
        setSimulatedProgress(newProgress);
      } else {
        setSimulatedProgress(duration);
      }
    }, 100); // Update every 100ms for smooth progress

    return () => clearInterval(interval);
  }, [isPlaying, receivedAt]); // Simplified dependencies

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-6">
        <p className="text-red-400">{error}</p>
        {retryCount > 3 && (
          <p className="text-red-400/60 text-sm mt-2">
            Make sure the server is running and accessible.
          </p>
        )}
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className="bg-white/5 border border-white/10 rounded-lg p-6">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 bg-white/40 rounded-full animate-pulse" />
          <p className="text-white/60">
            {retryCount > 0 ? `Reconnecting... (attempt ${retryCount + 1})` : 'Connecting to live stream...'}
          </p>
        </div>
      </div>
    );
  }

  // Determine which track to display
  // If nothing is currently playing but we have a last valid track, show it as paused
  const displayTrack = (!currentTrack?.track_id && lastValidTrack)
    ? { ...lastValidTrack, is_playing: false }
    : currentTrack;

  if (!displayTrack || !displayTrack.track_id) {
    return (
      <div className="bg-white/5 border border-white/10 rounded-lg p-6">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 bg-white/10 rounded-lg flex items-center justify-center">
            <Music className="w-8 h-8 text-white/40" />
          </div>
          <div>
            <p className="text-white/60">No track currently playing</p>
            <p className="text-sm text-white/40 mt-1">
              Start playing something on Spotify!
            </p>
          </div>
        </div>
      </div>
    );
  }

  const albumImage = displayTrack.album?.images?.[0]?.url;
  const artistNames = displayTrack.artists?.map((a) => a.name).join(', ') || 'Unknown Artist';

  return (
    <div className={`bg-gradient-to-br rounded-lg p-6 backdrop-blur-sm transition-all duration-700 ${
      displayTrack.is_playing
        ? 'from-[#1DB954]/20 to-[#1DB954]/5 border border-[#1DB954]/30 opacity-100'
        : 'from-white/10 to-white/5 border border-white/20 opacity-85'
    }`}>
      <div className="flex items-center gap-2 mb-4">
        {displayTrack.is_playing ? (
          <>
            <div className="w-2 h-2 bg-[#1DB954] rounded-full animate-pulse" />
            <p className="text-sm text-[#1DB954] font-medium">LIVE NOW</p>
          </>
        ) : (
          <>
            <div className="w-2 h-2 bg-white/40 rounded-full" />
            <p className="text-sm text-white/60 font-medium">PAUSED</p>
          </>
        )}
      </div>

      <div className="flex items-start gap-6">
        {/* Album Art */}
        <div className="flex-shrink-0">
          {albumImage ? (
            <img
              src={albumImage}
              alt={displayTrack.album?.name || 'Album art'}
              className={`w-32 h-32 rounded-lg shadow-2xl transition-all duration-700 ${
                displayTrack.is_playing ? 'grayscale-0' : 'grayscale-[30%]'
              }`}
            />
          ) : (
            <div className="w-32 h-32 bg-white/10 rounded-lg flex items-center justify-center">
              <Music className="w-12 h-12 text-white/40" />
            </div>
          )}
        </div>

        {/* Track Info */}
        <div className="flex-grow min-w-0">
          <h3 className="text-2xl font-bold text-white mb-2 truncate">
            {displayTrack.track_name}
          </h3>
          <p className="text-lg text-white/70 mb-4 truncate">{artistNames}</p>

          <div className="space-y-2">
            <div className="flex items-center gap-3 text-sm text-white/60">
              {displayTrack.is_playing ? (
                <>
                  <Play className="w-4 h-4 text-[#1DB954]" />
                  <span>Playing</span>
                </>
              ) : (
                <>
                  <Pause className="w-4 h-4 text-white/40" />
                  <span>Paused</span>
                </>
              )}
            </div>

            {displayTrack.album?.name && (
              <p className="text-sm text-white/50">
                <span className="text-white/70">Album:</span> {displayTrack.album.name}
              </p>
            )}

            {displayTrack.device?.name && (
              <p className="text-sm text-white/50">
                <span className="text-white/70">Device:</span> {displayTrack.device.name} (
                {displayTrack.device.type})
              </p>
            )}

            {displayTrack.duration_ms && (
              <div className="mt-4">
                <div className="flex justify-between text-xs text-white/50 mb-1">
                  <span>{formatTime(simulatedProgress)}</span>
                  <span>{formatTime(displayTrack.duration_ms)}</span>
                </div>
                <div className="w-full bg-white/10 rounded-full h-1.5">
                  <div
                    className="bg-[#1DB954] h-1.5 rounded-full transition-all duration-100"
                    style={{
                      width: `${(simulatedProgress / displayTrack.duration_ms) * 100}%`,
                    }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function formatTime(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}
