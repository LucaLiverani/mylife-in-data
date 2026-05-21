import { BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { CHANNEL_HEX, type Channel } from '@/lib/channels';
import { formatKpi, type KpiKind } from '@/lib/format';
import { CHART_STYLES } from './chartConfig';

export interface HistogramBin {
  /** X-axis label (e.g., "Mon", "14:00"). */
  label: string;
  /** Magnitude for the bar. */
  value: number;
}

interface ChannelHistogramProps {
  channel: Channel;
  bins: HistogramBin[];
  /** Tooltip value formatter. Default 'count'. */
  kind?: KpiKind;
  /**
   * Pixel height of the chart, OR `'fill'` to expand to the parent's height
   * (use this when the chart sits inside a flex-column Surface that should
   * stretch to match a sibling card).
   *
   * Defaults to `'fill'` so equal-height grids "just work."
   */
  height?: number | 'fill';
  /** Tooltip name for the value (e.g., "Events", "Activities"). */
  unitLabel?: string;
  /** Highlight a single bin (e.g. busiest weekday) with a brighter fill. */
  highlightLabel?: string;
  /** Minimum height in px when `height='fill'`. Default 220. */
  minHeight?: number;
}

/**
 * Producer-console level-meter histogram. Square bars, mono tick labels,
 * channel-color fill, signal-white/10 grid hairlines. Used wherever a
 * categorical or hour-of-day comparison is needed (weekday breakdown, hour
 * of day) — replaces the rounded-top default Recharts bars across the app.
 *
 * Rules embedded:
 *   - radius=0 (no rounded corners — square per DESIGN.md §4 Flat-Rest)
 *   - mono tabular-nums tick labels per DESIGN.md Mono-for-Data Rule
 *   - one channel color per chart per DESIGN.md Channel-Lane Rule
 */
export function ChannelHistogram({
  channel,
  bins,
  kind = 'count',
  height = 'fill',
  unitLabel,
  highlightLabel,
  minHeight = 220,
}: ChannelHistogramProps) {
  const hex = CHANNEL_HEX[channel];
  const dimmedHex = `${hex}66`; // ~40% opacity when a highlight is set

  // Tighten the per-category gap when there are few bars so the chart fills
  // its container (7-bar weekday histograms otherwise look stranded inside a
  // wide Surface). For 24-hour histograms we keep more breathing room.
  const gap = bins.length <= 12 ? '12%' : '18%';
  // Cap bar width so very-wide containers don't produce comically thick bars,
  // but lift the cap well above the previous 32px so weekday charts read full-width.
  const cap = bins.length <= 12 ? 72 : 36;

  // When fill, use flex:1 so we expand inside a flex-column Surface.
  const wrapStyle = height === 'fill'
    ? { flex: '1 1 auto', minHeight, width: '100%' }
    : { height, width: '100%' };

  return (
    <div style={wrapStyle}>
      <ResponsiveContainer>
        <BarChart data={bins} margin={{ top: 8, right: 8, left: -16, bottom: 0 }} barCategoryGap={gap}>
          <CartesianGrid {...CHART_STYLES.cartesianGrid} vertical={false} />
          <XAxis
            dataKey="label"
            stroke="rgba(255,255,255,0.25)"
            tickLine={false}
            axisLine={false}
            tick={{
              fill: 'rgba(255,255,255,0.6)',
              fontSize: 10,
              fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
              letterSpacing: '0.05em',
            }}
          />
          <YAxis
            stroke="rgba(255,255,255,0.25)"
            tickLine={false}
            axisLine={false}
            width={28}
            tick={{
              fill: 'rgba(255,255,255,0.4)',
              fontSize: 10,
              fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
            }}
            tickFormatter={(v: number) => formatKpi(v, kind)}
          />
          <Tooltip
            contentStyle={CHART_STYLES.tooltip.contentStyle}
            itemStyle={CHART_STYLES.tooltip.itemStyle}
            labelStyle={CHART_STYLES.tooltip.labelStyle}
            cursor={{ fill: 'rgba(255,255,255,0.04)' }}
            formatter={(value: number) => [formatKpi(value, kind), unitLabel ?? 'Value']}
          />
          <Bar dataKey="value" radius={0} maxBarSize={cap}>
            {bins.map((bin) => (
              <Cell
                key={bin.label}
                fill={highlightLabel && bin.label !== highlightLabel ? dimmedHex : hex}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
