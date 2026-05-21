import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { CHANNEL_CLASS } from '@/lib/channels';
import { useLiveTimeline, type TimelineEvent } from '@/lib/useLiveTimeline';
import { cn } from '@/lib/utils';

interface LiveConsoleProps {
  /** Max events to render. Default 6. */
  limit?: number;
  /** Polling cadence in ms. Default 15000. */
  refreshMs?: number;
}

/**
 * Compact live-event feed for Home. Renders the most recent N events from
 * `/api/now/timeline`, with a header LED that pulses when a sync just landed.
 * Links through to /now for the full stream.
 *
 * Stylistically a compressed cousin of pages/Now.tsx — one rail, one row per
 * event, no per-second "Xs ago" ticker. The full page handles the deep view.
 */
export function LiveConsole({ limit = 6, refreshMs = 15_000 }: LiveConsoleProps) {
  const { events, lastSync, loading, error, tick } = useLiveTimeline(refreshMs);
  void tick; // re-render trigger for "Last sync"

  const items = events.slice(0, limit);
  const lastSyncAgo = lastSync ? Math.floor((Date.now() - lastSync.getTime()) / 1000) : null;
  const fresh = lastSyncAgo !== null && lastSyncAgo < refreshMs / 1000 + 2;

  return (
    <Link
      to="/now"
      aria-label="Open the live timeline"
      className="group block rounded-md border border-signal-white/10 bg-rack-black/60 p-6 transition-shadow duration-200 ease-snap hover:shadow-lift hover:border-signal-white/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal-white"
    >
      <header className="mb-5 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span
            className={cn(
              'block size-2 rounded-sm',
              fresh ? 'bg-trace-up animate-pulse' : 'bg-signal-white/30',
            )}
            aria-hidden="true"
          />
          <h2 className="font-mono text-xs uppercase tracking-wider text-signal-white/80">
            Live console
          </h2>
          <span className="font-mono text-[10px] uppercase tracking-widest text-signal-white/40">
            {error
              ? 'No signal'
              : loading
                ? 'Connecting…'
                : `Last sync ${lastSyncAgo === null ? '—' : `${lastSyncAgo}s`} ago`}
          </span>
        </div>
        <span className="hidden items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-signal-white/40 group-hover:text-signal-white/70 sm:flex">
          Full timeline
          <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
        </span>
      </header>

      {error && items.length === 0 ? (
        <p className="font-mono text-sm uppercase tracking-wider text-trace-down/80">{error}</p>
      ) : items.length === 0 && !loading ? (
        <p className="font-mono text-sm uppercase tracking-wider text-signal-white/60">
          The console is silent.
        </p>
      ) : (
        <ol className="relative">
          <span aria-hidden="true" className="absolute left-[7px] top-3 bottom-3 w-px bg-signal-white/10" />
          {items.map((e, i) => (
            <CompactTimelineRow key={`${e.time}-${i}`} event={e} />
          ))}
        </ol>
      )}
    </Link>
  );
}

function CompactTimelineRow({ event }: { event: TimelineEvent }) {
  const dotClass = CHANNEL_CLASS.bg[event.channel];
  const channelText = CHANNEL_CLASS.text[event.channel];
  const localTime = new Date(event.time).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
  return (
    <li className="relative flex items-start gap-4 py-3">
      <span
        className={cn('relative z-10 mt-1.5 block size-3.5 shrink-0 rounded-sm border-2 border-rack-black', dotClass)}
        aria-hidden="true"
      />
      <time
        dateTime={event.time}
        className="mt-0.5 w-12 shrink-0 font-mono text-[10px] uppercase tracking-widest tabular-nums text-signal-white/50"
      >
        {localTime}
      </time>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm text-signal-white/90">
          <span className={cn('mr-2 font-mono text-[10px] uppercase tracking-widest', channelText)}>{event.channel}</span>
          <span className="text-signal-white/60">{event.label}:</span>{' '}
          <span className="font-medium text-signal-white">{event.value}</span>
        </p>
      </div>
    </li>
  );
}
