import { CHANNEL_HEX, type Channel } from '@/lib/channels';

interface SparklineProps {
  values: number[];
  channel: Channel;
  height?: number;
  /**
   * Fixed pixel width. Omit to make the sparkline fill its container width
   * (responsive mode: SVG stretches horizontally, stroke stays crisp via
   * `vector-effect="non-scaling-stroke"`).
   */
  width?: number;
  /** Stroke thickness in px. Default 1.5. */
  strokeWidth?: number;
  /** Optional aria-label override; defaults to decorative. */
  ariaLabel?: string;
}

/**
 * Pure-SVG mini line chart. No Recharts, no D3 — kept featherlight because
 * the dashboard renders many of these.
 *
 * Two modes:
 *   - fixed:        pass `width` in px (used by ChannelStrip's compact rendering)
 *   - responsive:   omit `width` → SVG fills the parent container; stroke
 *                   width stays consistent via `vector-effect="non-scaling-stroke"`
 *                   (used by TopList rows where the sparkline should stretch
 *                    to the available row width)
 *
 * Decorative by default (`aria-hidden`); pass `ariaLabel` to expose it to
 * assistive tech when the chart carries meaning the surrounding text doesn't
 * already convey.
 */
export function Sparkline({
  values,
  channel,
  height = 28,
  width,
  strokeWidth = 1.5,
  ariaLabel,
}: SparklineProps) {
  const responsive = width === undefined;
  // Virtual coordinate space for the path. In responsive mode the SVG renders
  // at 100% of its container and the path scales horizontally; the constant
  // here is arbitrary as long as it matches the viewBox.
  const renderWidth = width ?? 100;

  const safe = values.length > 0 ? values : [0];
  const min = Math.min(...safe);
  const max = Math.max(...safe);
  const range = max - min || 1;
  const pad = strokeWidth;

  const stepX = safe.length > 1 ? (renderWidth - pad * 2) / (safe.length - 1) : 0;

  const points = safe.map((v, i) => {
    const x = pad + i * stepX;
    const y = pad + (height - pad * 2) * (1 - (v - min) / range);
    return [x, y] as const;
  });

  const linePath = points.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(' ');
  const areaPath =
    `M ${points[0][0].toFixed(2)},${(height - pad).toFixed(2)} ` +
    points.map(([x, y]) => `L ${x.toFixed(2)},${y.toFixed(2)}`).join(' ') +
    ` L ${points[points.length - 1][0].toFixed(2)},${(height - pad).toFixed(2)} Z`;

  const hex = CHANNEL_HEX[channel];

  return (
    <svg
      width={responsive ? '100%' : width}
      height={height}
      viewBox={`0 0 ${renderWidth} ${height}`}
      preserveAspectRatio={responsive ? 'none' : 'xMidYMid meet'}
      role={ariaLabel ? 'img' : 'presentation'}
      aria-label={ariaLabel}
      aria-hidden={ariaLabel ? undefined : true}
      className="block"
    >
      <path
        d={areaPath}
        fill={hex}
        fillOpacity={0.15}
      />
      <polyline
        points={linePath}
        fill="none"
        stroke={hex}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect={responsive ? 'non-scaling-stroke' : undefined}
      />
    </svg>
  );
}
