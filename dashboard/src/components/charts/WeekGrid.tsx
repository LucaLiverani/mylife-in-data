import { useLayoutEffect, useRef, useState } from 'react';
import { CHANNEL_HEX, type Channel } from '@/lib/channels';

interface Cell {
  day: number;  // 0 = Mon, 6 = Sun
  hour: number; // 0..23
  /** Intensity 0..1 (e.g. % of hour scheduled). */
  intensity: number;
  /** Display label for tooltip. */
  label?: string;
}

interface WeekGridProps {
  channel: Channel;
  /** 7×24 = 168 cells. Missing cells render as empty. */
  cells: Cell[];
  /** Optional title for the tooltip body. */
  unitLabel?: string;
  /** Maximum cell width in px (height matches). Default 44. */
  maxCell?: number;
  /** Minimum cell width in px. Default 18. */
  minCell?: number;
}

/**
 * 24h × 7d "where time goes" grid. Hours as columns (so the chart reads
 * wide-and-short, like a conventional schedule), days as rows.
 * Channel-color intensity, mono tick labels, square cells.
 *
 * Responsive: ResizeObserver-driven cell size, fills container width within
 * minCell..maxCell. Renders at exact pixel dimensions so cells stay crisp.
 */
export function WeekGrid({
  channel,
  cells,
  unitLabel = 'busy',
  maxCell = 44,
  minCell = 18,
}: WeekGridProps) {
  const [hover, setHover] = useState<{ cell: Cell; x: number; y: number } | null>(null);

  // 7 rows (days) × 24 cols (hours)
  const grid: (Cell | undefined)[][] = Array.from({ length: 7 }, () => Array(24).fill(undefined));
  for (const c of cells) {
    if (c.hour >= 0 && c.hour < 24 && c.day >= 0 && c.day < 7) {
      grid[c.day][c.hour] = c;
    }
  }

  const fillForIntensity = (i: number) => {
    if (i <= 0) return 'rgba(255,255,255,0.04)';
    const v = Math.max(0, Math.min(1, i));
    const alphaHex = Math.round((0.15 + v * 0.85) * 255).toString(16).padStart(2, '0');
    return `${CHANNEL_HEX[channel]}${alphaHex}`;
  };

  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const COLS = 24; // hours
  const ROWS = 7;  // days
  const GAP = 3;
  const LABEL_W = 28;
  const HEADER_H = 18;

  const wrapRef = useRef<HTMLDivElement>(null);
  const [cell, setCell] = useState(maxCell);

  useLayoutEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const compute = () => {
      const w = el.clientWidth;
      const available = w - LABEL_W + GAP;
      const ideal = Math.floor(available / COLS - GAP);
      setCell(Math.max(minCell, Math.min(maxCell, ideal)));
    };
    compute();
    if (typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(compute);
    ro.observe(el);
    return () => ro.disconnect();
  }, [minCell, maxCell]);

  const width = LABEL_W + COLS * (cell + GAP) - GAP;
  const height = HEADER_H + ROWS * (cell + GAP) - GAP;

  return (
    <div ref={wrapRef} className="relative w-full overflow-x-auto scrollbar-thin">
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Weekly schedule grid by hour and day"
        className="block"
      >
        {/* Hour headers (every 3rd hour) */}
        {Array.from({ length: COLS }).map((_, hr) =>
          hr % 3 === 0 ? (
            <text
              key={`h-${hr}`}
              x={LABEL_W + hr * (cell + GAP) + cell / 2}
              y={12}
              textAnchor="middle"
              fontFamily='"IBM Plex Mono", ui-monospace, monospace'
              fontSize={9}
              fill="rgba(255,255,255,0.4)"
              style={{ textTransform: 'uppercase', letterSpacing: '0.1em' }}
            >
              {String(hr).padStart(2, '0')}
            </text>
          ) : null,
        )}
        {/* Day labels (rows) */}
        {days.map((d, di) => (
          <text
            key={d}
            x={LABEL_W - 6}
            y={HEADER_H + di * (cell + GAP) + cell / 2 + 3}
            textAnchor="end"
            fontFamily='"IBM Plex Mono", ui-monospace, monospace'
            fontSize={9}
            fill="rgba(255,255,255,0.4)"
            style={{ textTransform: 'uppercase', letterSpacing: '0.1em' }}
          >
            {d}
          </text>
        ))}
        {/* Cells */}
        {grid.flatMap((row, di) =>
          row.map((c, hr) => {
            const intensity = c?.intensity ?? 0;
            return (
              <rect
                key={`${di}-${hr}`}
                x={LABEL_W + hr * (cell + GAP)}
                y={HEADER_H + di * (cell + GAP)}
                width={cell}
                height={cell}
                rx={2}
                ry={2}
                fill={fillForIntensity(intensity)}
                onMouseEnter={(e) => c && setHover({ cell: c, x: e.clientX, y: e.clientY })}
                onMouseMove={(e) => c && setHover({ cell: c, x: e.clientX, y: e.clientY })}
                onMouseLeave={() => setHover(null)}
              />
            );
          }),
        )}
      </svg>
      {hover && (
        <div
          role="tooltip"
          className="pointer-events-none fixed z-50 rounded-md border border-signal-white/20 bg-rack-black/95 px-3 py-2 font-mono text-[11px] text-signal-white"
          style={{ left: hover.x + 12, top: hover.y + 12 }}
        >
          <div className="font-mono text-[10px] uppercase tracking-widest text-signal-white/50">
            {days[hover.cell.day]} · {String(hover.cell.hour).padStart(2, '0')}:00
          </div>
          <div className="tabular-nums">
            {hover.cell.label ?? `${Math.round(hover.cell.intensity * 100)}% ${unitLabel}`}
          </div>
        </div>
      )}
    </div>
  );
}
