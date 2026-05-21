import { Surface } from '@/components/Surface';
import { EventRow } from '@/components/EventRow';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { CHART_COLORS, CHART_STYLES, TIME_SERIES_CHART_HEIGHT, formatDetailedDate } from './chartConfig';
import { ChannelPie } from './ChannelPie';
import { TopList } from './TopList';
import { formatEventTime } from '@/lib/format';

interface SpotifyFullData {
  kpis: {
    totalTime: number | string;
    songsStreamed: number | string;
    uniqueArtists: number | string;
    avgDaily: number | string;
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
  relativeTime?: string;
  albumArt: string;
}

interface SpotifyChartsProps {
  data: SpotifyFullData;
  recentTracks: RecentTrack[];
}

export function SpotifyCharts({ data, recentTracks }: SpotifyChartsProps) {
  return (
    <>
      {/* 1. Daily time-series */}
      <section className="mb-12">
        <Surface>
          <h2 className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
            Daily listening hours · last 30 days
          </h2>
          <ResponsiveContainer width="100%" height={TIME_SERIES_CHART_HEIGHT}>
            <LineChart data={data.timeSeries.dates.map((date: string, i: number) => ({ date, hours: data.timeSeries.values[i] }))}>
              <CartesianGrid {...CHART_STYLES.cartesianGrid} />
              <XAxis
                dataKey="date"
                stroke="rgba(255,255,255,0.25)"
                tickLine={false}
                axisLine={false}
                tick={{ fill: 'rgba(255,255,255,0.6)', fontSize: 10, fontFamily: '"IBM Plex Mono", ui-monospace, monospace' }}
                tickFormatter={(value) => formatDetailedDate(value)}
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
                labelFormatter={(value) => `Date: ${value}`}
              />
              <Line type="monotone" dataKey="hours"
                    stroke={CHART_COLORS.spotify} strokeWidth={2}
                    dot={{ fill: CHART_COLORS.spotify, r: 2 }} activeDot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </Surface>
      </section>

      {/* 2. Top list + Distribution */}
      <section className="mb-12">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Surface className="flex h-full flex-col">
            <h2 className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
              Top artists
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

          <Surface className="flex h-full flex-col">
            <h2 className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
              Genre distribution
            </h2>
            <ChannelPie channel="spotify" data={data.genres} topN={5} />
          </Surface>
        </div>
      </section>

      {/* 5. Recent events */}
      <section>
        <Surface>
          <h2 className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
            Recently played
          </h2>
          <div className="-mx-6 -mb-6">
            {recentTracks.slice(0, 10).map((track, index) => (
              <EventRow
                key={index}
                channel="spotify"
                primary={track.track}
                secondary={track.artist}
                rightTop={track.relativeTime ?? ''}
                rightBottom={formatEventTime(track.time)}
                leftImage={track.albumArt}
              />
            ))}
          </div>
        </Surface>
      </section>
    </>
  );
}
