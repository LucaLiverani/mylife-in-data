import { Card } from '@/components/ui/card';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import { CHART_COLORS, CHART_STYLES, TIME_SERIES_CHART_HEIGHT, formatChartDate } from './chartConfig';

interface GoogleData {
  timeOfDay: Array<{ hour: string; searches: number }>;
  categories: Array<{ name: string; value: number }>;
  dailySearches: Array<{ date: string; searches: number }>;
  topSearches: Array<{ query: string; count: number }>;
}

export function GoogleCharts({ data }: { data: GoogleData }) {
  return (
    <>
      {/* Charts Section */}
      <section className="mb-12">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Search Time Distribution */}
          <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
            <h2 className="text-2xl font-bold mb-6">Search Activity by Time</h2>
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={data.timeOfDay}>
                <CartesianGrid {...CHART_STYLES.cartesianGrid} />
                <XAxis dataKey="hour" stroke="#fff" />
                <YAxis stroke="#fff" />
                <Tooltip contentStyle={CHART_STYLES.tooltip.contentStyle} />
                <Bar dataKey="searches" fill={CHART_COLORS.google} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          {/* Category Distribution */}
          <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
            <h2 className="text-2xl font-bold mb-6">Search Categories</h2>
            <div className="space-y-4 pt-8">
              {data.categories.map((cat, i: number) => (
                <div key={i} className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>{cat.name}</span>
                    <span className="text-[#4285F4] font-semibold">{cat.value}%</span>
                  </div>
                  <div className="w-full bg-white/10 rounded-full h-3">
                    <div
                      className="bg-gradient-to-r from-[#4285F4] to-[#34A853] h-3 rounded-full transition-all duration-500"
                      style={{ width: `${cat.value}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </section>

      {/* Daily Search Trend */}
      <section className="mb-12">
        <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
          <h2 className="text-2xl font-bold mb-6">Daily Search Volume (Last 30 Days)</h2>
          <ResponsiveContainer width="100%" height={TIME_SERIES_CHART_HEIGHT}>
            <LineChart data={data.dailySearches}>
              <CartesianGrid {...CHART_STYLES.cartesianGrid} />
              <XAxis
                dataKey="date"
                {...CHART_STYLES.timeSeriesXAxis}
                tickFormatter={(value) => formatChartDate(value)}
              />
              <YAxis stroke="#fff" />
              <Tooltip
                contentStyle={CHART_STYLES.tooltip.contentStyle}
                labelFormatter={(value) => `Date: ${value}`}
              />
              <Line type="monotone" dataKey="searches" stroke={CHART_COLORS.google} strokeWidth={2} dot={{ fill: CHART_COLORS.google, r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      </section>

      {/* Top Searches */}
      <section>
        <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
          <h2 className="text-2xl font-bold mb-6">Top Searches</h2>
          <div className="space-y-3">
            {data.topSearches.map((search, i: number) => (
              <div
                key={i}
                className="flex items-center justify-between p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-all"
              >
                <div className="flex items-center gap-4">
                  <div className="text-2xl font-bold text-[#4285F4] w-8">#{i + 1}</div>
                  <div className="font-mono text-sm text-white/90">{search.query}</div>
                </div>
                <div className="text-right">
                  <div className="font-semibold text-[#4285F4]">{search.count} times</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </section>
    </>
  );
}
