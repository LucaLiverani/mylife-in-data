import { useEffect, useState } from 'react';
import { FadeIn } from '@/components/animations/FadeIn';
import { Surface } from '@/components/Surface';
import { systemAPI } from '@/lib/api';
import { CHANNEL_CLASS, type Channel } from '@/lib/channels';
import { formatCount, formatDecimal } from '@/lib/format';
import { cn } from '@/lib/utils';

type Status = 'healthy' | 'degraded' | 'stale' | 'down';

interface ChannelHealth {
  channel: Channel;
  status: Status;
  lastBatchAgo: string;
  eventsPerHour: number;
  errors24h: number;
}

interface DbDisk {
  database: string;
  rows: number;
  diskUsedMb: number;
}

interface SystemHealth {
  generatedAt: string;
  overall: { status: Status; summary: string };
  channels: ChannelHealth[];
  storage: {
    name: string;
    status: Status;
    rowCount: number;
    diskUsedMb: number;
    byDatabase: DbDisk[];
  };
  errors24h: Array<{
    time: string;
    channel: Channel | 'platform';
    severity: 'warn' | 'error';
    message: string;
  }>;
}

const STATUS_CLASS: Record<Status, { dot: string; text: string; label: string }> = {
  healthy:  { dot: 'bg-trace-up',        text: 'text-trace-up',        label: 'Healthy'  },
  degraded: { dot: 'bg-yellow-500',      text: 'text-yellow-500',      label: 'Degraded' },
  stale:    { dot: 'bg-signal-white/40', text: 'text-signal-white/60', label: 'Stale'    },
  down:     { dot: 'bg-trace-down',      text: 'text-trace-down',      label: 'Down'     },
};

// Never throw on an unexpected/missing status — fall back to "stale".
const statusClass = (s: string | undefined | null) =>
  STATUS_CLASS[(s as Status)] ?? STATUS_CLASS.stale;

