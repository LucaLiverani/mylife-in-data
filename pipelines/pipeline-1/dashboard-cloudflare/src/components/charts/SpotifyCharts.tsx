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

interface RecentTrack {
  track: string;
  artist: string;
  time: string;
  albumArt: string;
}

interface SpotifyChartsProps {
  data: SpotifyFullData;
  recentTracks: RecentTrack[];
}

export function SpotifyCharts({ data, recentTracks }: SpotifyChartsProps) {
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
              <Line type="monotone" dataKey="hours" stroke={CHART_COLORS.spotify} strokeWidth={2} dot={{ fill: CHART_COLORS.spotify, r: 3 }} activeDot={{ r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      </section>

      {/* Recent Tracks */}
      <section>
        <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
          <h2 className="text-2xl font-bold mb-6">Recently Played</h2>
          <div className="space-y-4">
            {recentTracks.slice(0, 10).map((track, index) => (
              <div
                key={index}
                className="flex items-center gap-4 p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-all"
              >
                {/* Album Art */}
                <div className="flex-shrink-0">
                  <img
                    src={track.albumArt}
                    alt={`${track.track} album art`}
                    className="w-16 h-16 rounded-md object-cover"
                  />
                </div>

                {/* Track Info */}
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-lg truncate">{track.track}</div>
                  <div className="text-sm text-white/60 truncate">{track.artist}</div>
                </div>

                {/* Time */}
                <div className="text-right flex-shrink-0">
                  <div className="text-sm text-[#1DB954]">{track.time}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </section>
    </>
  );
}
