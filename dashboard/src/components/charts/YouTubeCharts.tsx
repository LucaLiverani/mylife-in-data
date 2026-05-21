import { useState } from 'react';
import { Surface } from '@/components/Surface';
import { EventRow } from '@/components/EventRow';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { CHART_STYLES, TIME_SERIES_CHART_HEIGHT, formatChartDate } from './chartConfig';
import { CHANNEL_HEX } from '@/lib/channels';
import { ChannelPie } from './ChannelPie';
import { TopList } from './TopList';
import { ChannelHistogram } from './ChannelHistogram';
import { cn } from '@/lib/utils';

// Sub-series palette for YouTube. The Channel-Lane Rule says channel-red
// owns the page — so the *primary* series (Watched) is channel-red. Other
// series sit on a signal-white scale so they read as "context" not "competitor."
// Ads is semantically negative → trace-down (a warning color the design system
// already owns, distinct from channel-red).
const SERIES_COLOR = {
  Watched:  CHANNEL_HEX.youtube,    // #FF0000 — channel identity, primary
  Searches: 'rgba(255,255,255,0.75)',
  Visits:   'rgba(255,255,255,0.45)',
  Ads:      '#F87171',              // trace-down — "this is the interruption"
  Other:    'rgba(255,255,255,0.22)',
} as const;
const SERIES_WIDTH: Record<YtSeries, number> = {
  Watched:  2.5,
  Searches: 1.5,
  Visits:   1.5,
  Ads:      2,
  Other:    1.25,
};

type YtSeries = 'Watched' | 'Searches' | 'Visits' | 'Ads' | 'Other';

interface DailyWatchTimeBreakdown {
  date: string;
  watchedHours: number;
  searchesHours: number;
  visitsHours: number;
  adsHours: number;
  otherHours: number;
  totalHours: number;
  watchedCount: number;
  searchesCount: number;
  visitsCount: number;
  adsCount: number;
  dayName: string;
  isWeekend: boolean;
}

interface YouTubeData {
  topChannels: Array<{
    channelId: string;
    channelTitle: string;
    watchCount: number;
    totalWatchTime: string;
    watchTimeHours: number;
    category: string;
    uniqueVideos: number;
    trend?: number[];
  }>;
  categoryBreakdown: Array<{
    name: string;
    watchCount: number;
    watchTime: string;
    watchPercentage: number;
    timePercentage: number;
    uniqueChannels: number;
  }>;
  dailyWatchTimeBreakdown: DailyWatchTimeBreakdown[];
  recentVideos: Array<{ title: string; time: string; relativeTime: string; timeOfDay: string; isFromAds: boolean }>;
  hourlyActivity: Array<{ hour: string; activities: number }>;
}

export function YouTubeCharts({ data }: { data: YouTubeData }) {
  // All primary series default-on; "Other" stays off (long-tail noise).
  const [visibleSeries, setVisibleSeries] = useState<Record<YtSeries, boolean>>({
    Watched:  true,
    Searches: true,
    Visits:   true,
    Ads:      true,
    Other:    false,
  });

  const toggleSeries = (s: YtSeries) => setVisibleSeries(p => ({ ...p, [s]: !p[s] }));

  const chartData = data.dailyWatchTimeBreakdown.map((day) => ({
    date: formatChartDate(day.date),
    Watched:  day.watchedHours,
    Searches: day.searchesHours,
    Visits:   day.visitsHours,
    Ads:      day.adsHours,
    Other:    day.otherHours,
  }));

  const series: Array<{ name: YtSeries; color: string }> = [
    { name: 'Watched',  color: SERIES_COLOR.Watched  },
    { name: 'Searches', color: SERIES_COLOR.Searches },
    { name: 'Visits',   color: SERIES_COLOR.Visits   },
    { name: 'Ads',      color: SERIES_COLOR.Ads      },
    { name: 'Other',    color: SERIES_COLOR.Other    },
  ];

  const pieData = data.categoryBreakdown.slice(0, 5).map(cat => ({
    name:  cat.name,
    value: cat.watchCount,
  }));

  return (
    <>
      {/* Daily Watch Time Breakdown — mono-uppercase header, no embedded KPI strip */}
      <section className="mb-12">
        <Surface>
          <h2 className="mb-4 font-mono text-xs uppercase tracking-wider text-signal-white/60">
            Daily watch time · last 30 days
          </h2>

          {/* Mono-uppercase toggle row */}
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
                    'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-channel-red',
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
                tickFormatter={(v: number) => `${v}h`}
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

      <section className="mb-12">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Surface className="flex h-full flex-col">
            <h2 className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
              Top channels
            </h2>
            <TopList
              channel="youtube"
              kind="hours"
              items={data.topChannels.map((c) => ({
                primary: c.channelTitle,
                secondary: c.category || `${c.watchCount} videos`,
                value: c.watchTimeHours,
                trend: c.trend,
              }))}
            />
          </Surface>

          <Surface className="flex h-full flex-col">
            <h2 className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
              Category distribution
            </h2>
            <ChannelPie channel="youtube" data={pieData} topN={5} />
          </Surface>
        </div>
      </section>

      <section className="mb-12">
        <Surface>
          <h2 className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
            Activity by hour
          </h2>
          <ChannelHistogram
            channel="youtube"
            bins={data.hourlyActivity.map((h) => ({ label: h.hour, value: h.activities }))}
            unitLabel="Activities"
            height={220}
          />
        </Surface>
      </section>

      <section className="mb-12">
        <Surface>
          <h2 className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
            Recent videos
          </h2>
          <div className="-mx-6 -mb-6 max-h-[600px] overflow-y-auto scrollbar-thin scrollbar-thumb-channel-red/50 scrollbar-track-transparent">
            {data.recentVideos.map((video, index) => (
              <EventRow
                key={index}
                channel="youtube"
                primary={video.title}
                secondary={video.isFromAds ? 'From Ads' : 'Watched'}
                rightTop={video.relativeTime}
                rightBottom={video.timeOfDay}
                leftIcon={
                  video.isFromAds ? (
                    <svg className="size-4" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                      <rect x="2" y="5" width="12" height="6" rx="1" fill="currentColor" />
                    </svg>
                  ) : (
                    <svg className="size-4" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                      <path d="M5 3L13 8L5 13V3Z" fill="currentColor" />
                    </svg>
                  )
                }
              />
            ))}
          </div>
        </Surface>
      </section>
    </>
  );
}
