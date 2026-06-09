import { useState, type ReactNode } from 'react';
import { Surface } from '@/components/Surface';
import { EventRow } from '@/components/EventRow';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { TopList } from './TopList';
import { ChannelHistogram } from './ChannelHistogram';
import { ChannelPie } from './ChannelPie';
import { CHART_STYLES, TIME_SERIES_CHART_HEIGHT, formatChartDate } from './chartConfig';
import { CHANNEL_HEX } from '@/lib/channels';
import { formatTimeAgo, formatTimeOfDay } from '@/lib/format';
import { cn } from '@/lib/utils';

// Channel-violet owns the page (primary "Directions" series). Other series
// sit on a signal-white scale so they read as supporting context without
// competing for identity — and stay clearly distinguishable from each other.
const SERIES_COLOR = {
  Directions:   CHANNEL_HEX.maps,          // #A855F7 — channel identity, primary
  Searches:     'rgba(255,255,255,0.75)',
  Explorations: 'rgba(255,255,255,0.45)',
  Other:        'rgba(255,255,255,0.22)',
} as const;
const SERIES_WIDTH: Record<MapsSeries, number> = {
  Directions:   2.5,
  Searches:     1.5,
  Explorations: 1.5,
  Other:        1.25,
};

type MapsSeries = 'Directions' | 'Searches' | 'Explorations' | 'Other';

interface MapsData {
  hourlyActivity: Array<{ hour: string; activities: number }>;
  lastActivities: Array<{ time: string; location: string; type: string }>;
  topDestinations: Array<{ destination: string; count: number; type: string; trend?: number[] }>;
  dailyActivity: Array<{ date: string; directions: number; searches: number; explorations: number; other: number }>;
}

// Top destinations carry a place primary_type ('tourist_attraction', 'city', …)
// from the catalog — prettify it for display (snake_case → Title Case).
const formatPlaceType = (type: string): string =>
  type ? type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) : 'Place';

const formatActivityType = (type: string): string => {
  const typeMap: Record<string, string> = {
    directions: 'Directions',
    search: 'Search',
    explore: 'Explore',
    place_view: 'Place View',
    app_usage: 'App Usage',
    view: 'View',
    review: 'Review',
    save: 'Save',
    other: 'Other',
  };
  return typeMap[type] || type;
};

