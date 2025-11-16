import { Card } from '@/components/ui/card';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line } from 'recharts';
import { CHART_COLORS, CHART_STYLES, TIME_SERIES_CHART_HEIGHT, formatDetailedDate } from './chartConfig';

// Define the structure of the data prop
interface SpotifyFullData {
  kpis: {
    totalTime: string;
    songsStreamed: string;
    uniqueArtists: string;
    avgDaily: string;
  };
  topArtists: Array<{ rank: number; name: string; plays: number; hours: number; genre: string }>;
  genres: Array<{ name: string; value: number }>;
  timeSeries: {
    dates: string[];
    values: number[];
  };
}

interface SpotifyChartsProps {
  data: SpotifyFullData;
}

export function SpotifyCharts({ data }: SpotifyChartsProps) {
  return (
    <>
      {/* Charts Section */}
      <section className="mb-12">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Top Artists */}
          <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
            <h2 className="text-2xl font-bold mb-6">Top Artists</h2>
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={data.topArtists} layout="vertical">
                <CartesianGrid {...CHART_STYLES.cartesianGrid} />
                <XAxis type="number" stroke="#fff" />
                <YAxis type="category" dataKey="name" stroke="#fff" width={120} />
                <Tooltip contentStyle={CHART_STYLES.tooltip.contentStyle} />
                <Bar dataKey="plays" fill={CHART_COLORS.spotify} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          {/* Genre Distribution */}
          <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
            <h2 className="text-2xl font-bold mb-6">Genre Distribution</h2>
            <ResponsiveContainer width="100%" height={350}>
              <PieChart>
                <Pie
                  data={data.genres}
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
                  {data.genres.map((entry, index: number) => (
                    <Cell key={`cell-${index}`} fill={CHART_COLORS.spotifyShades[index % 5]} />
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

      {/* Listening Time Trend */}
      <section className="mb-12">
        <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
          <h2 className="text-2xl font-bold mb-6">Daily Listening Hours</h2>
          <ResponsiveContainer width="100%" height={TIME_SERIES_CHART_HEIGHT}>
            <LineChart data={data.timeSeries.dates.map((date: string, i: number) => ({
              date,
              hours: data.timeSeries.values[i]
            }))}>
              <CartesianGrid {...CHART_STYLES.cartesianGrid} />
              <XAxis
                dataKey="date"
                {...CHART_STYLES.timeSeriesXAxis}
                tickFormatter={(value) => formatDetailedDate(value)}
              />
              <YAxis stroke="#fff" />
              <Tooltip
                contentStyle={CHART_STYLES.tooltip.contentStyle}
                labelFormatter={(value) => `Date: ${value}`}
              />
              <Line type="monotone" dataKey="hours" stroke={CHART_COLORS.spotify} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      </section>

      {/* Top Artists Details */}
      <section>
        <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
          <h2 className="text-2xl font-bold mb-6">Artist Details</h2>
          <div className="space-y-4">
            {data.topArtists.map((artist) => (
              <div
                key={artist.rank}
                className="flex items-center justify-between p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-all"
              >
                <div className="flex items-center gap-4">
                  <div className="text-2xl font-bold text-[#1DB954] w-8">#{artist.rank}</div>
                  <div>
                    <div className="font-semibold text-lg">{artist.name}</div>
                    <div className="text-sm text-white/60">{artist.genre}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-semibold">{artist.plays.toLocaleString()} plays</div>
                  <div className="text-sm text-white/60">{artist.hours} hours</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </section>
    </>
  );
}
