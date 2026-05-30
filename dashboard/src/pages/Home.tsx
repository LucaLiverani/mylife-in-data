import { useEffect, useState } from 'react';
import { ChannelStrip, type ChannelStatus } from '@/components/ChannelStrip';
import { LiveConsole } from '@/components/LiveConsole';
import { FadeIn } from '@/components/animations/FadeIn';
import { DataGenerationChart } from '@/components/charts/DataGenerationChart';
import { overviewAPI, travelAPI, calendarAPI, homeAPI } from '@/lib/api';
import { CHANNEL_CLASS, type Channel } from '@/lib/channels';
import { formatCount } from '@/lib/format';
import { useLiveSpotify } from '@/lib/useLiveSpotify';
import { cn } from '@/lib/utils';

interface OverviewData {
  summary: {
    spotifyHours:    number | string;
    youtubeHours:    number | string;
    songsStreamed:   number | string;
    artistsListened: number | string;
    videosWatched:   number | string;
    youtubeChannels: number | string;
    calendarEvents?: number | string;
    citiesVisited:   number | string;
  };
  dataGeneration: {
    dates: string[];
    spotify: number[];
    youtube: number[];
    calendar: number[];
    maps: number[];
    totalEvents: string;
    avgPerDay: string;
  };
  console?: {
    noisiestHour: string;            // "14:00"
    noisiestHourEventCount: number;
    quietStreakMinutes: number;
    daysTracked: number;
    channelDominance: Array<{ channel: Channel; share: number }>;
  };
  _meta?: { cached: boolean; timestamp: string };
}

interface TravelData {
  locations: Array<{ name: string; lat: number; lng: number; date: string; duration: string }>;
  stats: {
    citiesVisited:    number | string;
    countriesVisited: number | string;
    totalActivities:  number | string;
    uniqueDestinations: number | string;
  };
}

interface CalendarSummary {
  kpis: {
    plansCount:   number | string;
    freeDays:     number | string;
    totalEvents:  number | string;
    meetingHours: number | string;
    avgDaily:     number | string;
    busiestDay:   string;
  };
  upcomingEvents: Array<{
    title: string;
    category: string;
    time: string;
    relativeTime: string;
    durationMinutes: number;
  }>;
  dailyEvents: Array<{ date: string; events: number }>;
}

interface RecentEvents {
  spotify: Array<{ track: string; artist: string; time: string; relativeTime: string; albumArt: string }>;
  youtube: Array<{ title: string; activityType: string; time: string; isFromAds: boolean; relativeTime: string }>;
  maps: Array<{ location: string; type: string; time: string; timeOfDay: string }>;
}

function isToday(iso: string | undefined | null): boolean {
  if (!iso) return false;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return false;
  const now = new Date();
  return d.toDateString() === now.toDateString();
}

