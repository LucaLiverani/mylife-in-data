import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { CHART_COLORS, CHART_STYLES, TIME_SERIES_CHART_HEIGHT, formatChartDate } from './chartConfig';

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
        <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
          <h2 className="text-2xl font-bold mb-6">Daily Watch Time (Last 30 Days)</h2>

          {/* Stats and KPIs */}
          <div className="flex justify-between items-start mb-6">
            <div className="flex gap-8">
              <div>
                <p className="text-xs text-white/50 mb-1">Total Watch Time</p>
                <p className="text-2xl font-bold text-white">{totalHours.toFixed(1)}h</p>
                <p className="text-xs text-white/40">last 30 days</p>
              </div>
              <div>
                <p className="text-xs text-white/50 mb-1">Daily Average</p>
                <p className="text-2xl font-bold text-white">{avgHoursPerDay}h</p>
                <p className="text-xs text-white/40">per day</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-xs text-white/50 mb-1">Most Time On</p>
              <p className="text-xl font-bold" style={{ color: mostActive.color }}>{mostActive.name}</p>
              <p className="text-xs text-white/40">{mostActive.total.toFixed(1)}h total</p>
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
                label={{ value: 'Hours', angle: -90, position: 'insideLeft', fill: 'rgba(255, 255, 255, 0.7)' }}
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

      {/* Second: Top Channels and Category Breakdown */}
      <section className="mb-12">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Top Channels */}
          <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
            <h2 className="text-2xl font-bold mb-6">Top Channels</h2>
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={data.topChannels.slice(0, 10)} layout="vertical">
                <CartesianGrid {...CHART_STYLES.cartesianGrid} />
                <XAxis
                  type="number"
                  stroke="#fff"
                  label={{ value: 'Hours', position: 'insideBottom', offset: -5, fill: 'rgba(255, 255, 255, 0.7)' }}
                />
                <YAxis
                  type="category"
                  dataKey="channelTitle"
                  stroke="#fff"
                  width={120}
                  tick={{ fontSize: 12 }}
                />
                <Tooltip
                  contentStyle={CHART_STYLES.tooltip.contentStyle}
                  formatter={(value: number, name: string, props: any) => [
                    `${value.toFixed(1)}h (${props.payload.watchCount} videos)`,
                    'Watch Time'
                  ]}
                />
                <Bar
                  dataKey="watchTimeHours"
                  fill={CHART_COLORS.youtube}
                  radius={[0, 4, 4, 0]}
                  label={{
                    position: 'right',
                    fill: '#fff',
                    fontSize: 12,
                    formatter: (value: number) => `${value.toFixed(1)}h`
                  }}
                />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          {/* Category Breakdown */}
          <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
            <h2 className="text-2xl font-bold mb-6">Category Distribution</h2>
            <ResponsiveContainer width="100%" height={350}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={(entry: unknown) => {
                    const data = entry as { name: string; value: number; percent?: number };
                    return `${data.name} ${data.percent ? (data.percent * 100).toFixed(0) : 0}%`;
                  }}
                  outerRadius={120}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {pieData.map((entry, index: number) => (
                    <Cell key={`cell-${index}`} fill={CHART_COLORS.youtubeShades[index % 5]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={CHART_STYLES.tooltip.contentStyle}
                  itemStyle={{ color: '#fff' }}
                  labelStyle={{ color: '#fff' }}
                />
              </PieChart>
            </ResponsiveContainer>
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
          <div className="space-y-3 max-h-[600px] overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-[#FF0000]/50 scrollbar-track-transparent">
            {data.recentVideos.map((video, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-all"
              >
                <div className="flex items-center gap-4 flex-1 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-[#FF0000]/20 flex items-center justify-center flex-shrink-0">
                    {video.isFromAds ? (
                      <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none">
                        <rect x="2" y="5" width="12" height="6" rx="1" fill="#FF0000"/>
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none">
                        <path d="M5 3L13 8L5 13V3Z" fill="#FF0000"/>
                      </svg>
                    )}
                  </div>
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
