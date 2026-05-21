import { useMemo } from 'react';
import { FadeIn } from '@/components/animations/FadeIn';
import { CHANNEL_CLASS } from '@/lib/channels';
import { useLiveTimeline, type TimelineEvent } from '@/lib/useLiveTimeline';
import { cn } from '@/lib/utils';

const REFRESH_MS = 15_000;

export default function NowPage() {
  const { data, events, lastSync, loading, tick } = useLiveTimeline(REFRESH_MS);
  void tick;

  // Group events by local-day so a 7-day list stays readable.
  const grouped = useMemo(() => groupByDay(events), [events]);

  if (loading) {
    return (
      <div className="flex min-h-[80vh] items-center justify-center text-signal-white">
        <p className="font-mono text-sm uppercase tracking-wider text-signal-white/60">Listening for signal…</p>
      </div>
    );
  }

  const windowMins = data?.windowMinutes ?? 60;
  const windowLabel = formatWindow(windowMins);
  const lastSyncAgo = lastSync ? Math.floor((Date.now() - lastSync.getTime()) / 1000) : null;
  const fresh = lastSyncAgo !== null && lastSyncAgo < REFRESH_MS / 1000 + 2;

  return (
    <main className="min-h-screen text-signal-white">
      <div className="mx-auto max-w-3xl px-6 py-12">
        <FadeIn>
          <div className="mb-8">
            <p className="mb-2 font-mono text-xs uppercase tracking-wider text-signal-white/60">Live console</p>
            <h1 className="text-5xl font-bold leading-[1.0] tracking-tight lg:text-6xl">Now</h1>
            <p className="mt-3 max-w-xl text-sm italic text-signal-white/60">
              Everything that's reached the warehouse in the last {windowLabel}, across every channel.
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 font-mono text-[10px] uppercase tracking-widest text-signal-white/40">
              <span className="flex items-center gap-2">
                <span
                  className={cn('block size-1.5 rounded-sm', fresh ? 'bg-trace-up animate-pulse' : 'bg-signal-white/30')}
                  aria-hidden="true"
                />
                Last sync {lastSyncAgo === null ? '—' : `${lastSyncAgo}s`} ago · refresh every {REFRESH_MS / 1000}s
              </span>
              <span>{events.length} signals · {grouped.length} day{grouped.length === 1 ? '' : 's'}</span>
            </div>
          </div>
        </FadeIn>

        <FadeIn delay={0.1}>
          {events.length === 0 ? (
            <div className="rounded-md border border-signal-white/10 bg-rack-black/60 p-8 text-center">
              <p className="font-mono text-sm uppercase tracking-wider text-signal-white/60">The console is silent.</p>
              <p className="mt-2 text-xs italic text-signal-white/40">No signal in the last {windowLabel}.</p>
            </div>
          ) : (
            <div className="space-y-8">
              {grouped.map((day) => (
                <DayGroup key={day.key} day={day} />
              ))}
            </div>
          )}
        </FadeIn>
      </div>
    </main>
  );
}

interface DayBucket {
  key: string;       // YYYY-MM-DD
  label: string;     // "Today" / "Yesterday" / "Wed, Mar 5"
  events: TimelineEvent[];
}

function DayGroup({ day }: { day: DayBucket }) {
  return (
    <section aria-label={day.label}>
      <header className="mb-3 flex items-baseline justify-between">
        <h2 className="font-mono text-xs uppercase tracking-widest text-signal-white/60">{day.label}</h2>
        <span className="font-mono text-[10px] uppercase tracking-widest tabular-nums text-signal-white/40">
          {day.events.length} signal{day.events.length === 1 ? '' : 's'}
        </span>
      </header>
      <ol className="relative">
        <span aria-hidden="true" className="absolute left-[7px] top-2 bottom-2 w-px bg-signal-white/10" />
        {day.events.map((e, i) => (
          <TimelineRow key={`${e.time}-${i}`} event={e} />
        ))}
      </ol>
    </section>
  );
}

function TimelineRow({ event }: { event: TimelineEvent }) {
  const dotClass = CHANNEL_CLASS.bg[event.channel];
  const channelText = CHANNEL_CLASS.text[event.channel];
  const localTime = new Date(event.time).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
  return (
    <li className="relative flex items-start gap-4 py-2.5">
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

function formatWindow(minutes: number): string {
  if (minutes < 60) return `${minutes} minutes`;
  if (minutes < 24 * 60) {
    const h = Math.round(minutes / 60);
    return `${h} hour${h === 1 ? '' : 's'}`;
  }
  const d = Math.round(minutes / (24 * 60));
  return `${d} day${d === 1 ? '' : 's'}`;
}

function groupByDay(events: TimelineEvent[]): DayBucket[] {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const buckets = new Map<string, DayBucket>();
  for (const e of events) {
    const d = new Date(e.time);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    let bucket = buckets.get(key);
    if (!bucket) {
      const eventDay = new Date(d);
      eventDay.setHours(0, 0, 0, 0);
      const label =
        eventDay.getTime() === today.getTime()     ? 'Today' :
        eventDay.getTime() === yesterday.getTime() ? 'Yesterday' :
        eventDay.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
      bucket = { key, label, events: [] };
      buckets.set(key, bucket);
    }
    bucket.events.push(e);
  }

  // Sort buckets by date desc (Today first), preserving event order within each
  return Array.from(buckets.values()).sort(
    (a, b) => new Date(b.events[0].time).getTime() - new Date(a.events[0].time).getTime(),
  );
}
