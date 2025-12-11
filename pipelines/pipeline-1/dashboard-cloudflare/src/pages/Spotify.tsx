import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { FadeIn } from '@/components/animations/FadeIn';
import { ParticleBackground } from '@/components/animations/ParticleBackground';
import { KPIMetric } from '@/components/KPIMetric';
import { SpotifyCharts } from '@/components/charts/SpotifyCharts';
import { SpotifyLiveStream } from '@/components/spotify/SpotifyLiveStream';
import { spotifyAPI } from '@/lib/api';

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
  relativeTime: string;
  albumArt: string;
}

export default function SpotifyPage() {
  const [data, setData] = useState<SpotifyFullData | null>(null);
  const [recentTracks, setRecentTracks] = useState<RecentTrack[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [fullData, recent] = await Promise.all([
          spotifyAPI.getData() as Promise<SpotifyFullData>,
          spotifyAPI.getRecent() as Promise<RecentTrack[]>,
        ]);
        setData(fullData);
        setRecentTracks(recent);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch Spotify data:', err);
        setError('Failed to load Spotify data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#1a1a1a] to-[#2d2d2d] text-white">
        <ParticleBackground />
        <div className="relative z-10 flex items-center justify-center min-h-screen">
          <div className="text-center">
            <div className="w-16 h-16 border-4 border-[#1DB954] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-xl text-white/60">Loading Spotify data...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#1a1a1a] to-[#2d2d2d] text-white">
        <ParticleBackground />
        <div className="relative z-10 flex items-center justify-center min-h-screen">
          <div className="text-center">
            <p className="text-xl text-red-400">{error || 'No data available'}</p>
            <Link to="/" className="mt-4 inline-block text-[#1DB954] hover:underline">
              Return to Home
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#1a1a1a] to-[#2d2d2d] text-white">
      <ParticleBackground />

      <div className="relative z-10 max-w-7xl mx-auto px-6 py-20">
        {/* Header */}
        <FadeIn>
          <Link to="/" className="inline-flex items-center gap-2 text-white/60 hover:text-white transition-colors mb-8">
            <ArrowLeft className="w-4 h-4" />
            Back to Dashboard
          </Link>
          <div className="mb-12">
            <h1 className="text-5xl lg:text-7xl font-bold mb-4">
              <span className="text-[#1DB954]">Spotify</span> Analytics
            </h1>
            <p className="text-xl text-white/60 italic">
              A deep dive into my musical obsessions and sonic rabbit holes.
            </p>
          </div>
        </FadeIn>

        {/* Live Stream Section */}
        <section className="mb-12">
          <FadeIn delay={0.1}>
            <h2 className="text-2xl font-bold mb-4 text-white/90">Now Playing</h2>
            <SpotifyLiveStream />
          </FadeIn>
        </section>

        {/* KPI Section */}
        <section className="mb-12">
          <FadeIn delay={0.2}>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <KPIMetric
                label="Total Time"
                value={data.kpis.totalTime}
                color="#1DB954"
              />
              <KPIMetric
                label="Songs Streamed"
                value={data.kpis.songsStreamed}
                color="#1DB954"
              />
              <KPIMetric
                label="Unique Artists"
                value={data.kpis.uniqueArtists}
                color="#1DB954"
              />
              <KPIMetric
                label="Avg Daily"
                value={data.kpis.avgDaily}
                color="#1DB954"
              />
            </div>
          </FadeIn>
        </section>

        {/* Charts Section */}
        <FadeIn delay={0.3}>
          <SpotifyCharts data={data} recentTracks={recentTracks} />
        </FadeIn>
      </div>
    </div>
  );
}
