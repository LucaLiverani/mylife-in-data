import { useLayoutEffect, useRef, useState } from 'react';
import { CHANNEL_CLASS, type Channel } from '@/lib/channels';
import { formatKpi, type KpiKind } from '@/lib/format';
import { cn } from '@/lib/utils';
import { Sparkline } from '@/components/Sparkline';

export interface TopListItem {
  /** Primary label — e.g., artist name, channel title, destination. */
  primary: string;
  /** Optional secondary line — e.g., genre, category, activity type. */
  secondary?: string;
  /** Raw numeric value used for sort + display. */
  value: number;
  /** Optional per-item trend values. Rendered as an inline sparkline; length
   *  varies by source/window (e.g. Spotify = weekly since the KPI start date). */
  trend?: number[];
}

interface TopListProps {
  channel: Channel;
  items: TopListItem[];
  /** How `value` should be formatted for display (`hours`, `count`, etc.). */
  kind: KpiKind;
  /** Maximum number of rows to render (default 10). Items always sorted by value DESC. */
  limit?: number;
  /** Optional max-height for the scroll container. Default 360px. */
  maxHeight?: number;
}

/**
 * Shared "Top X" leaderboard used by every per-source page.
 *
 *   01  DOPE LEMON                                          4.2h
 *       lo-fi              ▁▂▃▅▇██▇▅▃▁▁▂▅▇█
 *
 * Always sorted by `value` descending. Inline per-item sparkline shows the
 * item's own momentum over its source's window (not a comparison to other items).
 *
 * Sparkline alignment: secondary labels naturally have different widths
 * ("lo-fi" vs "Science & Technology"), which would make sparklines start
 * at different X positions per row. We measure all secondary widths after
 * mount and pin every row's secondary column to the widest one — so every
 * sparkline begins from the same column edge.
 */
export function TopList({
  channel,
  items,
  kind,
  limit = 10,
  maxHeight = 360,
}: TopListProps) {
  const sorted = [...items].sort((a, b) => b.value - a.value).slice(0, limit);
  const channelText = CHANNEL_CLASS.text[channel];
  const scrollClasses = CHANNEL_CLASS.scrollbar[channel];

  const containerRef = useRef<HTMLOListElement>(null);
  const [secondaryWidth, setSecondaryWidth] = useState<number | null>(null);

  // Measure the widest secondary label after layout, before paint. Re-runs
  // when the item set changes (different sources / re-seed).
  useLayoutEffect(() => {
    const root = containerRef.current;
    if (!root) return;

    // Reset measurements so we read each label's natural intrinsic width.
    const labels = Array.from(root.querySelectorAll<HTMLElement>('[data-toplist-secondary]'));
    labels.forEach((el) => {
      el.style.width = 'auto';
    });

    if (labels.length === 0) {
      setSecondaryWidth(null);
      return;
    }

    let max = 0;
    labels.forEach((el) => {
      max = Math.max(max, el.scrollWidth);
    });

    // +1 to soak up sub-pixel rounding so the longest label doesn't truncate.
    setSecondaryWidth(max + 1);
  }, [sorted.length, channel, kind]);

  if (sorted.length === 0) {
    return (
      <p className="font-mono text-xs uppercase tracking-wider text-signal-white/40">
        No entries yet.
      </p>
    );
  }

  // maxWidth caps the pinned column on narrow cards so a long secondary
  // ("Science & Technology") can't crush the sparkline at mobile widths.
  const secondaryStyle = secondaryWidth
    ? { width: secondaryWidth, maxWidth: '45%', flexShrink: 0 }
    : undefined;

  return (
    <ol
      ref={containerRef}
      className={cn('overflow-y-auto pr-1', scrollClasses)}
      style={{ maxHeight }}
    >
      {sorted.map((item, i) => {
        const hasSecondary = Boolean(item.secondary);
        const hasTrend = Boolean(item.trend && item.trend.length > 0);
        const hasSecondLine = hasSecondary || hasTrend;
        return (
          <li
            key={`${item.primary}-${i}`}
            className="flex items-start gap-4 border-b border-signal-white/5 py-3 last:border-b-0"
          >
            <span className={cn('w-6 shrink-0 pt-0.5 font-mono text-xs font-medium tabular-nums', channelText)}>
              {String(i + 1).padStart(2, '0')}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-signal-white">
                {item.primary}
              </p>
              {hasSecondLine && (
                <div className="mt-1.5 flex items-center gap-4">
                  {/* Secondary column: always rendered (even as empty spacer) when ANY row in
                      the list has a secondary, so sparklines align across rows. */}
                  <p
                    data-toplist-secondary
                    style={secondaryStyle}
                    className="truncate font-mono text-[10px] uppercase tracking-wider text-signal-white/60"
                  >
                    {item.secondary ?? ''}
                  </p>
                  {hasTrend && (
                    <div className="min-w-0 flex-1">
                      <Sparkline values={item.trend!} channel={channel} height={24} />
                    </div>
                  )}
                </div>
              )}
            </div>
            <span className={cn('shrink-0 pt-0.5 font-mono text-sm font-bold tabular-nums', channelText)}>
              {formatKpi(item.value, kind)}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
