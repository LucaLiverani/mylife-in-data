import { useEffect, useState } from 'react';
import { ChannelStrip, type ChannelStatus } from '@/components/ChannelStrip';
import { FadeIn } from '@/components/animations/FadeIn';
import { DataGenerationChart } from '@/components/charts/DataGenerationChart';
import { overviewAPI, homeAPI, travelAPI, calendarAPI } from '@/lib/api';
import { CHANNEL_CLASS, type Channel } from '@/lib/channels';
import { formatEventTime } from '@/lib/format';
import { useLiveSpotify } from '@/lib/useLiveSpotify';

interface OverviewData {
  summary: {
    spotifyHours:    number | string;
    youtubeHours:    number | string;
    songsStreamed:   number | string;
    artistsListened: number | string;
    videosWatched:   number | string;
    youtubeChannels: number | string;
    searchQueries:   number | string;
    citiesVisited:   number | string;
  };
  dataGeneration: {
    dates: string[];
    spotify: number[];
    youtube: number[];
    google: number[];
    maps: number[];
    totalEvents: string;
    avgPerDay: string;
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

// Maps activity icons (currentColor inherits text-channel-violet from parent svg).
const getMapsActivityIcon = (type: string): JSX.Element => {
  switch (type) {
    case 'directions':
      return (
        <svg className="size-4" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path d="M8 2L8 14M8 2L4 6M8 2L12 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case 'search':
      return (
        <svg className="size-4" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <circle cx="7" cy="7" r="4" stroke="currentColor" strokeWidth="1.5" fill="none" />
          <path d="M10 10L13 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      );
    case 'explore':
      return (
        <svg className="size-4" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <circle cx="8" cy="8" r="5" stroke="currentColor" strokeWidth="1.5" fill="none" />
          <path d="M8 3L10 8L8 13L6 8L8 3Z" fill="currentColor" />
        </svg>
      );
    case 'place_view':
    case 'view':
    case 'app_usage':
    case 'save':
    case 'review':
    case 'place_visit':
      return (
        <svg className="size-4" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path d="M8 2C6.067 2 4.5 3.567 4.5 5.5C4.5 8.25 8 13 8 13C8 13 11.5 8.25 11.5 5.5C11.5 3.567 9.933 2 8 2ZM8 7C7.172 7 6.5 6.328 6.5 5.5C6.5 4.672 7.172 4 8 4C8.828 4 9.5 4.672 9.5 5.5C9.5 6.328 8.828 7 8 7Z" fill="currentColor" />
        </svg>
      );
    default:
      return (
        <svg className="size-4" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <circle cx="8" cy="8" r="5" stroke="currentColor" strokeWidth="1.5" fill="none" />
          <circle cx="8" cy="8" r="1.5" fill="currentColor" />
        </svg>
      );
  }
};

function ChannelPanel({
  channel,
  title,
  children,
}: {
  channel: Channel;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-md border border-signal-white/10 bg-rack-black/60">
      <header className="flex items-center gap-3 border-b border-signal-white/10 px-5 py-3">
        <span className={`block size-2 rounded-sm ${CHANNEL_CLASS.bg[channel]}`} aria-hidden="true" />
        <h3 className="font-mono text-xs font-medium uppercase tracking-wider text-signal-white/80">{title}</h3>
      </header>
      <div className={`max-h-[280px] overflow-y-auto ${CHANNEL_CLASS.scrollbar[channel]}`}>
        {children}
      </div>
    </section>
  );
}

function EventRow({
  channel,
  primary,
  secondary,
  rightTop,
  rightBottom,
  leftIcon,
  leftImage,
}: {
  channel: Channel;
  primary: string;
  secondary: string;
  rightTop: string;
  rightBottom: string;
  leftIcon?: React.ReactNode;
  leftImage?: string;
}) {
  const channelText = CHANNEL_CLASS.text[channel];
  return (
    <div className="flex items-center gap-3 border-b border-signal-white/5 px-5 py-3 last:border-b-0 transition-colors ease-snap duration-150 hover:bg-signal-white/[0.03]">
      {leftImage ? (
        <img src={leftImage} alt="" loading="lazy" decoding="async" className="size-10 rounded-sm object-cover" />
      ) : leftIcon ? (
        <span className={`flex size-10 items-center justify-center rounded-sm ${channelText}`}>{leftIcon}</span>
      ) : null}
      <div className="flex-1 min-w-0">
        <div className="truncate text-sm font-medium text-signal-white">{primary}</div>
        <div className="truncate text-xs text-signal-white/60">{secondary}</div>
      </div>
      <div className="text-right">
        <div className={`font-mono text-xs font-medium ${channelText}`}>{rightTop}</div>
        <div className="font-mono text-[10px] text-signal-white/60">{rightBottom}</div>
      </div>
    </div>
  );
}

// Returns true when the ISO timestamp falls on today's date (local time).
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
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-rack-black to-rack-charcoal text-signal-white">
        <p className="font-mono text-sm uppercase tracking-wider text-signal-white/60">Loading the console…</p>
      </div>
    );
  }

  // ─── Derive channel-strip props ───────────────────────────────────────
  const spotifyTrack = spotifyLive.data?.track_id
    ? spotifyLive.data
    : (spotifyLive.lastValidTrack ?? null);
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

  // ─── Sparkline data (last 30 days per channel) ────────────────────────
  const sparks = {
    spotify:  overviewData?.dataGeneration.spotify.slice(-30) ?? [],
    youtube:  overviewData?.dataGeneration.youtube.slice(-30) ?? [],
    maps:     overviewData?.dataGeneration.maps.slice(-30) ?? [],
    calendar: (calendarSummary?.dailyEvents.slice(-30) ?? []).map((d) => d.events),
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-rack-black to-rack-charcoal text-signal-white">
      <div className="mx-auto max-w-7xl px-6 py-16">

        {/* Hero — tighter than before, the channel strips take the visual weight */}
        <section className="mb-10" aria-labelledby="home-hero">
          <FadeIn>
            <h1 id="home-hero" className="mb-3 text-5xl font-bold leading-[1.0] tracking-tight lg:text-7xl">
              <span>My Life </span>
              <span className="text-channel-green">in Data</span>
            </h1>
            <p className="text-xl italic text-signal-white/60">
              Turning bad habits into pretty charts.
            </p>
            <blockquote className="mt-5 max-w-2xl border-l-2 border-channel-green/40 pl-4 font-mono text-sm italic text-signal-white/60">
              Pretty charts, brutal honesty, optional self-improvement.
            </blockquote>
            {overviewData?._meta?.cached && (
              <div role="status" className="mt-4 inline-block rounded-sm border border-trace-down/30 bg-trace-down/10 px-3 py-2 font-mono text-xs text-trace-down">
                ClickHouse offline — showing cached signal.
              </div>
            )}
          </FadeIn>
        </section>

        {/* Channel Strips — the new hero */}
        <section className="mb-16" aria-labelledby="channels-heading">
          <FadeIn delay={0.1}>
            <h2 id="channels-heading" className="mb-4 font-mono text-xs uppercase tracking-wider text-signal-white/60">
              Channels
            </h2>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
              <ChannelStrip
                channel="spotify"
                title="Spotify"
                status={spotifyStatus}
                primary={
                  spotifyTrack?.track_name
                    ?? spotifyMostRecent?.track
                    ?? 'The studio is quiet.'
                }
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

        {/* Data Generation — 90-day spectrum */}
        {overviewData?.dataGeneration && (
          <section className="mb-16" aria-labelledby="data-gen-heading">
            <FadeIn delay={0.15}>
              <h2 id="data-gen-heading" className="mb-4 font-mono text-xs uppercase tracking-wider text-signal-white/60">
                Signal over time
              </h2>
              <div className="rounded-md border border-signal-white/10 bg-rack-black/60 p-6">
                <div className="h-96">
                  <DataGenerationChart
                    data={overviewData.dataGeneration}
                    totalEvents={overviewData.dataGeneration.totalEvents}
                    avgPerDay={overviewData.dataGeneration.avgPerDay}
                  />
                </div>
              </div>
            </FadeIn>
          </section>
        )}

        {/* Recent Signal — three flat side-by-side panels */}
        <section aria-labelledby="recent-heading">
          <FadeIn delay={0.2}>
            <h2 id="recent-heading" className="mb-4 font-mono text-xs uppercase tracking-wider text-signal-white/60">
              Recent Signal
            </h2>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <ChannelPanel channel="spotify" title="Spotify">
                {recentEvents?.spotify.map((track, i) => (
                  <EventRow
                    key={i}
                    channel="spotify"
                    primary={track.track}
                    secondary={track.artist}
                    rightTop={track.relativeTime}
                    rightBottom={formatEventTime(track.time)}
                    leftImage={track.albumArt}
                  />
                ))}
              </ChannelPanel>

              <ChannelPanel channel="youtube" title="YouTube">
                {recentEvents?.youtube.map((video, i) => (
                  <EventRow
                    key={i}
                    channel="youtube"
                    primary={video.title}
                    secondary={video.isFromAds ? 'From Ads' : 'Watched'}
                    rightTop={video.relativeTime}
                    rightBottom={formatEventTime(video.time)}
                    leftIcon={
                      video.isFromAds ? (
                        <svg className="size-4 text-channel-red" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                          <rect x="2" y="5" width="12" height="6" rx="1" fill="currentColor" />
                        </svg>
                      ) : (
                        <svg className="size-4 text-channel-red" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                          <path d="M5 3L13 8L5 13V3Z" fill="currentColor" />
                        </svg>
                      )
                    }
                  />
                ))}
              </ChannelPanel>

              <ChannelPanel channel="maps" title="Maps">
                {recentEvents?.maps.map((activity, i) => (
                  <EventRow
                    key={i}
                    channel="maps"
                    primary={activity.location}
                    secondary={activity.type.replace('_', ' ')}
                    rightTop={activity.timeOfDay}
                    rightBottom={formatEventTime(activity.time)}
                    leftIcon={getMapsActivityIcon(activity.type)}
                  />
                ))}
              </ChannelPanel>
            </div>
          </FadeIn>
        </section>
      </div>
    </main>
  );
}
