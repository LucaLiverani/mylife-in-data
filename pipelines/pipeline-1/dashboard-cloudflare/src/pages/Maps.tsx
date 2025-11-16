import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { FadeIn } from '@/components/animations/FadeIn';
import { ParticleBackground } from '@/components/animations/ParticleBackground';
import { KPIMetric } from '@/components/KPIMetric';
import { TravelMap } from '@/components/maps/TravelMap';
import { MapsCharts } from '@/components/charts/MapsCharts';
import { Card } from '@/components/ui/card';
import { travelAPI } from '@/lib/api';

// Mock additional data
const mockData = {
  monthlyTrips: [
    { month: 'Jan', trips: 2 },
    { month: 'Feb', trips: 1 },
    { month: 'Mar', trips: 3 },
    { month: 'Apr', trips: 2 },
    { month: 'May', trips: 4 },
    { month: 'Jun', trips: 3 },
    { month: 'Jul', trips: 5 },
    { month: 'Aug', trips: 2 },
    { month: 'Sep', trips: 3 },
    { month: 'Oct', trips: 2 },
    { month: 'Nov', trips: 1 },
    { month: 'Dec', trips: 2 },
  ],
  continents: [
    { name: 'Europe', cities: 12, percentage: 52 },
    { name: 'Asia', cities: 6, percentage: 26 },
    { name: 'North America', cities: 4, percentage: 17 },
    { name: 'South America', cities: 1, percentage: 5 },
  ],
  topDestinations: [
    { city: 'Paris, France', visits: 5, days: 24 },
    { city: 'Tokyo, Japan', visits: 4, days: 28 },
    { city: 'London, UK', visits: 4, days: 20 },
    { city: 'Barcelona, Spain', visits: 3, days: 21 },
    { city: 'New York, USA', visits: 3, days: 15 },
  ],
};

interface TravelData {
  locations: Array<{ name: string; lat: number; lng: number; date: string; duration: string }>;
  stats: {
    totalDistance: string;
    countries: string;
    cities: string;
    longestTrip: string;
  };
}

export default function MapsPage() {
  const [travelData, setTravelData] = useState<TravelData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const result = await travelAPI.getData() as TravelData;
        setTravelData(result);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch travel data:', err);
        setError('Failed to load travel data');
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
            <div className="w-16 h-16 border-4 border-[#A855F7] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-xl text-white/60">Loading travel data...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error || !travelData) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#1a1a1a] to-[#2d2d2d] text-white">
        <ParticleBackground />
        <div className="relative z-10 flex items-center justify-center min-h-screen">
          <div className="text-center">
            <p className="text-xl text-red-400">{error || 'No data available'}</p>
            <Link to="/" className="mt-4 inline-block text-[#A855F7] hover:underline">
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
              <span className="text-[#A855F7]">Travel</span> Analytics
            </h1>
            <p className="text-xl text-white/60 italic">
              Collecting passport stamps and existential crises since 2024.
            </p>
          </div>
        </FadeIn>

        {/* KPI Section */}
        <section className="mb-12">
          <FadeIn delay={0.1}>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <KPIMetric
                label="Total Distance"
                value={travelData.stats.totalDistance}
                color="#A855F7"
              />
              <KPIMetric
                label="Countries"
                value={travelData.stats.countries}
                color="#A855F7"
              />
              <KPIMetric
                label="Cities"
                value={travelData.stats.cities}
                color="#A855F7"
              />
              <KPIMetric
                label="Longest Trip"
                value={travelData.stats.longestTrip}
                color="#A855F7"
              />
            </div>
          </FadeIn>
        </section>

        {/* Map Section */}
        <section className="mb-12">
          <FadeIn delay={0.2}>
            <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
              <h2 className="text-2xl font-bold mb-6">Travel Map</h2>
              <div className="h-[500px] rounded-lg overflow-hidden">
                <TravelMap locations={travelData.locations} />
              </div>
            </Card>
          </FadeIn>
        </section>

        {/* Charts Section */}
        <FadeIn delay={0.3}>
          <MapsCharts mockData={mockData} />
        </FadeIn>
      </div>
    </div>
  );
}
