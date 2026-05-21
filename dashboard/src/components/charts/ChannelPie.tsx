import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { CHANNEL_RAMP, type Channel } from '@/lib/channels';
import { CHART_STYLES } from './chartConfig';

interface Slice {
  name: string;
  value: number;
  /** Optional precomputed percentage. If absent, derived from values. */
  percentage?: number;
  // Recharts's ChartDataInput requires an index signature.
  [k: string]: unknown;
}

interface ChannelPieProps {
  /** Page channel — determines the tonal ramp used for slice colors. */
  channel: Channel;
  data: Slice[];
  /** Optional explicit color map for slices by name; falls back to channel ramp. */
  colorByName?: Record<string, string>;
  /**
   * Donut canvas height in px, or `'fill'` to expand to the parent's
   * remaining height (use inside a flex-column Surface). Default `'fill'`.
   */
  height?: number | 'fill';
  /** How many slices to render before grouping the rest as "Other". */
  topN?: number;
  /** Whether to render the legend below the donut. */
  legend?: boolean;
  /** Minimum height in px when height='fill'. Default 220. */
  minHeight?: number;
}

/**
 * Unified donut + legend used by every per-source page (Spotify genres,
 * YouTube categories, Calendar categories, etc.). Same shape, same spacing,
 * same tooltip — only colors and data change. Tonal ramp comes from
 * CHANNEL_RAMP unless `colorByName` is given.
 */
export function ChannelPie({
  channel,
  data,
  colorByName,
  height = 'fill',
  topN = 5,
  legend = true,
  minHeight = 220,
}: ChannelPieProps) {
  const ramp = CHANNEL_RAMP[channel];

  const sorted = [...data].sort((a, b) => b.value - a.value);
  const head = sorted.slice(0, topN);
  const tail = sorted.slice(topN);
  const slices: Slice[] =
    tail.length > 0
      ? [...head, { name: 'Other', value: tail.reduce((sum, s) => sum + s.value, 0) }]
      : head;

  const total = slices.reduce((sum, s) => sum + s.value, 0);
  const colorFor = (name: string, i: number): string =>
    colorByName?.[name] ?? ramp[i % ramp.length];

  // When fill, the donut expands; when fixed, it uses the pixel height.
  const canvasStyle = height === 'fill'
    ? { flex: '1 1 auto', minHeight, width: '100%' }
    : { height, width: '100%' };

  return (
    <div className={height === 'fill' ? 'flex h-full w-full flex-col' : undefined}>
      <div style={canvasStyle}>
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={slices}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              outerRadius="90%"
              innerRadius="55%"
              paddingAngle={2}
              stroke="transparent"
            >
              {slices.map((s, i) => (
                <Cell key={s.name} fill={colorFor(s.name, i)} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={CHART_STYLES.tooltip.contentStyle}
              itemStyle={CHART_STYLES.tooltip.itemStyle}
              labelStyle={CHART_STYLES.tooltip.labelStyle}
              formatter={(value: number, name: string) => {
                const pct = total > 0 ? ((value / total) * 100).toFixed(0) : '0';
                return [`${value.toLocaleString()} (${pct}%)`, name];
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      {legend && (
        <ul className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 font-mono text-xs">
          {slices.map((s, i) => {
            const pct = s.percentage ?? (total > 0 ? Math.round((s.value / total) * 100) : 0);
            return (
              <li key={s.name} className="flex items-center gap-2 text-signal-white/80">
                <span
                  className="block size-2 shrink-0 rounded-sm"
                  style={{ backgroundColor: colorFor(s.name, i) }}
                  aria-hidden="true"
                />
                <span className="truncate">{s.name}</span>
                <span className="ml-auto tabular-nums text-signal-white/50">{pct}%</span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