export default function Home() {
  const [loading, setLoading] = useState(true);
  const [overviewData, setOverviewData] = useState<OverviewData | null>(null);
  const [travelData, setTravelData] = useState<TravelData | null>(null);
  const [recentEvents, setRecentEvents] = useState<RecentEvents | null>(null);
  const [calendarSummary, setCalendarSummary] = useState<CalendarSummary | null>(null);
  const spotifyLive = useLiveSpotify();

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [overview, travel, events, calendar] = await Promise.all([
          overviewAPI.getStats(),
          travelAPI.getData(),
          homeAPI.getRecentEvents(),
          calendarAPI.getData().catch(() => null),
        ]);
        setOverviewData(overview as OverviewData);
        setTravelData(travel as TravelData);
        setRecentEvents(events as RecentEvents);
        if (calendar) setCalendarSummary(calendar as CalendarSummary);
      } catch (error) {
        console.error('Error fetching data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-[80vh] items-center justify-center text-signal-white">
        <p className="font-mono text-sm uppercase tracking-wider text-signal-white/60">Loading the console…</p>
      </div>
    );
  }

  // ─── Derive channel-strip props ───────────────────────────────────────
  const spotifyTrack = spotifyLive.data?.track_id ? spotifyLive.data : (spotifyLive.lastValidTrack ?? null);
  const spotifyArtists = spotifyTrack?.artists?.map((a) => a.name).join(', ') ?? '';
  const spotifyMostRecent = recentEvents?.spotify[0];
  const spotifyStatus: ChannelStatus =
    spotifyLive.isPlaying ? 'live' :
    (spotifyTrack || spotifyMostRecent) ? 'recent' : 'idle';

  const youtubeMostRecent = recentEvents?.youtube[0];
  const youtubeStatus: ChannelStatus = youtubeMostRecent ? 'recent' : 'idle';

  const mapsMostRecent = recentEvents?.maps[0];
  const mapsStatus: ChannelStatus = mapsMostRecent ? 'recent' : 'idle';

  const nextEvent = calendarSummary?.upcomingEvents?.[0];
  const calendarStatus: ChannelStatus =
    nextEvent && isToday(nextEvent.time) ? 'today' :
    nextEvent ? 'recent' : 'idle';

  const sparks = {
    spotify:  overviewData?.dataGeneration.spotify.slice(-30) ?? [],
    youtube:  overviewData?.dataGeneration.youtube.slice(-30) ?? [],
    maps:     overviewData?.dataGeneration.maps.slice(-30) ?? [],
    calendar: (calendarSummary?.dailyEvents.slice(-30) ?? []).map((d) => d.events),
  };

  const consoleSig = overviewData?.console;
  const dominant = consoleSig?.channelDominance?.slice().sort((a, b) => b.share - a.share)[0];

  return (
    <main className="text-signal-white">
      <div className="mx-auto max-w-7xl px-6 py-12">

        {/* Hero — tighter, blockquote stripped, tagline does the work */}
        <section className="mb-10" aria-labelledby="home-hero">
          <FadeIn>
            <p className="mb-3 font-mono text-xs uppercase tracking-wider text-signal-white/60">
              Producer's console · {consoleSig?.daysTracked ? `${formatCount(consoleSig.daysTracked)} days tracked` : 'all channels'}
            </p>
            <h1 id="home-hero" className="mb-4 text-5xl font-bold leading-[1.0] tracking-tight lg:text-7xl">
              <span>My Life </span>
              <span className="text-channel-green">in Data</span>
            </h1>
            <p className="max-w-2xl text-xl italic text-signal-white/70">
              Pretty charts, brutal honesty, optional self-improvement.
            </p>
            {overviewData?._meta?.cached && (
              <div role="status" className="mt-4 inline-block rounded-sm border border-trace-down/30 bg-trace-down/10 px-3 py-2 font-mono text-xs text-trace-down">
                ClickHouse offline — showing cached signal.
              </div>
            )}
          </FadeIn>
        </section>

        {/* Console signature — the meters that say what the system is doing right now */}
        {consoleSig && (
          <section className="mb-12" aria-labelledby="console-row">
            <FadeIn delay={0.08}>
              <h2 id="console-row" className="mb-4 font-mono text-xs uppercase tracking-wider text-signal-white/60">
                Console
              </h2>
              <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                <ConsoleMeter
                  label="Noisiest hour"
                  value={consoleSig.noisiestHour}
                  hint={`${formatCount(consoleSig.noisiestHourEventCount)} events`}
                />
                <ConsoleMeter
                  label="Quiet streak"
                  value={`${formatCount(consoleSig.quietStreakMinutes)}m`}
                  hint="since last signal"
                />
                <ConsoleMeter
                  label="Days tracked"
                  value={formatCount(consoleSig.daysTracked)}
                  hint="across all channels"
                />
                <ConsoleMeter
                  label="Top channel"
                  value={dominant?.channel ?? '-'}
                  hint={dominant ? `${Math.round(dominant.share * 100)}% share` : ''}
                  channel={dominant?.channel}
                />
              </div>
            </FadeIn>
          </section>
        )}

        {/* Channel Strips — the four signals */}
        <section className="mb-14" aria-labelledby="channels-heading">
          <FadeIn delay={0.12}>
            <h2 id="channels-heading" className="mb-4 font-mono text-xs uppercase tracking-wider text-signal-white/60">
              Channels
            </h2>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
              <ChannelStrip
                channel="spotify"
                title="Spotify"
                status={spotifyStatus}
                primary={spotifyTrack?.track_name ?? spotifyMostRecent?.track ?? 'The studio is quiet.'}
                secondary={
                  spotifyTrack
                    ? spotifyArtists
                    : spotifyMostRecent
                      ? `${spotifyMostRecent.artist} · ${spotifyMostRecent.relativeTime}`
                      : 'No signal'
                }
                sparkline={sparks.spotify}
                kpiA={{ label: 'Hours',   value: overviewData?.summary.spotifyHours    ?? 0, kind: 'hours' }}
                kpiB={{ label: 'Artists', value: overviewData?.summary.artistsListened ?? 0, kind: 'count' }}
                href="/spotify"
              />
              <ChannelStrip
                channel="youtube"
                title="YouTube"
                status={youtubeStatus}
                primary={youtubeMostRecent?.title ?? 'No recent videos.'}
                secondary={
                  youtubeMostRecent
                    ? `${youtubeMostRecent.isFromAds ? 'From Ads' : 'Watched'} · ${youtubeMostRecent.relativeTime}`
                    : 'No signal'
                }
                sparkline={sparks.youtube}
                kpiA={{ label: 'Hours',    value: overviewData?.summary.youtubeHours    ?? 0, kind: 'hours' }}
                kpiB={{ label: 'Channels', value: overviewData?.summary.youtubeChannels ?? 0, kind: 'count' }}
                href="/youtube"
              />
              <ChannelStrip
                channel="maps"
                title="Maps"
                status={mapsStatus}
                primary={mapsMostRecent?.location ?? 'Nowhere new today.'}
                secondary={
                  mapsMostRecent
                    ? `${mapsMostRecent.type.replace('_', ' ')} · ${mapsMostRecent.timeOfDay.toLowerCase()}`
                    : 'No signal'
                }
                sparkline={sparks.maps}
                kpiA={{ label: 'Cities',    value: travelData?.stats.citiesVisited    ?? 0, kind: 'count' }}
                kpiB={{ label: 'Countries', value: travelData?.stats.countriesVisited ?? 0, kind: 'count' }}
                href="/maps"
              />
              <ChannelStrip
                channel="calendar"
                title="Calendar"
                status={calendarStatus}
                primary={nextEvent?.title ?? 'Nothing on the schedule.'}
                secondary={
                  nextEvent
                    ? `${nextEvent.relativeTime} · ${nextEvent.durationMinutes} min`
                    : 'Free as a bird'
                }
                sparkline={sparks.calendar}
                kpiA={{ label: 'Plans',     value: calendarSummary?.kpis.plansCount ?? 0, kind: 'count' }}
                kpiB={{ label: 'Free days', value: calendarSummary?.kpis.freeDays   ?? 0, kind: 'count' }}
                href="/google"
              />
            </div>
          </FadeIn>
        </section>

        {/* Signal over time — 90-day cross-channel line */}
        {overviewData?.dataGeneration && (
          <section className="mb-14" aria-labelledby="data-gen-heading">
            <FadeIn delay={0.15}>
              <h2 id="data-gen-heading" className="mb-4 font-mono text-xs uppercase tracking-wider text-signal-white/60">
                Signal over time
              </h2>
              <div className="rounded-md border border-signal-white/10 bg-rack-black/60 p-6">
                <div className="h-96">
                  <DataGenerationChart data={overviewData.dataGeneration} />
                </div>
              </div>
            </FadeIn>
          </section>
        )}

        {/* Live console — the last cross-channel events, embedded so Home reads
            as a real-time surface, not just a summary. Click-through to /now.
            Sized to match (and slightly exceed) the signal-over-time chart above. */}
        <section aria-labelledby="live-console">
          <FadeIn delay={0.18}>
            <LiveConsole limit={12} />
          </FadeIn>
        </section>
      </div>
    </main>
  );
}

/**
 * Console-signature meter — the cross-channel KPIs that live on Home.
 * Smaller and quieter than ChannelStrip; not interactive.
 */
function ConsoleMeter({
  label,
  value,
  hint,
  channel,
}: {
  label: string;
  value: string;
  hint?: string;
  channel?: Channel;
}) {
  const valueClass = channel ? CHANNEL_CLASS.text[channel] : 'text-signal-white';
  return (
    <div className="rounded-md border border-signal-white/10 bg-rack-black/60 p-5">
      <p className="font-mono text-[10px] uppercase tracking-widest text-signal-white/60">{label}</p>
      <p className={cn('mt-2 font-mono text-2xl font-bold capitalize tabular-nums', valueClass)}>{value}</p>
      {hint && <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-signal-white/40">{hint}</p>}
    </div>
  );
}
