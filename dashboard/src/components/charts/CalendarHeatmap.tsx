import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { CHANNEL_HEX, type Channel } from '@/lib/channels';
import { formatKpi, type KpiKind } from '@/lib/format';

interface CalendarHeatmapProps {
  channel: Channel;
  /** Daily values keyed by YYYY-MM-DD. Missing days render as empty. */
  data: Record<string, number>;
  /** End date (inclusive). Defaults to today. */
  endDate?: Date;
  /** Number of weeks to render. Defaults to 53 (~1 year, GitHub-style). */
  weeks?: number;
  /** Unit label for tooltip ("plays", "hours", etc.). */
  unitLabel?: string;
  /** Format kind for tooltip value. */
  kind?: KpiKind;
  /** Minimum cell size in px. Below this the container scrolls horizontally. */
  minCell?: number;
  /** Maximum cell size in px. Caps the cell size on very wide containers. */
  maxCell?: number;
}

/**
 * GitHub-style calendar heatmap. 7 rows (days of week) × `weeks` columns.
 * Channel-color tint, 5 intensity stops + an "empty" stop.
 *
 * Responsive sizing: measures container width via ResizeObserver and picks
 * a cell size that fills horizontally, within minCell..maxCell. Renders at
 * exact pixel dimensions (no percentage width) so cells stay crisp.
 */
export function CalendarHeatmap({
  channel,
  data,
  endDate,
  weeks = 53,
  unitLabel = 'events',
  kind = 'count',
  minCell = 8,
  maxCell = 30,
}: CalendarHeatmapProps) {
  const end = endDate ?? new Date();
  const lastSunday = new Date(end);
  lastSunday.setHours(0, 0, 0, 0);
  lastSunday.setDate(lastSunday.getDate() + (6 - lastSunday.getDay()));

  const cells = useMemo(() => {
    const days: Array<{ date: Date; value: number }> = [];
    const start = new Date(lastSunday);
    start.setDate(start.getDate() - (weeks * 7 - 1));
    for (let i = 0; i < weeks * 7; i++) {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      days.push({ date: d, value: data[key] ?? 0 });
    }
    return days;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, weeks, lastSunday.toISOString()]);

  const values = cells.map((c) => c.value).filter((v) => v > 0);
  const max = values.length > 0 ? Math.max(...values) : 1;

  const fillForValue = (v: number) => {
    if (v <= 0) return 'rgba(255,255,255,0.04)';
    const ratio = Math.min(1, v / max);
    const bucket = ratio < 0.2 ? 0.2 : ratio < 0.4 ? 0.4 : ratio < 0.6 ? 0.6 : ratio < 0.8 ? 0.8 : 1;
    return `${CHANNEL_HEX[channel]}${alpha(bucket)}`;
  };

  // ── Responsive sizing — fill the container width ────────────────────
  const wrapRef = useRef<HTMLDivElement>(null);
  const [cellSize, setCellSize] = useState<number>(16);
  const GAP = 3;
  const LABEL_W = 28;

  useLayoutEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const compute = () => {
      const w = el.clientWidth;
      // Solve LABEL_W + weeks*(cell+GAP) - GAP <= w → cell <= (w - LABEL_W + GAP)/weeks - GAP
      const available = w - LABEL_W + GAP;
      const ideal = Math.floor(available / weeks - GAP);
      setCellSize(Math.max(minCell, Math.min(maxCell, ideal)));
    };
    compute();
    if (typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(compute);
    ro.observe(el);
    return () => ro.disconnect();
  }, [weeks, minCell, maxCell]);

  // When the grid is wider than the container (phones), land on the most
  // recent weeks — the left edge is the oldest, least interesting end.
  // Runs after the cellSize layout is committed, not against the initial one.
  useLayoutEffect(() => {
    const el = wrapRef.current;
    if (el) el.scrollLeft = el.scrollWidth;
  }, [cellSize, weeks]);

  const width = LABEL_W + weeks * (cellSize + GAP) - GAP;
  const height = 7 * (cellSize + GAP) - GAP;

  const [hover, setHover] = useState<{ idx: number; x: number; y: number } | null>(null);
  const hoverCell = hover ? cells[hover.idx] : null;
  useEffect(() => () => setHover(null), []);

  const dayLabels = ['Mon', '', 'Wed', '', 'Fri', '', 'Sun'];
  const rowDayOrder = [1, 2, 3, 4, 5, 6, 0];

  return (
    <div ref={wrapRef} className="w-full overflow-x-auto scrollbar-thin">
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`Activity heatmap, last ${weeks} weeks`}
        className="block"
      >
        {dayLabels.map((d, ri) =>
          d ? (
            <text
              key={ri}
              x={LABEL_W - 6}
              y={ri * (cellSize + GAP) + cellSize / 2 + 3}
              textAnchor="end"
              fontFamily='"IBM Plex Mono", ui-monospace, monospace'
              fontSize={9}
              fill="rgba(255,255,255,0.4)"
              style={{ textTransform: 'uppercase', letterSpacing: '0.1em' }}
            >
              {d}
            </text>
          ) : null,
        )}
        {Array.from({ length: weeks }).map((_, wi) =>
          rowDayOrder.map((dow, ri) => {
            const idx = wi * 7 + dow;
            const c = cells[idx];
            if (!c) return null;
            return (
              <rect
                key={`${wi}-${ri}`}
                x={LABEL_W + wi * (cellSize + GAP)}
                y={ri * (cellSize + GAP)}
                width={cellSize}
                height={cellSize}
                rx={2}
                ry={2}
                fill={fillForValue(c.value)}
                onMouseEnter={(e) => setHover({ idx, x: e.clientX, y: e.clientY })}
                onMouseMove={(e) => setHover({ idx, x: e.clientX, y: e.clientY })}
                onMouseLeave={() => setHover(null)}
                // Touch devices have no hover — tap toggles the same tooltip.
                onClick={(e) =>
                  setHover((h) => (h?.idx === idx ? null : { idx, x: e.clientX, y: e.clientY }))
                }
              />
            );
          }),
        )}
      </svg>

      <div className="mt-3 flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-signal-white/40">
        <span>Less</span>
        {[0, 0.2, 0.4, 0.6, 0.8, 1].map((step) => (
          <span
            key={step}
            className="inline-block size-3 rounded-[2px]"
            style={{ backgroundColor: step === 0 ? 'rgba(255,255,255,0.04)' : `${CHANNEL_HEX[channel]}${alpha(step)}` }}
            aria-hidden="true"
          />
        ))}
        <span>More</span>
      </div>

      {hoverCell && hover && (
        <div
          role="tooltip"
          className="pointer-events-none fixed z-50 rounded-md border border-signal-white/20 bg-rack-black/95 px-3 py-2 font-mono text-[11px] text-signal-white"
          style={{ left: hover.x + 12, top: hover.y + 12 }}
        >
          <div className="font-mono text-[10px] uppercase tracking-widest text-signal-white/50">
            {hoverCell.date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
          </div>
          <div className="tabular-nums">
            {formatKpi(hoverCell.value, kind)} <span className="text-signal-white/50">{unitLabel}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function alpha(ratio: number): string {
  const v = Math.max(0, Math.min(255, Math.round(ratio * 255)));
  return v.toString(16).padStart(2, '0');
}