export default function SystemPage() {
  const [data, setData] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    systemAPI.getHealth()
      .then((d) => setData(d as SystemHealth))
      .catch(() => setError('System endpoint unreachable.'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-[80vh] items-center justify-center text-signal-white">
        <p className="font-mono text-sm uppercase tracking-wider text-signal-white/60">Polling the rack…</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-20 text-signal-white">
        <p className="mb-4 font-mono text-xs uppercase tracking-wider text-trace-down">
          The system page can't reach itself.
        </p>
        <p className="text-sm text-signal-white/70">{error ?? 'No data.'}</p>
      </main>
    );
  }

  const overall = statusClass(data.overall?.status);
  const channels = data.channels ?? [];
  const errors = data.errors24h ?? [];

  return (
    <main className="min-h-screen text-signal-white">
      <div className="mx-auto max-w-7xl px-6 py-12">
        <FadeIn>
          <div className="mb-12">
            <p className="mb-2 font-mono text-xs uppercase tracking-wider text-signal-white/60">System health</p>
            <div className="flex items-baseline gap-4">
              <h1 className="text-5xl font-bold leading-[1.0] tracking-tight lg:text-6xl">
                <span className={overall.text}>{overall.label}</span>
              </h1>
              <span className="font-mono text-xs uppercase tracking-widest text-signal-white/50">
                {data.overall?.summary ?? ''}
              </span>
            </div>
            <p className="mt-3 max-w-xl text-sm italic text-signal-white/60">
              The infrastructure behind the surface — ingestion, storage, freshness.
            </p>
          </div>
        </FadeIn>

        {/* Channels */}
        <FadeIn delay={0.1}>
          <section className="mb-10" aria-labelledby="system-channels">
            <h2 id="system-channels" className="mb-4 font-mono text-xs uppercase tracking-wider text-signal-white/60">
              Channels
            </h2>
            {channels.length === 0 ? (
              <p className="font-mono text-sm text-signal-white/60">No channel data.</p>
            ) : (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
                {channels.map((c) => (
                  <ChannelHealthTile key={c.channel} health={c} />
                ))}
              </div>
            )}
          </section>
        </FadeIn>

        {/* Storage */}
        <FadeIn delay={0.15}>
          <section className="mb-10" aria-labelledby="system-storage">
            <Surface>
              <StorageBlock storage={data.storage} />
            </Surface>
          </section>
        </FadeIn>

        {/* Alerts */}
        <FadeIn delay={0.2}>
          <section aria-labelledby="system-alerts">
            <Surface>
              <h2 id="system-alerts" className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
                Alerts · last 7 days
              </h2>
              {errors.length === 0 ? (
                <p className="font-mono text-sm text-signal-white/60">
                  No alerts. <span className="text-signal-white/40">(All quiet.)</span>
                </p>
              ) : (
                <ul className="-mx-6 -mb-6">
                  {errors.map((e, i) => (
                    <li key={i} className="flex items-start gap-3 border-t border-signal-white/5 px-6 py-3">
                      <span
                        className={cn(
                          'mt-1.5 block size-1.5 shrink-0 rounded-sm',
                          e.severity === 'error' ? 'bg-trace-down' : 'bg-yellow-500',
                        )}
                        aria-hidden="true"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm text-signal-white">{e.message}</div>
                        <div className="font-mono text-[10px] uppercase tracking-wider text-signal-white/50">
                          {e.channel} · {e.time ? new Date(e.time).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Surface>
          </section>
        </FadeIn>
      </div>
    </main>
  );
}

function ChannelHealthTile({ health }: { health: ChannelHealth }) {
  const c = statusClass(health.status);
  const channelClass = CHANNEL_CLASS.bg[health.channel] ?? 'bg-signal-white/40';
  const channelText = CHANNEL_CLASS.text[health.channel] ?? 'text-signal-white';
  return (
    <article className="rounded-md border border-signal-white/10 bg-rack-black/60 p-5">
      <div className="mb-3 flex items-center justify-between">
        <span className={cn('block size-2 rounded-sm', channelClass)} aria-hidden="true" />
        <span className={cn('flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest', c.text)}>
          <span className={cn('block size-1.5 rounded-sm', c.dot)} aria-hidden="true" />
          {c.label}
        </span>
      </div>
      <h3 className={cn('text-xl font-bold capitalize leading-none tracking-tight', channelText)}>
        {health.channel}
      </h3>
      <dl className="mt-4 grid grid-cols-2 gap-y-2 font-mono text-[11px]">
        <dt className="uppercase tracking-wider text-signal-white/40">Last batch</dt>
        <dd className="text-right text-signal-white/80">{health.lastBatchAgo}</dd>
        <dt className="uppercase tracking-wider text-signal-white/40">Ingest rate</dt>
        <dd className="text-right tabular-nums text-signal-white/80">{formatCount(health.eventsPerHour)}/hr</dd>
      </dl>
    </article>
  );
}

function StorageBlock({ storage }: { storage: SystemHealth['storage'] }) {
  const c = statusClass(storage?.status);
  const byDatabase = storage?.byDatabase ?? [];
  return (
    <>
      <div className="mb-6 flex items-center justify-between">
        <h2 className="font-mono text-xs uppercase tracking-wider text-signal-white/60">{storage?.name ?? 'ClickHouse'}</h2>
        <span className={cn('flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest', c.text)}>
          <span className={cn('block size-1.5 rounded-sm', c.dot)} aria-hidden="true" />
          {c.label}
        </span>
      </div>
      <dl className="grid grid-cols-2 gap-y-3 font-mono text-xs">
        <dt className="uppercase tracking-wider text-signal-white/40">Total rows</dt>
        <dd className="text-right tabular-nums text-signal-white/90">{formatCount(storage?.rowCount ?? 0)}</dd>
        <dt className="uppercase tracking-wider text-signal-white/40">Disk used</dt>
        <dd className="text-right tabular-nums text-signal-white/90">{formatDecimal((storage?.diskUsedMb ?? 0) / 1024)} GB</dd>
      </dl>
      {byDatabase.length > 0 && (
        <div className="mt-6">
          <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-signal-white/40">By database</p>
          <ul className="font-mono text-xs">
            {byDatabase.map((db) => (
              <li key={db.database} className="flex items-center justify-between border-t border-signal-white/5 py-2">
                <span className="text-signal-white/70">{db.database}</span>
                <span className="tabular-nums text-signal-white/90">
                  {formatCount(db.rows)} rows · {formatDecimal(db.diskUsedMb / 1024)} GB
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}
