import { Card } from '@/components/ui/card';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { CHART_COLORS, CHART_STYLES, TIME_SERIES_CHART_HEIGHT, formatChartDate } from './chartConfig';

interface YouTubeData {
  topChannels: Array<{ name: string; videos: number; category: string; hours: number }>;
  categories: Array<{ name: string; value: number }>;
  watchTime: Array<{ date: string; hours: number }>;
}

export function YouTubeCharts({ data }: { data: YouTubeData }) {
  return (
    <>
      {/* Charts Section */}
      <section className="mb-12">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Top Channels */}
          <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
            <h2 className="text-2xl font-bold mb-6">Top Channels</h2>
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={data.topChannels} layout="vertical">
                <CartesianGrid {...CHART_STYLES.cartesianGrid} />
                <XAxis type="number" stroke="#fff" />
                <YAxis type="category" dataKey="name" stroke="#fff" width={140} />
                <Tooltip contentStyle={CHART_STYLES.tooltip.contentStyle} />
                <Bar dataKey="videos" fill={CHART_COLORS.youtube} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          {/* Category Distribution */}
          <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
            <h2 className="text-2xl font-bold mb-6">Content Categories</h2>
            <div className="space-y-4 pt-8">
              {data.categories.map((cat, i: number) => (
                <div key={i} className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>{cat.name}</span>
                    <span className="text-[#FF0000] font-semibold">{cat.value}%</span>
                  </div>
                  <div className="w-full bg-white/10 rounded-full h-3">
                    <div
                      className="bg-gradient-to-r from-[#FF0000] to-[#CC0000] h-3 rounded-full transition-all duration-500"
                      style={{ width: `${cat.value}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </section>

      {/* Watch Time Trend */}
      <section className="mb-12">
        <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
          <h2 className="text-2xl font-bold mb-6">Daily Watch Time (Last 30 Days)</h2>
          <ResponsiveContainer width="100%" height={TIME_SERIES_CHART_HEIGHT}>
            <AreaChart data={data.watchTime}>
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
              <Area type="monotone" dataKey="hours" stroke={CHART_COLORS.youtube} fill="#FF000040" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      </section>

      {/* Channel Details */}
      <section>
        <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
          <h2 className="text-2xl font-bold mb-6">Channel Details</h2>
          <div className="space-y-4">
            {data.topChannels.map((channel, i: number) => (
              <div
                key={i}
                className="flex items-center justify-between p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-all"
              >
                <div className="flex items-center gap-4">
                  <div className="text-2xl font-bold text-[#FF0000] w-8">#{i + 1}</div>
                  <div>
                    <div className="font-semibold text-lg">{channel.name}</div>
                    <div className="text-sm text-white/60">{channel.category}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-semibold">{channel.videos} videos</div>
                  <div className="text-sm text-white/60">{channel.hours} hours</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </section>
    </>
  );
}
