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
  /** Pixel height of the chart. Default 260. */
  height?: number;
  /** Tooltip name for the value (e.g., "Events", "Activities"). */
  unitLabel?: string;
  /** Highlight a single bin (e.g. busiest weekday) with a brighter fill. */
  highlightLabel?: string;
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
  height = 260,
  unitLabel,
  highlightLabel,
}: ChannelHistogramProps) {
  const hex = CHANNEL_HEX[channel];
  const dimmedHex = `${hex}66`; // ~40% opacity when a highlight is set

  return (
    <div style={{ height }}>
      <ResponsiveContainer>
        <BarChart data={bins} margin={{ top: 8, right: 8, left: -16, bottom: 0 }} barCategoryGap="20%">
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
          <Bar dataKey="value" radius={0} maxBarSize={32}>
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
