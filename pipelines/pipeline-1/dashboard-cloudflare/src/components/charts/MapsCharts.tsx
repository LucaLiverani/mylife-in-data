import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { CHART_COLORS, CHART_STYLES, TIME_SERIES_CHART_HEIGHT, formatChartDate } from './chartConfig';

interface MapsData {
  hourlyActivity: Array<{ hour: string; activities: number }>;
  lastActivities: Array<{ time: string; location: string; type: string; timeOfDay: string }>;
  topDestinations: Array<{ destination: string; count: number; type: string }>;
  dailyActivity: Array<{ date: string; directions: number; searches: number; explorations: number; other: number }>;
}

// Helper to format activity type for display
const formatActivityType = (type: string): string => {
  const typeMap: Record<string, string> = {
    'directions': 'Directions',
    'search': 'Search',
    'explore': 'Explore',
    'place_view': 'Place View',
    'app_usage': 'App Usage',
    'view': 'View',
    'review': 'Review',
    'save': 'Save',
    'other': 'Other',
  };
  return typeMap[type] || type;
};

// Helper to get icon for activity type
const getActivityIcon = (type: string): string => {
  const iconMap: Record<string, string> = {
    'directions': '🧭',
    'search': '🔍',
    'explore': '🗺️',
    'place_view': '👁️',
    'app_usage': '📱',
    'view': '👀',
    'review': '⭐',
    'save': '💾',
    'other': '📍',
  };
  return iconMap[type] || '📍';
};

// Helper to format time ago
const formatTimeAgo = (timeString: string): string => {
  const date = new Date(timeString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
};

export function MapsCharts({ data }: { data: MapsData }) {
  const [visibleSeries, setVisibleSeries] = useState({
    Directions: true,
    Searches: true,
    Explorations: true,
    Other: true,
  });

  const toggleSeries = (series: keyof typeof visibleSeries) => {
    setVisibleSeries(prev => ({ ...prev, [series]: !prev[series] }));
  };

  // Transform data for chart
  const chartData = data.dailyActivity.map((d) => ({
    date: formatChartDate(d.date),
    Directions: Number(d.directions) || 0,
    Searches: Number(d.searches) || 0,
    Explorations: Number(d.explorations) || 0,
    Other: Number(d.other) || 0,
  }));

  const series = [
    { name: 'Directions', color: '#10b981' },
    { name: 'Searches', color: '#3b82f6' },
    { name: 'Explorations', color: '#f59e0b' },
    { name: 'Other', color: '#8b5cf6' },
  ] as const;

  // Calculate totals
  const totalDirections = data.dailyActivity.reduce((a, b) => a + Number(b.directions), 0);
  const totalSearches = data.dailyActivity.reduce((a, b) => a + Number(b.searches), 0);
  const totalExplorations = data.dailyActivity.reduce((a, b) => a + Number(b.explorations), 0);
  const totalOther = data.dailyActivity.reduce((a, b) => a + Number(b.other), 0);
  const totalActivities = totalDirections + totalSearches + totalExplorations + totalOther;
  const avgPerDay = data.dailyActivity.length > 0 ? Math.round(totalActivities / data.dailyActivity.length) : 0;

  const mostActive = [
    { name: 'Directions', total: totalDirections, color: '#10b981' },
    { name: 'Searches', total: totalSearches, color: '#3b82f6' },
    { name: 'Explorations', total: totalExplorations, color: '#f59e0b' },
    { name: 'Other', total: totalOther, color: '#8b5cf6' },
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
                <p className="text-2xl font-bold text-white">{avgPerDay.toLocaleString()}</p>
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
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="colorDirections" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                </linearGradient>
                <linearGradient id="colorSearches" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                </linearGradient>
                <linearGradient id="colorExplorations" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#f59e0b" stopOpacity={0}/>
                </linearGradient>
                <linearGradient id="colorOther" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0}/>
                </linearGradient>
              </defs>
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
              {visibleSeries.Directions && (
                <Area
                  type="monotone"
                  dataKey="Directions"
                  stackId="1"
                  stroke="#10b981"
                  strokeWidth={2}
                  fill="url(#colorDirections)"
                  dot={{ fill: '#10b981', r: 3 }}
                  activeDot={{ r: 5 }}
                />
              )}
              {visibleSeries.Searches && (
                <Area
                  type="monotone"
                  dataKey="Searches"
                  stackId="1"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  fill="url(#colorSearches)"
                  dot={{ fill: '#3b82f6', r: 3 }}
                  activeDot={{ r: 5 }}
                />
              )}
              {visibleSeries.Explorations && (
                <Area
                  type="monotone"
                  dataKey="Explorations"
                  stackId="1"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  fill="url(#colorExplorations)"
                  dot={{ fill: '#f59e0b', r: 3 }}
                  activeDot={{ r: 5 }}
                />
              )}
              {visibleSeries.Other && (
                <Area
                  type="monotone"
                  dataKey="Other"
                  stackId="1"
                  stroke="#8b5cf6"
                  strokeWidth={2}
                  fill="url(#colorOther)"
                  dot={{ fill: '#8b5cf6', r: 3 }}
                  activeDot={{ r: 5 }}
                />
              )}
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      </section>

      {/* Second: Top Destinations and Hourly Activity */}
      <section className="mb-12">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Top Destinations */}
          <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
            <h2 className="text-2xl font-bold mb-6">Top 10 Destinations</h2>
            <div className="space-y-3 max-h-[300px] overflow-y-auto">
              {data.topDestinations.map((dest, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-all"
                >
                  <div className="flex items-center gap-4 flex-1 min-w-0">
                    <div className="text-2xl font-bold text-[#A855F7] w-8">#{index + 1}</div>
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-sm truncate">{dest.destination}</div>
                      <div className="text-xs text-white/60">
                        {dest.type === 'search' ? 'Search' : 'Directions'}
                      </div>
                    </div>
                  </div>
                  <div className="text-right ml-4">
                    <div className="text-lg font-bold text-[#A855F7]">{dest.count}</div>
                    <div className="text-xs text-white/60">times</div>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Activity by Hour */}
          <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
            <h2 className="text-2xl font-bold mb-6">Activity by Hour</h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data.hourlyActivity}>
                <CartesianGrid {...CHART_STYLES.cartesianGrid} />
                <XAxis dataKey="hour" stroke="#fff" />
                <YAxis stroke="#fff" />
                <Tooltip contentStyle={CHART_STYLES.tooltip.contentStyle} />
                <Bar dataKey="activities" fill={CHART_COLORS.maps} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </div>
      </section>

      {/* Third: Last Activity - Full Width */}
      <section className="mb-12">
        <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
          <h2 className="text-2xl font-bold mb-6">Last Activity</h2>
          <div className="space-y-3">
            {data.lastActivities.map((activity, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-all"
              >
                <div className="flex items-center gap-4 flex-1 min-w-0">
                  <div className="text-2xl">{getActivityIcon(activity.type)}</div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-sm truncate">{activity.location}</div>
                    <div className="text-xs text-white/60">{formatActivityType(activity.type)}</div>
                  </div>
                </div>
                <div className="text-right ml-4">
                  <div className="text-sm font-semibold text-[#A855F7]">{formatTimeAgo(activity.time)}</div>
                  <div className="text-xs text-white/60">{activity.timeOfDay}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </section>
    </>
  );
}
