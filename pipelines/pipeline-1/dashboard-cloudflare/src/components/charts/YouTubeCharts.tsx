import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { CHART_COLORS, CHART_STYLES, TIME_SERIES_CHART_HEIGHT, formatChartDate } from './chartConfig';

interface DailyActivityBreakdown {
  date: string;
  watched: number;
  searches: number;
  visits: number;
  subscriptions: number;
  likes: number;
  comments: number;
  shares: number;
  ads: number;
  other: number;
  totalActivities: number;
  uniqueVideos: number;
  dayName: string;
  isWeekend: boolean;
}

interface YouTubeData {
  topVideos: Array<{ rank: number; title: string; videoId: string; watchCount: number; category: string }>;
  activityTypes: Array<{ name: string; value: number; count: number }>;
  dailyActivityBreakdown: DailyActivityBreakdown[];
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
  const chartData = data.dailyActivityBreakdown.map((day) => ({
    date: formatChartDate(day.date),
    Watched: day.watched,
    Searches: day.searches,
    Visits: day.visits,
    Ads: day.ads,
    Other: day.other + day.subscriptions + day.likes + day.comments + day.shares,
  }));

  const series = [
    { name: 'Watched', color: CHART_COLORS.youtube },
    { name: 'Searches', color: '#3b82f6' },
    { name: 'Visits', color: '#10b981' },
    { name: 'Ads', color: '#f59e0b' },
    { name: 'Other', color: '#8b5cf6' },
  ] as const;

  // Calculate totals
  const totalWatched = data.dailyActivityBreakdown.reduce((a, b) => a + b.watched, 0);
  const totalSearches = data.dailyActivityBreakdown.reduce((a, b) => a + b.searches, 0);
  const totalAds = data.dailyActivityBreakdown.reduce((a, b) => a + b.ads, 0);
  const totalActivities = data.dailyActivityBreakdown.reduce((a, b) => a + b.totalActivities, 0);
  const avgPerDay = data.dailyActivityBreakdown.length > 0
    ? (totalActivities / data.dailyActivityBreakdown.length).toFixed(1)
    : '0';

  const mostActive = [
    { name: 'Watched', total: totalWatched, color: CHART_COLORS.youtube },
    { name: 'Searches', total: totalSearches, color: '#3b82f6' },
    { name: 'Ads', total: totalAds, color: '#f59e0b' },
  ].sort((a, b) => b.total - a.total)[0];

  return (
    <>
      {/* First: Daily Activity Breakdown - Full Width */}
      <section className="mb-12">
        <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
          <h2 className="text-2xl font-bold mb-6">Daily Activity Breakdown (Last 30 Days)</h2>

          {/* Stats and KPIs */}
          <div className="flex justify-between items-start mb-6">
            <div className="flex gap-8">
              <div>
                <p className="text-xs text-white/50 mb-1">Total Activities</p>
                <p className="text-2xl font-bold text-white">{totalActivities.toLocaleString()}</p>
                <p className="text-xs text-white/40">last 30 days</p>
              </div>
              <div>
                <p className="text-xs text-white/50 mb-1">Daily Average</p>
                <p className="text-2xl font-bold text-white">{avgPerDay}</p>
                <p className="text-xs text-white/40">per day</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-xs text-white/50 mb-1">Most Common</p>
              <p className="text-xl font-bold" style={{ color: mostActive.color }}>{mostActive.name}</p>
              <p className="text-xs text-white/40">{mostActive.total.toLocaleString()} activities</p>
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
                <span className="text-sm text-white/80">{s.name}</span>
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
                label={{ value: 'Activities', angle: -90, position: 'insideLeft', fill: 'rgba(255, 255, 255, 0.7)' }}
              />
              <Tooltip
                contentStyle={CHART_STYLES.tooltip.contentStyle}
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
        </Card>
      </section>

      {/* Second: Top Videos and Activity Types */}
      <section className="mb-12">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Top Videos */}
          <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
            <h2 className="text-2xl font-bold mb-6">Top 10 Videos</h2>
            <div className="space-y-3 max-h-[400px] overflow-y-auto">
              {data.topVideos.map((video, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-all"
                >
                  <div className="flex items-center gap-4 flex-1 min-w-0">
                    <div className="text-2xl font-bold text-[#FF0000] w-8">#{video.rank}</div>
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-sm truncate">{video.title}</div>
                      <div className="text-xs text-white/60">{video.category}</div>
                    </div>
                  </div>
                  <div className="text-right ml-4">
                    <div className="text-lg font-bold text-[#FF0000]">{video.watchCount}</div>
                    <div className="text-xs text-white/60">watches</div>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Activity Types */}
          <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
            <h2 className="text-2xl font-bold mb-6">Activity Types</h2>
            <div className="space-y-4 pt-4">
              {data.activityTypes.map((type, i: number) => (
                <div key={i} className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>{type.name}</span>
                    <span className="text-[#FF0000] font-semibold">{type.value}%</span>
                  </div>
                  <div className="w-full bg-white/10 rounded-full h-3">
                    <div
                      className="bg-gradient-to-r from-[#FF0000] to-[#CC0000] h-3 rounded-full transition-all duration-500"
                      style={{ width: `${type.value}%` }}
                    />
                  </div>
                  <div className="text-xs text-white/40">{type.count.toLocaleString()} activities</div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </section>

      {/* Third: Hourly Activity - Full Width */}
      <section className="mb-12">
        <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
          <h2 className="text-2xl font-bold mb-6">Activity by Hour</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data.hourlyActivity}>
              <CartesianGrid {...CHART_STYLES.cartesianGrid} />
              <XAxis
                dataKey="hour"
                stroke="#fff"
                tick={{ fill: 'rgba(255, 255, 255, 0.7)' }}
                tickLine={{ stroke: 'rgba(255, 255, 255, 0.1)' }}
              />
              <YAxis
                stroke="#fff"
                tick={{ fill: 'rgba(255, 255, 255, 0.7)' }}
                tickLine={{ stroke: 'rgba(255, 255, 255, 0.1)' }}
              />
              <Tooltip contentStyle={CHART_STYLES.tooltip.contentStyle} />
              <Bar dataKey="activities" fill={CHART_COLORS.youtube} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </section>

      {/* Fourth: Recent Videos - Full Width */}
      <section className="mb-12">
        <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
          <h2 className="text-2xl font-bold mb-6">Recent Videos</h2>
          <div className="space-y-3">
            {data.recentVideos.map((video, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-all"
              >
                <div className="flex items-center gap-4 flex-1 min-w-0">
                  <div className="text-2xl">{video.isFromAds ? '📺' : '▶️'}</div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-sm truncate">{video.title}</div>
                    <div className="text-xs text-white/60">
                      {video.isFromAds ? 'From Ads' : 'Watched'}
                    </div>
                  </div>
                </div>
                <div className="text-right ml-4">
                  <div className="text-sm font-semibold text-[#FF0000]">{video.relativeTime}</div>
                  <div className="text-xs text-white/60">{video.timeOfDay}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </section>
    </>
  );
}
