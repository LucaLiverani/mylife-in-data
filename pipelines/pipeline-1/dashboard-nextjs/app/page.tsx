import { ServiceCard } from '@/components/ServiceCard';
import { FadeIn } from '@/components/animations/FadeIn';
import { ParticleBackground } from '@/components/animations/ParticleBackground';
import { Typewriter } from '@/components/animations/Typewriter';
import { DataGenerationChart } from '@/components/charts/DataGenerationChart';
import { RecentEventItem } from '@/components/RecentEventItem';
import { TravelMapClient } from '@/components/TravelMapClient';
import { overviewAPI, travelAPI, spotifyAPI } from '@/lib/api';

// Force dynamic rendering since we need to fetch data at runtime
export const dynamic = 'force-dynamic';

interface RecentTrack {
  track: string;
  artist: string;
  time: string;
  albumArt?: string;
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

interface OverviewData {
  summary: {
    songsStreamed: string;
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
}

export default async function Home() {
  const overviewData = await overviewAPI.getStats() as OverviewData;
  const travelData = await travelAPI.getData() as TravelData;
  const recentTracks = await spotifyAPI.getRecent() as RecentTrack[];

  // Group recent events by service type
  const eventGroups = [
    {
      service: 'Spotify',
      color: '#1DB954',
      maxVisible: 3,
      events: [
        { type: 'spotify', title: recentTracks[0]?.track || 'Song 1', subtitle: recentTracks[0]?.artist || 'Artist', time: recentTracks[0]?.time || '2m ago', image: recentTracks[0]?.albumArt, color: '#1DB954' },
        { type: 'spotify', title: recentTracks[1]?.track || 'Song 2', subtitle: recentTracks[1]?.artist || 'Artist', time: recentTracks[1]?.time || '18m ago', image: recentTracks[1]?.albumArt, color: '#1DB954' },
        { type: 'spotify', title: recentTracks[2]?.track || 'Song 3', subtitle: recentTracks[2]?.artist || 'Artist', time: recentTracks[2]?.time || '2h ago', image: recentTracks[2]?.albumArt, color: '#1DB954' },
        { type: 'spotify', title: recentTracks[3]?.track || 'Song 4', subtitle: recentTracks[3]?.artist || 'Artist', time: recentTracks[3]?.time || '3h ago', image: recentTracks[3]?.albumArt, color: '#1DB954' },
        { type: 'spotify', title: recentTracks[4]?.track || 'Song 5', subtitle: recentTracks[4]?.artist || 'Artist', time: recentTracks[4]?.time || '4h ago', image: recentTracks[4]?.albumArt, color: '#1DB954' },
        { type: 'spotify', title: recentTracks[5]?.track || 'Song 6', subtitle: recentTracks[5]?.artist || 'Artist', time: recentTracks[5]?.time || '5h ago', image: recentTracks[5]?.albumArt, color: '#1DB954' },
        { type: 'spotify', title: recentTracks[6]?.track || 'Song 7', subtitle: recentTracks[6]?.artist || 'Artist', time: recentTracks[6]?.time || '6h ago', image: recentTracks[6]?.albumArt, color: '#1DB954' },
        { type: 'spotify', title: 'Song 8', subtitle: 'Artist 8', time: '7h ago', color: '#1DB954' },
        { type: 'spotify', title: 'Song 9', subtitle: 'Artist 9', time: '8h ago', color: '#1DB954' },
        { type: 'spotify', title: 'Song 10', subtitle: 'Artist 10', time: '9h ago', color: '#1DB954' },
      ]
    },
    {
      service: 'YouTube',
      color: '#FF0000',
      maxVisible: 2,
      events: [
        { type: 'youtube', title: 'Building a Dashboard with Next.js', subtitle: 'Fireship', time: '15m ago', color: '#FF0000' },
        { type: 'youtube', title: 'TypeScript Advanced Patterns', subtitle: 'Web Dev Simplified', time: '4h ago', color: '#FF0000' },
        { type: 'youtube', title: 'React Performance Tips', subtitle: 'Jack Herrington', time: '5h ago', color: '#FF0000' },
        { type: 'youtube', title: 'CSS Grid Tutorial', subtitle: 'Kevin Powell', time: '6h ago', color: '#FF0000' },
        { type: 'youtube', title: 'Web Development in 2024', subtitle: 'Traversy Media', time: '7h ago', color: '#FF0000' },
        { type: 'youtube', title: 'JavaScript ES2024 Features', subtitle: 'Fireship', time: '8h ago', color: '#FF0000' },
        { type: 'youtube', title: 'Node.js Best Practices', subtitle: 'Academind', time: '9h ago', color: '#FF0000' },
        { type: 'youtube', title: 'API Design Guide', subtitle: 'Hussein Nasser', time: '10h ago', color: '#FF0000' },
        { type: 'youtube', title: 'Database Indexing', subtitle: 'ByteByteGo', time: '11h ago', color: '#FF0000' },
        { type: 'youtube', title: 'Clean Code Tips', subtitle: 'Uncle Bob', time: '12h ago', color: '#FF0000' },
      ]
    },
    {
      service: 'Google',
      color: '#4285F4',
      maxVisible: 1,
      events: [
        { type: 'google', title: 'best practices for data visualization', subtitle: 'Google Search', time: '1h ago', color: '#4285F4' },
        { type: 'google', title: 'nextjs 15 new features', subtitle: 'Google Search', time: '2h ago', color: '#4285F4' },
        { type: 'google', title: 'tailwind css gradient examples', subtitle: 'Google Search', time: '3h ago', color: '#4285F4' },
        { type: 'google', title: 'typescript generic types', subtitle: 'Google Search', time: '4h ago', color: '#4285F4' },
        { type: 'google', title: 'react hooks performance', subtitle: 'Google Search', time: '5h ago', color: '#4285F4' },
        { type: 'google', title: 'css flexbox vs grid', subtitle: 'Google Search', time: '6h ago', color: '#4285F4' },
        { type: 'google', title: 'docker compose tutorial', subtitle: 'Google Search', time: '7h ago', color: '#4285F4' },
        { type: 'google', title: 'kubernetes deployment', subtitle: 'Google Search', time: '8h ago', color: '#4285F4' },
        { type: 'google', title: 'graphql vs rest api', subtitle: 'Google Search', time: '9h ago', color: '#4285F4' },
        { type: 'google', title: 'web security best practices', subtitle: 'Google Search', time: '10h ago', color: '#4285F4' },
      ]
    },
  ].slice(0, 3);

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
                  { label: 'Artists', value: '100' },
                  { label: 'Songs', value: '22,456' }
                ]}
                color="#1DB954"
                href="/spotify"
              />
              <ServiceCard
                title="YouTube"
                iconName="youtube"
                stats={[
                  { label: 'Channels', value: '156' },
                  { label: 'Videos', value: '3,456' }
                ]}
                color="#FF0000"
                href="/youtube"
              />
              <ServiceCard
                title="Google Search"
                iconName="search"
                stats={[
                  { label: 'Queries', value: '456' },
                  { label: 'Categories', value: '23' }
                ]}
                color="#4285F4"
                href="/google"
              />
              <ServiceCard
                title="Maps"
                iconName="map"
                stats={[
                  { label: 'Cities', value: travelData.stats.cities },
                  { label: 'Countries', value: travelData.stats.countries }
                ]}
                color="#A855F7"
                href="/maps"
              />
            </div>
          </FadeIn>
        </section>

