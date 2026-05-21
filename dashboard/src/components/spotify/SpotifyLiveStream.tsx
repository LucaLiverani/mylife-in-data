import { Music } from 'lucide-react';
import { useLiveSpotify } from '@/lib/useLiveSpotify';

export function SpotifyLiveStream() {
  const { data: currentTrack, lastValidTrack, isConnected, error } = useLiveSpotify();

  if (error) {
    return (
      <div role="alert" className="rounded-md border border-trace-down/30 bg-trace-down/10 p-5">
        <p className="font-mono text-sm text-trace-down">{error}</p>
        <p className="mt-1 font-mono text-xs text-trace-down/70">API unreachable.</p>
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className="rounded-md border border-signal-white/10 bg-rack-black/60 p-5">
        <div className="flex items-center gap-3">
          <span className="size-2 animate-pulse rounded-sm bg-signal-white/40" aria-hidden="true" />
          <p className="font-mono text-xs uppercase tracking-wider text-signal-white/60">Connecting…</p>
        </div>
      </div>
    );
  }

  const displayTrack =
    (!currentTrack?.track_id && lastValidTrack)
      ? { ...lastValidTrack, is_playing: false }
      : currentTrack;

  if (!displayTrack || !displayTrack.track_id) {
    return (
      <div className="rounded-md border border-signal-white/10 bg-rack-black/60 p-5">
        <div className="flex items-center gap-4">
          <div className="flex size-16 items-center justify-center rounded-sm bg-rack-charcoal">
            <Music className="size-7 text-signal-white/30" aria-hidden="true" />
          </div>
          <div>
            <p className="font-mono text-xs uppercase tracking-wider text-signal-white/60">The studio is quiet.</p>
            <p className="mt-1 text-sm text-signal-white/40">No signal on the listening channel right now.</p>
          </div>
        </div>
      </div>
    );
  }

  const albumImage = displayTrack.album?.images?.[0]?.url;
  const artistNames = displayTrack.artists?.map((a) => a.name).join(', ') || 'Unknown Artist';
  const playing = displayTrack.is_playing;

  return (
    <article
      role="status"
      aria-live="polite"
      aria-label={`Now ${playing ? 'playing' : 'paused'}: ${displayTrack.track_name} by ${artistNames}`}
      className={
        'overflow-hidden rounded-md border transition-colors duration-300 ease-snap ' +
        (playing
          ? 'border-channel-green/40 bg-gradient-to-br from-channel-green/30 to-channel-green/5'
          : 'border-signal-white/10 bg-rack-black/60')
      }
    >
      <header className="flex items-center gap-2 border-b border-signal-white/5 px-5 py-3">
        {playing ? (
          <>
            <span className="size-2 animate-pulse rounded-sm bg-channel-green" aria-hidden="true" />
            <p className="font-mono text-xs font-medium uppercase tracking-widest text-channel-green">
              Live now
            </p>
          </>
        ) : (
          <>
            <span className="size-2 rounded-sm bg-signal-white/40" aria-hidden="true" />
            <p className="font-mono text-xs font-medium uppercase tracking-widest text-signal-white/60">
              Paused
            </p>
          </>
        )}
      </header>

      <div className="flex flex-col gap-5 p-5 sm:flex-row sm:items-start sm:gap-6">
        <div className="flex-shrink-0 self-center sm:self-start">
          {albumImage ? (
            <img
              src={albumImage}
              alt={displayTrack.album?.name ? `Album art for ${displayTrack.album.name}` : 'Album art'}
              loading="lazy"
              decoding="async"
              className={
                'size-24 rounded-sm transition-all duration-300 ease-snap sm:size-32 ' +
                (playing ? 'grayscale-0' : 'grayscale-[30%]')
              }
            />
          ) : (
            <div className="flex size-24 items-center justify-center rounded-sm bg-rack-charcoal sm:size-32">
              <Music className="size-10 text-signal-white/30" aria-hidden="true" />
            </div>
          )}
        </div>

        <div className="min-w-0 flex-grow">
          <h3 className="mb-1 truncate text-xl font-bold sm:text-2xl">{displayTrack.track_name}</h3>
          <p className="mb-4 truncate text-base text-signal-white/70">{artistNames}</p>

          <dl className="space-y-1 font-mono text-xs text-signal-white/60">
            {displayTrack.album?.name && (
              <div className="flex gap-2">
                <dt className="uppercase tracking-wider text-signal-white/40">Album</dt>
                <dd className="truncate text-signal-white/80">{displayTrack.album.name}</dd>
              </div>
            )}
            {displayTrack.device?.name && (
              <div className="flex gap-2">
                <dt className="uppercase tracking-wider text-signal-white/40">Device</dt>
                <dd className="truncate text-signal-white/80">
                  {displayTrack.device.name} <span className="text-signal-white/50">({displayTrack.device.type})</span>
                </dd>
              </div>
            )}
          </dl>
        </div>
      </div>
    </article>
  );
}
