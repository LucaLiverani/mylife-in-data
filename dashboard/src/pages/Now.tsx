import { useEffect, useState } from 'react';
import { FadeIn } from '@/components/animations/FadeIn';
import { nowAPI } from '@/lib/api';
import { CHANNEL_CLASS, type Channel } from '@/lib/channels';
import { cn } from '@/lib/utils';

interface TimelineEvent {
  time: string;          // ISO
  channel: Channel;
  label: string;         // e.g. "Track started"
  value: string;         // e.g. "Strobe — Deadmau5"
  href?: string;
}

interface NowTimeline {
  generatedAt: string;
  windowMinutes: number;
  events: TimelineEvent[];
}

const REFRESH_MS = 15_000;

export default function NowPage() {
  const [data, setData] = useState<NowTimeline | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastSync, setLastSync] = useState<Date | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let active = true;
    const fetch = async () => {
      try {
        const result = (await nowAPI.getTimeline()) as NowTimeline;
        if (!active) return;
        setData(result);
        setLastSync(new Date());
      } catch {
        if (active) setLastSync(new Date());
      } finally {
        if (active) setLoading(false);
      }
    };
    fetch();
    const id = window.setInterval(fetch, REFRESH_MS);
    return () => { active = false; window.clearInterval(id); };
  }, []);

  // 1Hz tick so the "Last sync Xs ago" indicator counts smoothly
  useEffect(() => {
    const id = window.setInterval(() => setTick((t) => t + 1), 1000);
    return () => window.clearInterval(id);
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-[80vh] items-center justify-center text-signal-white">
        <p className="font-mono text-sm uppercase tracking-wider text-signal-white/60">Listening for signal…</p>
      </div>
    );
  }

  const eventsByMostRecent = (data?.events ?? []).slice().sort((a, b) =>
    new Date(b.time).getTime() - new Date(a.time).getTime(),
  );
  const youngest = eventsByMostRecent[0];
  const oldestSinceMs = youngest ? Date.now() - new Date(youngest.time).getTime() : null;
  const lastSyncAgo = lastSync ? Math.floor((Date.now() - lastSync.getTime()) / 1000) : null;
  void tick; // re-render trigger only

  return (
    <main className="min-h-screen text-signal-white">
      <div className="mx-auto max-w-3xl px-6 py-12">
        <FadeIn>
          <div className="mb-10">
            <p className="mb-2 font-mono text-xs uppercase tracking-wider text-signal-white/60">Live console</p>
            <h1 className="text-5xl font-bold leading-[1.0] tracking-tight lg:text-6xl">Now</h1>
            <p className="mt-3 max-w-xl text-sm italic text-signal-white/60">
              Everything that happened in the last {data?.windowMinutes ?? 60} minutes, across every channel.
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 font-mono text-[10px] uppercase tracking-widest text-signal-white/40">
              <span className="flex items-center gap-2">
                <span
                  className={cn(
                    'block size-1.5 rounded-sm',
                    lastSyncAgo !== null && lastSyncAgo < REFRESH_MS / 1000 + 2
                      ? 'bg-trace-up animate-pulse'
                      : 'bg-signal-white/30',
                  )}
                  aria-hidden="true"
                />
                Last sync {lastSyncAgo === null ? '—' : `${lastSyncAgo}s`} ago · refresh every {REFRESH_MS / 1000}s
              </span>
              {youngest && oldestSinceMs !== null && (
                <span>Latest signal: {formatRelative(oldestSinceMs)} ago</span>
              )}
            </div>
          </div>
        </FadeIn>

        <FadeIn delay={0.1}>
          {eventsByMostRecent.length === 0 ? (
            <div className="rounded-md border border-signal-white/10 bg-rack-black/60 p-8 text-center">
              <p className="font-mono text-sm uppercase tracking-wider text-signal-white/60">The console is silent.</p>
              <p className="mt-2 text-xs italic text-signal-white/40">No signal in the last {data?.windowMinutes ?? 60} minutes.</p>
            </div>
          ) : (
            <ol className="relative">
              {/* vertical hairline */}
              <span
                aria-hidden="true"
                className="absolute left-[7px] top-2 bottom-2 w-px bg-signal-white/10"
              />
              {eventsByMostRecent.map((e, i) => (
                <TimelineRow key={`${e.time}-${i}`} event={e} />
              ))}
            </ol>
          )}
        </FadeIn>
      </div>
    </main>
  );
}

function TimelineRow({ event }: { event: TimelineEvent }) {
  const dotClass = CHANNEL_CLASS.bg[event.channel];
  const channelText = CHANNEL_CLASS.text[event.channel];
  const localTime = new Date(event.time).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
  return (
    <li className="relative flex items-start gap-4 py-3">
      <span className={cn('relative z-10 mt-1.5 block size-3.5 shrink-0 rounded-sm border-2 border-rack-black', dotClass)} aria-hidden="true" />
      <time
        dateTime={event.time}
        className="mt-1 w-14 shrink-0 font-mono text-[10px] uppercase tracking-widest tabular-nums text-signal-white/50"
      >
        {localTime}
      </time>
      <div className="min-w-0 flex-1">
        <p className="text-sm text-signal-white">
          <span className={cn('mr-2 font-mono text-[10px] uppercase tracking-widest', channelText)}>{event.channel}</span>
          <span className="text-signal-white/70">{event.label}:</span>{' '}
          <span className="font-medium text-signal-white">{event.value}</span>
        </p>
      </div>
    </li>
  );
}

function formatRelative(ms: number): string {
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  return `${h}h`;
}
