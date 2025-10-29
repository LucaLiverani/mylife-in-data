'use client';

import dynamic from 'next/dynamic';

// Load TravelMap only on client to avoid SSR issues with Leaflet
const TravelMap = dynamic(() => import('@/components/TravelMap').then(mod => ({ default: mod.TravelMap })), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full bg-white/5 rounded-xl border border-white/10 flex items-center justify-center">
      <p className="text-white/50">Loading map...</p>
    </div>
  ),
});

interface TravelMapClientProps {
  locations: Array<{
    name: string;
    lat: number;
    lng: number;
    duration: string;
  }>;
}

export function TravelMapClient({ locations }: TravelMapClientProps) {
  return <TravelMap locations={locations} />;
}
