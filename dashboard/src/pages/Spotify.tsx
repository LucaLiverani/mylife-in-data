import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { FadeIn } from '@/components/animations/FadeIn';
import { KPIMetric } from '@/components/KPIMetric';
import { KpiSince } from '@/components/KpiSince';
import { SpotifyCharts } from '@/components/charts/SpotifyCharts';
import { SpotifyLiveStream } from '@/components/spotify/SpotifyLiveStream';
import { spotifyAPI } from '@/lib/api';

interface SpotifyFullData {
  kpis: {
    totalTime: number | string;
    songsStreamed: number | string;
    uniqueArtists: number | string;
    avgDaily: number | string;
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
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-rack-black to-rack-charcoal text-signal-white">
        <p className="font-mono text-sm uppercase tracking-wider text-signal-white/60">Cuing up the listening channel…</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-rack-black to-rack-charcoal text-signal-white">
        <div className="mx-auto max-w-2xl px-4 py-20 sm:px-6">
          <p className="mb-4 font-mono text-xs uppercase tracking-wider text-trace-down">{error || 'No signal on this channel.'}</p>
          <Link to="/" className="font-mono text-xs uppercase tracking-wider text-signal-white/60 hover:text-signal-white">
            Back to console
          </Link>
        </div>
      </main>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-rack-black to-rack-charcoal text-signal-white">

      <div className="relative z-10 max-w-7xl mx-auto px-4 py-12 sm:px-6 sm:py-20">
        {/* Header */}
        <FadeIn>
          <Link to="/" className="inline-flex items-center gap-2 text-signal-white/60 hover:text-signal-white transition-colors mb-8">
            <ArrowLeft className="w-4 h-4" />
            Back to Dashboard
          </Link>
          <div className="mb-12">
            <h1 className="text-4xl sm:text-5xl lg:text-7xl font-bold mb-4">
              <span className="text-channel-green">Spotify</span> Analytics
            </h1>
            <p className="text-xl text-signal-white/60 italic">
              Documenting my questionable taste in music, one play at a time.
            </p>
          </div>
        </FadeIn>

        {/* Live Stream Section */}
        <section className="mb-12">
          <FadeIn delay={0.1}>
            <h2 className="text-2xl font-bold mb-4 text-signal-white/90">Now Playing</h2>
            <SpotifyLiveStream />
          </FadeIn>
        </section>

        {/* KPI Section */}
        <section className="mb-12">
          <FadeIn delay={0.2}>
            <h2 className="mb-4 font-mono text-xs uppercase tracking-wider text-signal-white/60">Overview<KpiSince /></h2>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <KPIMetric label="Hours"     value={data.kpis.totalTime}     kind="hours" channel="spotify" />
              <KPIMetric label="Artists"   value={data.kpis.uniqueArtists} kind="count" channel="spotify" />
              <KPIMetric label="Songs"     value={data.kpis.songsStreamed} kind="count" channel="spotify" />
              <KPIMetric label="Avg / day" value={data.kpis.avgDaily}      kind="hours" channel="spotify" />
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