const getActivityIcon = (type: string) => {
  switch (type) {
    case 'directions':
      return (
        <svg className="size-4 text-channel-violet" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path d="M8 2L8 14M8 2L4 6M8 2L12 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case 'search':
      return (
        <svg className="size-4 text-channel-violet" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <circle cx="7" cy="7" r="4" stroke="currentColor" strokeWidth="1.5" fill="none" />
          <path d="M10 10L13 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      );
    case 'explore':
      return (
        <svg className="size-4 text-channel-violet" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <circle cx="8" cy="8" r="5" stroke="currentColor" strokeWidth="1.5" fill="none" />
          <path d="M8 3L10 8L8 13L6 8L8 3Z" fill="currentColor" />
        </svg>
      );
    case 'place_view':
    case 'view':
    case 'app_usage':
    case 'save':
    case 'review':
      return (
        <svg className="size-4 text-channel-violet" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path d="M8 2C6.067 2 4.5 3.567 4.5 5.5C4.5 8.25 8 13 8 13C8 13 11.5 8.25 11.5 5.5C11.5 3.567 9.933 2 8 2ZM8 7C7.172 7 6.5 6.328 6.5 5.5C6.5 4.672 7.172 4 8 4C8.828 4 9.5 4.672 9.5 5.5C9.5 6.328 8.828 7 8 7Z" fill="currentColor" />
        </svg>
      );
    default:
      return (
        <svg className="size-4 text-channel-violet" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <circle cx="8" cy="8" r="5" stroke="currentColor" strokeWidth="1.5" fill="none" />
          <circle cx="8" cy="8" r="1.5" fill="currentColor" />
        </svg>
      );
  }
};

export function MapsCharts({ data, tripsSlot }: { data: MapsData; tripsSlot?: ReactNode }) {
  const [visibleSeries, setVisibleSeries] = useState<Record<MapsSeries, boolean>>({
    Directions:   true,
    Searches:     true,
    Explorations: true,
    Other:        false,
  });

  const toggleSeries = (s: MapsSeries) => setVisibleSeries(p => ({ ...p, [s]: !p[s] }));

  // Defensive sort by raw date ascending so the x-axis always reads oldest →
  // newest (most recent day on the right), regardless of the order the API/view
  // returns rows in. The dbt model + API both sort ASC too; this is the last
  // line of defense so a query regression can't flip the axis again.
  const chartData = [...data.dailyActivity]
    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
    .map((d) => ({
      date: formatChartDate(d.date),
      Directions:   Number(d.directions)   || 0,
      Searches:     Number(d.searches)     || 0,
      Explorations: Number(d.explorations) || 0,
      Other:        Number(d.other)        || 0,
    }));

  // Activity-type distribution — totals across the 30-day window. Channels
  // the same color scheme as the daily-activity series so legend pairs read.
  const totals = data.dailyActivity.reduce(
    (acc, d) => ({
      Directions:   acc.Directions   + (Number(d.directions)   || 0),
      Searches:     acc.Searches     + (Number(d.searches)     || 0),
      Explorations: acc.Explorations + (Number(d.explorations) || 0),
      Other:        acc.Other        + (Number(d.other)        || 0),
    }),
    { Directions: 0, Searches: 0, Explorations: 0, Other: 0 },
  );
  const distributionData = [
    { name: 'Directions',   value: totals.Directions   },
    { name: 'Searches',     value: totals.Searches     },
    { name: 'Explorations', value: totals.Explorations },
    { name: 'Other',        value: totals.Other        },
  ].filter((d) => d.value > 0);

  const series: Array<{ name: MapsSeries; color: string }> = [
    { name: 'Directions',   color: SERIES_COLOR.Directions   },
    { name: 'Searches',     color: SERIES_COLOR.Searches     },
    { name: 'Explorations', color: SERIES_COLOR.Explorations },
    { name: 'Other',        color: SERIES_COLOR.Other        },
  ];

  return (
    <>
      <section className="mb-12">
        <Surface>
          <h2 className="mb-4 font-mono text-xs uppercase tracking-wider text-signal-white/60">
            Daily activity · last 30 days
          </h2>

          <div className="mb-4 flex flex-wrap gap-3">
            {series.map((s) => {
              const on = visibleSeries[s.name];
              return (
                <button
                  key={s.name}
                  onClick={() => toggleSeries(s.name)}
                  aria-pressed={on}
                  className={cn(
                    'flex items-center gap-2 rounded-sm px-2 py-2 font-mono text-[10px] uppercase tracking-widest transition-colors sm:py-1',
                    'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-channel-violet',
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

          <ResponsiveContainer width="100%" height={TIME_SERIES_CHART_HEIGHT}>
            <LineChart data={chartData}>
              <CartesianGrid {...CHART_STYLES.cartesianGrid} />
              <XAxis
                dataKey="date"
                stroke="rgba(255,255,255,0.25)"
                tickLine={false}
                axisLine={false}
                tick={{ fill: 'rgba(255,255,255,0.6)', fontSize: 10, fontFamily: '"IBM Plex Mono", ui-monospace, monospace' }}
              />
              <YAxis
                stroke="rgba(255,255,255,0.25)"
                tickLine={false}
                axisLine={false}
                width={32}
                tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10, fontFamily: '"IBM Plex Mono", ui-monospace, monospace' }}
              />
              <Tooltip
                contentStyle={CHART_STYLES.tooltip.contentStyle}
                itemStyle={CHART_STYLES.tooltip.itemStyle}
                labelStyle={CHART_STYLES.tooltip.labelStyle}
                cursor={CHART_STYLES.tooltip.cursor}
              />
              {series.map((s) =>
                visibleSeries[s.name] ? (
                  <Line
                    key={s.name}
                    type="monotone"
                    dataKey={s.name}
                    stroke={s.color}
                    strokeWidth={SERIES_WIDTH[s.name]}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                ) : null,
              )}
            </LineChart>
          </ResponsiveContainer>
        </Surface>
      </section>

      {/* 2. Top list + Distribution — side-by-side, equal height */}
      <section className="mb-12">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Surface className="flex h-full flex-col">
            <h2 className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
              Top destinations
            </h2>
            <TopList
              channel="maps"
              kind="count"
              items={data.topDestinations.map((d) => ({
                primary: d.destination,
                secondary: formatPlaceType(d.type),
                value: d.count,
                trend: d.trend,
              }))}
            />
          </Surface>

          <Surface className="flex h-full flex-col">
            <h2 className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
              Activity-type distribution
            </h2>
            <ChannelPie channel="maps" data={distributionData} topN={4} />
          </Surface>
        </div>
      </section>

      {/* 3. Activity by hour — full width */}
      <section className="mb-12">
        <Surface>
          <h2 className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
            Activity by hour
          </h2>
          <ChannelHistogram
            channel="maps"
            bins={data.hourlyActivity.map((h) => ({ label: h.hour, value: h.activities }))}
            unitLabel="Activities"
            height={220}
          />
        </Surface>
      </section>

      {/* 4. Trips — injected by the page so owner-mode state stays in Maps.tsx */}
      {tripsSlot}

      {/* 5. Recent events */}
      <section className="mb-12">
        <Surface>
          <h2 className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
            Last activity
          </h2>
          <div className="-mx-4 -mb-4 max-h-[600px] sm:-mx-6 sm:-mb-6 overflow-y-auto scrollbar-thin scrollbar-thumb-channel-violet/50 scrollbar-track-transparent">
            {data.lastActivities.map((activity, index) => (
              <EventRow
                key={index}
                channel="maps"
                primary={activity.location}
                secondary={formatActivityType(activity.type)}
                rightTop={formatTimeAgo(activity.time)}
                rightBottom={formatTimeOfDay(activity.time)}
                leftIcon={getActivityIcon(activity.type)}
              />
            ))}
          </div>
        </Surface>
      </section>
    </>
  );
}
