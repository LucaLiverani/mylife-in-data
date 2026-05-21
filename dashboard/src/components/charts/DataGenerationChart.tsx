import { useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { CHART_COLORS, CHART_STYLES, formatChartDate } from './chartConfig';
import { cn } from '@/lib/utils';

interface DataGenerationChartProps {
  data: {
    dates: string[];
    spotify: number[];
    youtube: number[];
    calendar: number[];
    maps: number[];
  };
}

type SeriesName = 'Spotify' | 'YouTube' | 'Maps' | 'Calendar';

/**
 * 90-day signal-over-time line chart with four channel series.
 * No mini-KPI strip embedded (the page's Channels row above already says
 * who's loudest). Legend buttons toggle series; mono-uppercase, on-system.
 */
export function DataGenerationChart({ data }: DataGenerationChartProps) {
  const [visibleSeries, setVisibleSeries] = useState<Record<SeriesName, boolean>>({
    Spotify:  true,
    YouTube:  true,
    Maps:     true,
    Calendar: true,
  });

  const chartData = data.dates.map((date, i) => ({
    date: formatChartDate(date),
    Spotify:  Number(data.spotify[i])  || 0,
    YouTube:  Number(data.youtube[i])  || 0,
    Maps:     Number(data.maps[i])     || 0,
    Calendar: Number(data.calendar[i]) || 0,
  }));

  const toggleSeries = (series: SeriesName) => {
    setVisibleSeries(prev => ({ ...prev, [series]: !prev[series] }));
  };

  const series: Array<{ name: SeriesName; color: string }> = [
    { name: 'Spotify',  color: CHART_COLORS.spotify  },
    { name: 'YouTube',  color: CHART_COLORS.youtube  },
    { name: 'Maps',     color: CHART_COLORS.maps     },
    { name: 'Calendar', color: CHART_COLORS.calendar },
  ];

  return (
    <div className="flex h-full flex-col">
      {/* Mono-uppercase toggle row — on system, replaces the old hero-tile strip */}
      <div className="mb-4 flex flex-wrap gap-3">
        {series.map((s) => {
          const on = visibleSeries[s.name];
          return (
            <button
              key={s.name}
              onClick={() => toggleSeries(s.name)}
              aria-pressed={on}
              className={cn(
                'flex items-center gap-2 rounded-sm px-2 py-1 font-mono text-[10px] uppercase tracking-widest transition-colors',
                'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal-white',
                on ? 'text-signal-white/90' : 'text-signal-white/30',
              )}
            >
              <span
                className="block size-2 rounded-sm"
                style={{ backgroundColor: on ? s.color : 'rgba(255,255,255,0.15)' }}
                aria-hidden="true"
              />
              {s.name}
            </button>
          );
        })}
      </div>

      <div className="flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid {...CHART_STYLES.cartesianGrid} />
            <XAxis
              dataKey="date"
              stroke="rgba(255,255,255,0.25)"
              tickLine={false}
              axisLine={false}
              tick={{
                fill: 'rgba(255,255,255,0.6)',
                fontSize: 10,
                fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
              }}
            />
            <YAxis
              stroke="rgba(255,255,255,0.25)"
              tickLine={false}
              axisLine={false}
              width={32}
              tick={{
                fill: 'rgba(255,255,255,0.4)',
                fontSize: 10,
                fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
              }}
            />
            <Tooltip
              contentStyle={CHART_STYLES.tooltip.contentStyle}
              itemStyle={CHART_STYLES.tooltip.itemStyle}
              labelStyle={CHART_STYLES.tooltip.labelStyle}
              cursor={CHART_STYLES.tooltip.cursor}
            />
            {visibleSeries.Spotify && (
              <Line type="monotone" dataKey="Spotify"
                    stroke={CHART_COLORS.spotify}  strokeWidth={2}
                    dot={{ fill: CHART_COLORS.spotify, r: 2 }}  activeDot={{ r: 4 }} />
            )}
            {visibleSeries.YouTube && (
              <Line type="monotone" dataKey="YouTube"
                    stroke={CHART_COLORS.youtube}  strokeWidth={2}
                    dot={{ fill: CHART_COLORS.youtube, r: 2 }}  activeDot={{ r: 4 }} />
            )}
            {visibleSeries.Maps && (
              <Line type="monotone" dataKey="Maps"
                    stroke={CHART_COLORS.maps}     strokeWidth={2}
                    dot={{ fill: CHART_COLORS.maps, r: 2 }}     activeDot={{ r: 4 }} />
            )}
            {visibleSeries.Calendar && (
              <Line type="monotone" dataKey="Calendar"
                    stroke={CHART_COLORS.calendar} strokeWidth={2}
                    dot={{ fill: CHART_COLORS.calendar, r: 2 }} activeDot={{ r: 4 }} />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
