import { Surface } from '@/components/Surface';
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import { CHART_COLORS, CHART_STYLES, TIME_SERIES_CHART_HEIGHT, formatDetailedDate } from './chartConfig';
import { ChannelPie } from './ChannelPie';
import { TopList } from './TopList';
import { formatEventTime } from '@/lib/format';

// Define the structure of the data prop
interface SpotifyFullData {
  kpis: {
    totalTime: string;
    songsStreamed: string;
    uniqueArtists: string;
    avgDaily: string;
  };
  topArtists: Array<{ rank: number; name: string; plays: number; hours: number; genre: string; trend?: number[] }>;
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
          <Surface>
            <h2 className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
              Top Artists
            </h2>
            <TopList
              channel="spotify"
              kind="hours"
              items={data.topArtists.map((a) => ({
                primary: a.name,
                secondary: a.genre || `${a.plays} plays`,
                value: a.hours,
                trend: a.trend,
              }))}
            />
          </Surface>

          {/* Genre Distribution */}
          <Surface>
            <h2 className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
              Genre Distribution
            </h2>
            <ChannelPie channel="spotify" data={data.genres} height={280} topN={5} />
          </Surface>
        </div>
      </section>

      {/* Listening Time Trend */}
      <section className="mb-12">
        <Surface className="p-6">
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
                contentStyle={CHART_STYLES.tooltip.contentStyle} itemStyle={CHART_STYLES.tooltip.itemStyle} labelStyle={CHART_STYLES.tooltip.labelStyle}
                labelFormatter={(value) => `Date: ${value}`}
              />
              <Line type="monotone" dataKey="hours" stroke={CHART_COLORS.spotify} strokeWidth={2} dot={{ fill: CHART_COLORS.spotify, r: 3 }} activeDot={{ r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        </Surface>
      </section>

      {/* Recent Tracks */}
      <section>
        <Surface className="p-6">
          <h2 className="text-2xl font-bold mb-6">Recently Played</h2>
          <div className="space-y-4">
            {recentTracks.slice(0, 10).map((track, index) => (
              <div
                key={index}
                className="flex items-center gap-4 p-3 border-b border-signal-white/5 last:border-b-0 hover:bg-signal-white/[0.03] transition-colors duration-150 ease-snap"
              >
                {/* Album Art */}
                <div className="flex-shrink-0">
                  <img
                    src={track.albumArt}
                    alt={`${track.track} album art`}
                    loading="lazy"
                    decoding="async"
                    className="w-16 h-16 rounded-md object-cover"
                  />
                </div>

                {/* Track Info */}
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-lg truncate">{track.track}</div>
                  <div className="text-sm text-signal-white/60 truncate">{track.artist}</div>
                </div>

                {/* Time */}
                <div className="text-right flex-shrink-0 font-mono">
                  <div className="text-sm font-semibold text-channel-green">{track.relativeTime}</div>
                  <div className="text-xs text-signal-white/60">{formatEventTime(track.time)}</div>
                </div>
              </div>
            ))}
          </div>
        </Surface>
      </section>
    </>
  );
}
