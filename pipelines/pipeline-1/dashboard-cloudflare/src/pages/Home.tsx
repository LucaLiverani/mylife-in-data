import { useEffect, useState } from 'react';
import { ServiceCard } from '@/components/ServiceCard';
import { FadeIn } from '@/components/animations/FadeIn';
import { ParticleBackground } from '@/components/animations/ParticleBackground';
import { Typewriter } from '@/components/animations/Typewriter';
import { DataGenerationChart } from '@/components/charts/DataGenerationChart';
import { overviewAPI, homeAPI, travelAPI } from '@/lib/api';

interface OverviewData {
  summary: {
    songsStreamed: string;
    artistsListened: string;
    videosWatched: string;
    youtubeChannels: string;
    searchQueries: string;
    citiesVisited: string;
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
  _meta?: {
    cached: boolean;
    timestamp: string;
  };
}

interface TravelData {
  locations: Array<{ name: string; lat: number; lng: number; date: string; duration: string }>;
  stats: {
    totalActivities: string;
    uniqueDestinations: string;
  };
}

interface RecentEvents {
  spotify: Array<{
    track: string;
    artist: string;
    time: string;
    relativeTime: string;
    albumArt: string;
  }>;
  youtube: Array<{
    title: string;
    activityType: string;
    time: string;
    isFromAds: boolean;
    relativeTime: string;
  }>;
  maps: Array<{
    location: string;
    type: string;
    time: string;
    timeOfDay: string;
  }>;
}

// Helper to get icon for Maps activity type
const getMapsActivityIcon = (type: string): JSX.Element => {
  switch (type) {
    case 'directions':
      // Arrow/Navigation icon
      return (
        <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none">
          <path d="M8 2L8 14M8 2L4 6M8 2L12 6" stroke="#A855F7" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      );
    case 'search':
      // Magnifying glass icon
      return (
        <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none">
          <circle cx="7" cy="7" r="4" stroke="#A855F7" strokeWidth="1.5" fill="none"/>
          <path d="M10 10L13 13" stroke="#A855F7" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
      );
    case 'explore':
      // Compass icon
      return (
        <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="5" stroke="#A855F7" strokeWidth="1.5" fill="none"/>
          <path d="M8 3L10 8L8 13L6 8L8 3Z" fill="#A855F7"/>
        </svg>
      );
    case 'place_view':
    case 'view':
    case 'app_usage':
    case 'save':
    case 'review':
    case 'place_visit':
      // Location pin icon
      return (
        <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none">
          <path d="M8 2C6.067 2 4.5 3.567 4.5 5.5C4.5 8.25 8 13 8 13C8 13 11.5 8.25 11.5 5.5C11.5 3.567 9.933 2 8 2ZM8 7C7.172 7 6.5 6.328 6.5 5.5C6.5 4.672 7.172 4 8 4C8.828 4 9.5 4.672 9.5 5.5C9.5 6.328 8.828 7 8 7Z" fill="#A855F7"/>
        </svg>
      );
    default:
      // Target/circle icon for other types
      return (
        <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="5" stroke="#A855F7" strokeWidth="1.5" fill="none"/>
          <circle cx="8" cy="8" r="1.5" fill="#A855F7"/>
        </svg>
      );
  }
};

export default function Home() {
  const [loading, setLoading] = useState(true);
  const [overviewData, setOverviewData] = useState<OverviewData | null>(null);
  const [travelData, setTravelData] = useState<TravelData | null>(null);
  const [recentEvents, setRecentEvents] = useState<RecentEvents | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [overview, travel, events] = await Promise.all([
          overviewAPI.getStats(),
          travelAPI.getData(),
          homeAPI.getRecentEvents(),
        ]);

        setOverviewData(overview as OverviewData);
        setTravelData(travel as TravelData);
        setRecentEvents(events as RecentEvents);
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
      <div className="min-h-screen bg-gradient-to-br from-[#1a1a1a] to-[#2d2d2d] text-white flex items-center justify-center">
        <div className="text-2xl">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#1a1a1a] to-[#2d2d2d] text-white">
      <ParticleBackground />

      <div className="relative z-10 max-w-7xl mx-auto px-6 py-20">
        {/* Hero Section */}
        <section className="mb-20">
          <FadeIn>
            <div className="mb-8">
              <h1 className="text-6xl lg:text-8xl font-bold leading-tight mb-4">
                <span className="text-white">My Life </span>
                <span className="text-[#1DB954]">in Data</span>
              </h1>
              <p className="text-2xl lg:text-3xl font-light text-white/60 italic">
                <Typewriter
                  texts={[
                    "Turning bad habits into pretty charts.",
                    "Obsessively tracking everything I should probably forget.",
                    "Making procrastination look productive since 2024.",
                  ]}
                  speed={60}
                  deleteSpeed={40}
                  pauseTime={2000}
                />
              </p>
            </div>
            <div className="max-w-4xl">
              <p className="text-lg text-white/70 leading-relaxed mb-4">
                My Life in Data aggregates all my daily services to expose my music fixations, time sinkholes, and data black holes, then wraps it in visuals.
              </p>
              <blockquote className="text-lg text-white/50 italic border-l-4 border-[#1DB954]/30 pl-4">
                &quot;Pretty charts, brutal honesty, optional self‑improvement.&quot;
              </blockquote>
              {overviewData?._meta?.cached && (
                <div className="mt-4 text-sm text-yellow-400/80 bg-yellow-400/10 border border-yellow-400/30 rounded-lg px-4 py-2">
                  ⚠️ Showing cached data (ClickHouse unavailable)
                </div>
              )}
            </div>
          </FadeIn>
        </section>

        {/* Service Cards */}
        <section className="mb-20">
          <FadeIn delay={0.2}>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <ServiceCard
                title="Spotify"
                iconName="music"
                stats={[
                  { label: 'Artists', value: overviewData?.summary.artistsListened || '0' },
                  { label: 'Songs', value: overviewData?.summary.songsStreamed || '0' }
                ]}
                color="#1DB954"
                href="/spotify"
              />
              <ServiceCard
                title="YouTube"
                iconName="youtube"
                stats={[
                  { label: 'Channels', value: overviewData?.summary.youtubeChannels || '0' },
                  { label: 'Videos', value: overviewData?.summary.videosWatched || '0' }
                ]}
                color="#FF0000"
                href="/youtube"
              />
              <ServiceCard
                title="Maps"
                iconName="map"
                stats={[
                  { label: 'Activities', value: travelData?.stats.totalActivities || '0' },
                  { label: 'Destinations', value: travelData?.stats.uniqueDestinations || '0' }
                ]}
                color="#A855F7"
                href="/maps"
              />
              <ServiceCard
                title="Google Search"
                iconName="search"
                stats={[
                  { label: 'Queries', value: overviewData?.summary.searchQueries || '0' },
                  { label: 'Categories', value: '23' }
                ]}
                color="#4285F4"
                href="/google"
              />
            </div>
          </FadeIn>
        </section>

        {/* Data Generation Chart */}
        {overviewData?.dataGeneration && (
          <section className="mb-20">
            <FadeIn delay={0.3}>
              <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8">
                <h2 className="text-2xl font-bold mb-6">Data Generation Over Time</h2>
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

        {/* Recent Events */}
        <section className="mb-20">
          <FadeIn delay={0.4}>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8">
              <h2 className="text-2xl font-bold mb-6">Recent Events</h2>

              <div className="space-y-6">
                {/* Spotify Events */}
                <div className="bg-[#1DB954]/10 border-2 border-[#1DB954]/30 rounded-xl p-6">
                  <h3 className="text-xl font-bold mb-4">Spotify</h3>
                  <div className="space-y-3 max-h-[280px] overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-[#1DB954]/50 scrollbar-track-transparent">
                    {recentEvents?.spotify.map((track, i) => (
                      <div key={i} className="flex items-center gap-4 p-4 rounded-lg bg-black/20 hover:bg-black/30 transition-all">
                        {track.albumArt && (
                          <img src={track.albumArt} alt={track.track} className="w-16 h-16 rounded" />
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="font-semibold text-lg truncate">{track.track}</div>
                          <div className="text-sm text-white/60 truncate">{track.artist}</div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm font-semibold text-[#1DB954]">{track.relativeTime}</div>
                          <div className="text-xs text-white/60">{track.time}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* YouTube Events */}
                <div className="bg-[#FF0000]/10 border-2 border-[#FF0000]/30 rounded-xl p-6">
                  <h3 className="text-xl font-bold mb-4">Recent Videos</h3>
                  <div className="space-y-3 max-h-[280px] overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-[#FF0000]/50 scrollbar-track-transparent">
                    {recentEvents?.youtube.map((video, i) => (
                      <div key={i} className="flex items-center justify-between p-4 rounded-lg bg-black/20 hover:bg-black/30 transition-all">
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
                          <div className="text-xs text-white/60">{video.time}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Maps Events */}
                <div className="bg-[#A855F7]/10 border-2 border-[#A855F7]/30 rounded-xl p-6">
                  <h3 className="text-xl font-bold mb-4">Maps</h3>
                  <div className="space-y-3 max-h-[280px] overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-[#A855F7]/50 scrollbar-track-transparent">
                    {recentEvents?.maps.map((activity, i) => (
                      <div key={i} className="flex items-center justify-between p-4 rounded-lg bg-black/20 hover:bg-black/30 transition-all">
                        <div className="flex items-center gap-4 flex-1 min-w-0">
                          <div className="w-8 h-8 rounded-lg bg-[#A855F7]/20 flex items-center justify-center flex-shrink-0">
                            {getMapsActivityIcon(activity.type)}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="font-semibold text-sm truncate">{activity.location}</div>
                            <div className="text-xs text-white/60 capitalize">{activity.type.replace('_', ' ')}</div>
                          </div>
                        </div>
                        <div className="text-right ml-4">
                          <div className="text-sm font-semibold text-[#A855F7]">{activity.timeOfDay}</div>
                          <div className="text-xs text-white/60">{activity.time}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </FadeIn>
        </section>
      </div>
    </div>
  );
}