        {/* Data Generation & Recent Activity */}
        <section className="mb-20">
          <FadeIn delay={0.4}>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Data Generation Chart */}
              <div className="lg:col-span-2 bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 flex flex-col">
                <h2 className="text-2xl font-bold mb-6">Monthly Data Generation</h2>
                <div className="flex-1">
                  <DataGenerationChart
                    data={overviewData.dataGeneration}
                    totalEvents={overviewData.dataGeneration.totalEvents}
                    avgPerDay={overviewData.dataGeneration.avgPerDay}
                  />
                </div>
              </div>

              {/* Recent Events */}
              <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 flex flex-col">
                <h3 className="text-xl font-bold mb-6">Recent Events</h3>
                <div className="space-y-4 flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent pr-2">
                  {eventGroups.map((group, i: number) => (
                    <div
                      key={i}
                      className="rounded-lg p-3 border transition-all duration-300"
                      style={{
                        backgroundColor: `${group.color}08`,
                        borderColor: `${group.color}30`,
                      }}
                    >
                      <div className="flex items-center gap-2 mb-3">
                        <div
                          className="w-2 h-2 rounded-full"
                          style={{ backgroundColor: group.color }}
                        />
                        <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: group.color }}>
                          {group.service}
                        </p>
                      </div>
                      <div
                        className="space-y-1 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent"
                        style={{
                          maxHeight: `${group.maxVisible * 60}px`
                        }}
                      >
                        {group.events.map((event, j: number) => (
                          <RecentEventItem key={j} event={event} />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </FadeIn>
        </section>

        {/* Travel Preview */}
        <section>
          <FadeIn delay={0.6}>
            <div className="mb-8">
              <h2 className="text-4xl font-bold mb-3">My Travel History</h2>
              <p className="text-lg text-white/50 italic">
                Proof I occasionally leave my desk (and immediately start missing my setup).
              </p>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Map */}
              <div className="lg:col-span-2 bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 flex flex-col">
                <div className="flex-1 min-h-[400px]">
                  <TravelMapClient locations={travelData.locations} />
                </div>
              </div>

              {/* Travel KPIs */}
              <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 flex flex-col">
                <h3 className="text-xl font-bold mb-6">Travel Stats</h3>
                <div className="space-y-4 flex-1">
                  {/* Countries */}
                  <div className="rounded-xl p-4 border border-[#A855F7]/30 bg-gradient-to-r from-[#A855F7]/10 to-[#A855F7]/5 hover:border-[#A855F7]/50 transition-all duration-300 group">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-lg bg-[#A855F7]/20 flex items-center justify-center group-hover:scale-110 transition-transform flex-shrink-0">
                        <svg className="w-6 h-6 text-[#A855F7]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </div>
                      <div className="flex-1">
                        <p className="text-xs font-semibold uppercase tracking-wider text-white/60 mb-1">Countries Visited</p>
                        <p className="text-3xl font-bold text-[#A855F7]">{travelData.stats.countries}</p>
                      </div>
                    </div>
                  </div>

                  {/* Cities */}
                  <div className="rounded-xl p-4 border border-[#A855F7]/30 bg-gradient-to-r from-[#A855F7]/10 to-[#A855F7]/5 hover:border-[#A855F7]/50 transition-all duration-300 group">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-lg bg-[#A855F7]/20 flex items-center justify-center group-hover:scale-110 transition-transform flex-shrink-0">
                        <svg className="w-6 h-6 text-[#A855F7]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                        </svg>
                      </div>
                      <div className="flex-1">
                        <p className="text-xs font-semibold uppercase tracking-wider text-white/60 mb-1">Cities Explored</p>
                        <p className="text-3xl font-bold text-[#A855F7]">{travelData.stats.cities}</p>
                      </div>
                    </div>
                  </div>

                  {/* Recent Destinations */}
                  <div className="rounded-xl p-4 border border-[#A855F7]/30 bg-gradient-to-r from-[#A855F7]/10 to-[#A855F7]/5 flex-1 flex flex-col">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="w-10 h-10 rounded-lg bg-[#A855F7]/20 flex items-center justify-center flex-shrink-0">
                        <svg className="w-5 h-5 text-[#A855F7]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                      </div>
                      <p className="text-xs font-semibold uppercase tracking-wider text-white/60">Recent Destinations</p>
                    </div>
                    <div className="space-y-2 flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent pr-2">
                      {travelData.locations.slice(0, 8).map((location, i: number) => (
                        <div key={i} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-[#A855F7]/10 transition-colors border-b border-white/5 last:border-0">
                          <div className="flex items-center gap-3">
                            <div className="w-2 h-2 rounded-full bg-[#A855F7] shadow-lg shadow-[#A855F7]/50" />
                            <p className="text-sm font-medium text-white">{location.name.split(',')[0]}</p>
                          </div>
                          <p className="text-xs text-white/40 font-mono">{location.duration}</p>
                        </div>
                      ))}
                    </div>
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
