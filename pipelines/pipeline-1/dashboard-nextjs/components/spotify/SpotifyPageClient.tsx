"use client";

import dynamic from 'next/dynamic';

const SpotifyCharts = dynamic(() => import('@/components/charts/SpotifyCharts').then(mod => mod.SpotifyCharts), {
  ssr: false,
  loading: () => <div className="text-center text-white/60">Loading charts...</div>,
});

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

export function SpotifyPageClient({ data }: { data: SpotifyFullData }) {
  return <SpotifyCharts data={data} />;
}
