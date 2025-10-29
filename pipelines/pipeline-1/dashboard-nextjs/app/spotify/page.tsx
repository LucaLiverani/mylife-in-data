import { FadeIn } from '@/components/animations/FadeIn';
import { ParticleBackground } from '@/components/animations/ParticleBackground';
import { KPIMetric } from '@/components/KPIMetric';
import { spotifyAPI } from '@/lib/api';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { SpotifyPageClient } from '@/components/spotify/SpotifyPageClient';
import { SpotifyLiveStream } from '@/components/spotify/SpotifyLiveStream';

export const metadata = {
  title: 'Spotify Stats - My Life in Data',
  description: 'Detailed Spotify listening statistics and analytics',
};

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

export default async function SpotifyPage() {
  const data = await spotifyAPI.getData() as SpotifyFullData;

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#1a1a1a] to-[#2d2d2d] text-white">
      <ParticleBackground />

      <div className="relative z-10 max-w-7xl mx-auto px-6 py-20">
        {/* Header */}
        <FadeIn>
          <Link href="/" className="inline-flex items-center gap-2 text-white/60 hover:text-white transition-colors mb-8">
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

        <FadeIn delay={0.3}>
          <SpotifyPageClient data={data} />
        </FadeIn>
      </div>
    </div>
  );
}