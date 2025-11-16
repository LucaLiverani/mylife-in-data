import { useEffect, useState } from 'react';
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
const POLL_INTERVAL = 5000; // Poll every 5 seconds

export function SpotifyLiveStream() {
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
  const [simulatedProgress, setSimulatedProgress] = useState<number>(0);
  const [receivedAt, setReceivedAt] = useState<number>(Date.now());
  const [isPlaying, setIsPlaying] = useState<boolean>(false);

  // Polling effect
  useEffect(() => {
    let isActive = true;
    let timeoutId: number;

    const poll = async () => {
      if (!isActive) return;

      try {
        const response = await fetch('/api/spotify/current');

        if (!response.ok) {
          throw new Error('Failed to fetch current track');
        }

        const data = await response.json();

        if (!isActive) return;

        // Handle the response
        if (data.type === 'current_track') {
          const trackData = data.data as SpotifyPlaybackData;
          setCurrentTrack(trackData);
          setIsConnected(true);
          setError(null);

          // Save as last valid track if it has track info
          if (trackData.track_id) {
            setLastValidTrack(trackData);
            try {
              localStorage.setItem(LAST_TRACK_KEY, JSON.stringify(trackData));
            } catch (error) {
              console.error('Failed to save track to localStorage:', error);
            }
          }

          // Update playing state
          setIsPlaying(trackData.is_playing);

          // Update progress
          if (trackData.is_playing && trackData.progress_ms !== undefined) {
            setReceivedAt(Date.now());
            setSimulatedProgress(trackData.progress_ms);
          } else if (!trackData.is_playing && trackData.progress_ms !== undefined) {
            setSimulatedProgress(trackData.progress_ms);
          }
        } else if (data.type === 'no_track') {
          setIsConnected(true);
          setCurrentTrack({ ...data.data, track_id: null });
          setIsPlaying(false);
        }
      } catch (err) {
        if (!isActive) return;
        console.error('Polling error:', err);
        setError('Failed to fetch current track');
        setIsConnected(false);
      }

      // Schedule next poll
      if (isActive) {
        timeoutId = window.setTimeout(poll, POLL_INTERVAL);
      }
    };

    // Initial poll
    poll();

    return () => {
      isActive = false;
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, []);

  // Simulate progress for playing tracks
  useEffect(() => {
    if (!isPlaying) {
      return;
    }

    const trackToSimulate = currentTrack?.track_id ? currentTrack : lastValidTrack;

    if (!trackToSimulate || !trackToSimulate.duration_ms) {
      return;
    }

    const initialProgress = trackToSimulate.progress_ms || 0;
    const duration = trackToSimulate.duration_ms;
    const startTime = receivedAt;

    const interval = setInterval(() => {
      const elapsedSinceReceived = Date.now() - startTime;
      const newProgress = initialProgress + elapsedSinceReceived;

      if (newProgress < duration) {
        setSimulatedProgress(newProgress);
      } else {
        setSimulatedProgress(duration);
      }
    }, 100);

    return () => clearInterval(interval);
  }, [isPlaying, receivedAt, currentTrack, lastValidTrack]);

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-6">
        <p className="text-red-400">{error}</p>
        <p className="text-red-400/60 text-sm mt-2">
          Make sure the API is accessible.
        </p>
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className="bg-white/5 border border-white/10 rounded-lg p-6">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 bg-white/40 rounded-full animate-pulse" />
          <p className="text-white/60">Loading current track...</p>
        </div>
      </div>
    );
  }

  // Determine which track to display
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
