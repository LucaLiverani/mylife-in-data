import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { CHANNEL_CLASS, type Channel } from '@/lib/channels';
import { formatKpi, type KpiKind } from '@/lib/format';
import { cn } from '@/lib/utils';
import { Sparkline } from './Sparkline';

export type ChannelStatus = 'live' | 'today' | 'recent' | 'idle';

interface KpiSpec {
  label: string;
  value: number | string;
  kind?: KpiKind;
}

interface ChannelStripProps {
  channel: Channel;
  title: string;
  status: ChannelStatus;
  primary: string;
  secondary: string;
  sparkline: number[];
  kpiA: KpiSpec;
  kpiB: KpiSpec;
  href: string;
}

const STATUS_LABEL: Record<ChannelStatus, string> = {
  live:   'Live now',
  today:  'Today',
  recent: 'Recent',
  idle:   'Quiet',
};

/**
 * Home-page channel hero. Flat rack-black surface at rest; hover lifts and
 * tints the border + glow with the channel color. The entire strip is the
 * click target. Layout matches the per-source KPI Meter pattern from
 * DESIGN.md §5 — label-above-value, mono numerics, channel-color values.
 *
 *   ┌────────────────────────────────────────┐
 *   │ ● LIVE                            →    │  status + click chevron
 *   │ Spotify                                │  channel name
 *   │                                        │
 *   │ Shape of You                           │  primary
 *   │ Ed Sheeran                             │  secondary
 *   │                                        │
 *   │ ▁▂▃▅█▆▃▁▂▃▅▆▃▁▂▃▅▆▃▁▂▃▅▆▃▁▂▃▅          │  30-day sparkline
 *   │ ─────────────────────────────          │  hairline
 *   │ HOURS              ARTISTS             │  KPI labels (mono /60)
 *   │ 253h               847                 │  KPI values (mono large, channel color)
 *   └────────────────────────────────────────┘
 */
export function ChannelStrip({
  channel,
  title,
  status,
  primary,
  secondary,
  sparkline,
  kpiA,
  kpiB,
  href,
}: ChannelStripProps) {
  const isLive = status === 'live';
  const dotClass =
    status === 'live'   ? cn(CHANNEL_CLASS.bg[channel], 'animate-pulse') :
    status === 'today'  ? CHANNEL_CLASS.bg[channel] :
    status === 'recent' ? 'bg-signal-white/40' :
                          'bg-signal-white/20';
  const statusTextClass = isLive ? CHANNEL_CLASS.text[channel] : 'text-signal-white/60';

  return (
    <Link
      to={href}
      aria-label={`${title} channel — ${primary}`}
      className={cn(
        'group flex h-full flex-col gap-4 rounded-md border border-signal-white/10 bg-rack-black/60 p-5',
        'transition duration-200 ease-snap',
        'hover:-translate-y-0.5 hover:shadow-lift',
        CHANNEL_CLASS.hoverGlow[channel],
        CHANNEL_CLASS.hoverBorder[channel],
        CHANNEL_CLASS.focusRing[channel],
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2',
        'focus:outline-none',
      )}
    >
      {/* Status + click chevron — top row, balanced */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={cn('block size-2 rounded-sm', dotClass)} aria-hidden="true" />
          <span className={cn('font-mono text-[10px] font-medium uppercase tracking-widest', statusTextClass)}>
            {STATUS_LABEL[status]}
          </span>
        </div>
        <span
          className={cn(
            'flex items-center gap-1 font-mono text-[10px] font-medium uppercase tracking-widest',
            'text-signal-white/35 transition-colors',
            CHANNEL_CLASS.groupHoverText[channel],
          )}
          aria-hidden="true"
        >
          View
          <ChevronRight className="size-3.5 transition-transform duration-200 ease-snap group-hover:translate-x-0.5" />
        </span>
      </div>

      {/* Channel name */}
      <h3 className={cn('text-2xl font-bold leading-none tracking-tight', CHANNEL_CLASS.text[channel])}>
        {title}
      </h3>

      {/* Primary + secondary */}
      <div className="min-h-[3.25rem]">
        <p className="line-clamp-2 text-sm font-medium text-signal-white">{primary}</p>
        <p className="mt-1 truncate font-mono text-xs text-signal-white/60">{secondary}</p>
      </div>

      {/* Sparkline — fills the card width regardless of viewport */}
      {sparkline.length > 0 && (
        <div className="w-full">
          <Sparkline values={sparkline} channel={channel} height={32} />
        </div>
      )}

      {/* KPI pair — mono mixing-desk readout, label above value */}
      <div className="mt-auto grid grid-cols-2 gap-4 border-t border-signal-white/10 pt-4">
        <KpiBlock channel={channel} spec={kpiA} />
        <KpiBlock channel={channel} spec={kpiB} />
      </div>
    </Link>
  );
}

function KpiBlock({ channel, spec }: { channel: Channel; spec: KpiSpec }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="font-mono text-[10px] font-medium uppercase tracking-widest text-signal-white/60">
        {spec.label}
      </span>
      <span className={cn('font-mono text-2xl font-bold leading-none tabular-nums', CHANNEL_CLASS.text[channel])}>
        {formatKpi(spec.value, spec.kind ?? 'count')}
      </span>
    </div>
  );
}
