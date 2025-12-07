import { useEffect, useState } from 'react';
import { ServiceCard } from '@/components/ServiceCard';
import { FadeIn } from '@/components/animations/FadeIn';
import { ParticleBackground } from '@/components/animations/ParticleBackground';
import { Typewriter } from '@/components/animations/Typewriter';
import { DataGenerationChart } from '@/components/charts/DataGenerationChart';
import { overviewAPI, spotifyAPI, travelAPI } from '@/lib/api';

interface OverviewData {
  summary: {
    songsStreamed: string;
    artistsListened: string;
    videosWatched: string;
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
    totalDistance: string;
    countries: string;
    cities: string;
    longestTrip: string;
  };
}

interface RecentTrack {
  track: string;
  artist: string;
  time: string;
  albumArt?: string;
}

export default function Home() {
  const [loading, setLoading] = useState(true);
  const [overviewData, setOverviewData] = useState<OverviewData | null>(null);
  const [travelData, setTravelData] = useState<TravelData | null>(null);
  const [recentTracks, setRecentTracks] = useState<RecentTrack[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [overview, travel, tracks] = await Promise.all([
          overviewAPI.getStats(),
          travelAPI.getData(),
          spotifyAPI.getRecent(),
        ]);

        setOverviewData(overview as OverviewData);
        setTravelData(travel as TravelData);
        setRecentTracks(tracks as RecentTrack[]);
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
                  { label: 'Channels', value: '156' },
                  { label: 'Videos', value: overviewData?.summary.videosWatched || '0' }
                ]}
                color="#FF0000"
                href="/youtube"
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

        {/* Recent Tracks */}
        <section className="mb-20">
          <FadeIn delay={0.4}>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8">
              <h2 className="text-2xl font-bold mb-6">Recent Tracks</h2>
              <div className="space-y-3">
                {recentTracks.slice(0, 5).map((track, i) => (
                  <div key={i} className="flex items-center gap-4 p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors">
                    {track.albumArt && (
                      <img src={track.albumArt} alt={track.track} className="w-12 h-12 rounded" />
                    )}
                    <div className="flex-1">
                      <div className="font-semibold">{track.track}</div>
                      <div className="text-sm text-white/60">{track.artist}</div>
                    </div>
                    <div className="text-sm text-white/40">{track.time}</div>
                  </div>
                ))}
              </div>
            </div>
          </FadeIn>
        </section>
      </div>
    </div>
  );
}
