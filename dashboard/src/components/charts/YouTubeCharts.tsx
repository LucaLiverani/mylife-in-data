import { useState } from 'react';
import { Surface } from '@/components/Surface';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { CHART_COLORS, CHART_STYLES, TIME_SERIES_CHART_HEIGHT, formatChartDate } from './chartConfig';
import { ChannelPie } from './ChannelPie';
import { TopList } from './TopList';
import { ChannelHistogram } from './ChannelHistogram';

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
  const [visibleSeries, setVisibleSeries] = useState({
    Watched: true,
    Searches: true,
    Visits: false,
    Ads: true,
    Other: false,
  });

  const toggleSeries = (series: keyof typeof visibleSeries) => {
    setVisibleSeries(prev => ({ ...prev, [series]: !prev[series] }));
  };

  // Transform data for chart
  const chartData = data.dailyWatchTimeBreakdown.map((day) => ({
    date: formatChartDate(day.date),
    Watched: day.watchedHours,
    Searches: day.searchesHours,
    Visits: day.visitsHours,
    Ads: day.adsHours,
    Other: day.otherHours,
  }));

  const series = [
    { name: 'Watched', color: CHART_COLORS.youtube },
    { name: 'Searches', color: '#3b82f6' },
    { name: 'Visits', color: '#10b981' },
    { name: 'Ads', color: '#f59e0b' },
    { name: 'Other', color: '#8b5cf6' },
  ] as const;

  // Calculate totals in hours
  const totalWatchedHours = data.dailyWatchTimeBreakdown.reduce((a, b) => a + b.watchedHours, 0);
  const totalSearchesHours = data.dailyWatchTimeBreakdown.reduce((a, b) => a + b.searchesHours, 0);
  const totalAdsHours = data.dailyWatchTimeBreakdown.reduce((a, b) => a + b.adsHours, 0);
  const totalHours = data.dailyWatchTimeBreakdown.reduce((a, b) => a + b.totalHours, 0);
  const avgHoursPerDay = data.dailyWatchTimeBreakdown.length > 0
    ? (totalHours / data.dailyWatchTimeBreakdown.length).toFixed(1)
    : '0';

  const mostActive = [
    { name: 'Watched', total: totalWatchedHours, color: CHART_COLORS.youtube },
    { name: 'Searches', total: totalSearchesHours, color: '#3b82f6' },
    { name: 'Ads', total: totalAdsHours, color: '#f59e0b' },
  ].sort((a, b) => b.total - a.total)[0];

  // Prepare data for pie chart
  const pieData = data.categoryBreakdown.slice(0, 5).map(cat => ({
    name: cat.name,
    value: cat.watchCount,
    watchCount: cat.watchCount,
    watchTime: cat.watchTime,
  }));

  return (
    <>
      {/* First: Daily Watch Time Breakdown - Full Width */}
      <section className="mb-12">
        <Surface className="p-6">
          <h2 className="text-2xl font-bold mb-6">Daily Watch Time (Last 30 Days)</h2>

          {/* Stats and KPIs */}
          <div className="flex justify-between items-start mb-6">
            <div className="flex gap-8">
              <div>
                <p className="text-xs text-signal-white/50 mb-1">Total Watch Time</p>
                <p className="text-2xl font-bold text-signal-white">{totalHours.toFixed(1)}h</p>
                <p className="text-xs text-signal-white/40">last 30 days</p>
              </div>
              <div>
                <p className="text-xs text-signal-white/50 mb-1">Daily Average</p>
                <p className="text-2xl font-bold text-signal-white">{avgHoursPerDay}h</p>
                <p className="text-xs text-signal-white/40">per day</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-xs text-signal-white/50 mb-1">Most Time On</p>
              <p className="text-xl font-bold" style={{ color: mostActive.color }}>{mostActive.name}</p>
              <p className="text-xs text-signal-white/40">{mostActive.total.toFixed(1)}h total</p>
            </div>
          </div>

          {/* Legend */}
          <div className="flex flex-wrap gap-4 mb-4">
            {series.map((s) => (
              <button
                key={s.name}
                onClick={() => toggleSeries(s.name)}
                className="flex items-center gap-2 transition-opacity"
                style={{ opacity: visibleSeries[s.name] ? 1 : 0.4 }}
              >
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: s.color }}
                />
                <span className="text-sm text-signal-white/80">{s.name}</span>
              </button>
            ))}
          </div>

          {/* Chart */}
          <ResponsiveContainer width="100%" height={TIME_SERIES_CHART_HEIGHT}>
            <LineChart data={chartData}>
              <CartesianGrid {...CHART_STYLES.cartesianGrid} />
              <XAxis
                dataKey="date"
                {...CHART_STYLES.timeSeriesXAxis}
              />
              <YAxis
                stroke="#fff"
                tick={{ fill: 'rgba(255, 255, 255, 0.7)' }}
                tickLine={{ stroke: 'rgba(255, 255, 255, 0.1)' }}
                label={{ value: 'Hours', angle: -90, position: 'insideLeft', fill: 'rgba(255, 255, 255, 0.7)' }}
              />
              <Tooltip
                contentStyle={CHART_STYLES.tooltip.contentStyle} itemStyle={CHART_STYLES.tooltip.itemStyle} labelStyle={CHART_STYLES.tooltip.labelStyle}
                cursor={CHART_STYLES.tooltip.cursor}
              />
              {visibleSeries.Watched && (
                <Line
                  type="monotone"
                  dataKey="Watched"
                  stroke={CHART_COLORS.youtube}
                  strokeWidth={2}
                  dot={{ fill: CHART_COLORS.youtube, r: 3 }}
                  activeDot={{ r: 5 }}
                />
              )}
              {visibleSeries.Searches && (
                <Line
                  type="monotone"
                  dataKey="Searches"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={{ fill: '#3b82f6', r: 3 }}
                  activeDot={{ r: 5 }}
                />
              )}
              {visibleSeries.Visits && (
                <Line
                  type="monotone"
                  dataKey="Visits"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={{ fill: '#10b981', r: 3 }}
                  activeDot={{ r: 5 }}
                />
              )}
              {visibleSeries.Ads && (
                <Line
                  type="monotone"
                  dataKey="Ads"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  dot={{ fill: '#f59e0b', r: 3 }}
                  activeDot={{ r: 5 }}
                />
              )}
              {visibleSeries.Other && (
                <Line
                  type="monotone"
                  dataKey="Other"
                  stroke="#8b5cf6"
                  strokeWidth={2}
                  dot={{ fill: '#8b5cf6', r: 3 }}
                  activeDot={{ r: 5 }}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </Surface>
      </section>

      {/* Second: Top Channels and Category Breakdown */}
      <section className="mb-12">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Top Channels */}
          <Surface>
            <h2 className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
              Top Channels
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

          {/* Category Breakdown */}
          <Surface>
            <h2 className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
              Category Distribution
            </h2>
            <ChannelPie channel="youtube" data={pieData} height={280} topN={5} />
          </Surface>
        </div>
      </section>

      {/* Third: Hourly Activity - Full Width */}
      <section className="mb-12">
        <Surface>
          <h2 className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
            Activity by Hour
          </h2>
          <ChannelHistogram
            channel="youtube"
            bins={data.hourlyActivity.map((h) => ({ label: h.hour, value: h.activities }))}
            unitLabel="Activities"
            height={260}
          />
        </Surface>
      </section>

      {/* Fourth: Recent Videos - Full Width */}
      <section className="mb-12">
        <Surface className="p-6">
          <h2 className="text-2xl font-bold mb-6">Recent Videos</h2>
          <div className="space-y-3 max-h-[600px] overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-channel-red/50 scrollbar-track-transparent">
            {data.recentVideos.map((video, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-3 border-b border-signal-white/5 last:border-b-0 hover:bg-signal-white/[0.03] transition-colors duration-150 ease-snap"
              >
                <div className="flex items-center gap-4 flex-1 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-channel-red/20 flex items-center justify-center flex-shrink-0">
                    {video.isFromAds ? (
                      <svg className="size-4 text-channel-red" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                        <rect x="2" y="5" width="12" height="6" rx="1" fill="currentColor"/>
                      </svg>
                    ) : (
                      <svg className="size-4 text-channel-red" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                        <path d="M5 3L13 8L5 13V3Z" fill="currentColor"/>
                      </svg>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-sm truncate">{video.title}</div>
                    <div className="text-xs text-signal-white/60">
                      {video.isFromAds ? 'From Ads' : 'Watched'}
                    </div>
                  </div>
                </div>
                <div className="text-right ml-4">
                  <div className="text-sm font-semibold text-channel-red">{video.relativeTime}</div>
                  <div className="text-xs text-signal-white/60">{video.timeOfDay}</div>
                </div>
              </div>
            ))}
          </div>
        </Surface>
      </section>
    </>
  );
}
