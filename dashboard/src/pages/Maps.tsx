import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, AlertTriangle } from 'lucide-react';
import { FadeIn } from '@/components/animations/FadeIn';
import { ParticleBackground } from '@/components/animations/ParticleBackground';
import { KPIMetric } from '@/components/KPIMetric';
import { TravelMap } from '@/components/maps/TravelMap';
import { MapsCharts } from '@/components/charts/MapsCharts';
import { Card } from '@/components/ui/card';
import { travelAPI } from '@/lib/api';

interface TravelData {
  stats: {
    totalActivities: string;
    totalDirections: string;
    totalSearches: string;
    totalExplorations: string;
    likelyVisits: string;
    uniqueDestinations: string;
    daysWithActivity: string;
    daysTracked: string;
    avgActivitiesPerDay: string;
    directionsPct: string;
    searchPct: string;
    explorePct: string;
    firstActivity: string;
    lastActivity: string;
  };
  locations: Array<{ name: string; lat: number; lng: number; duration: string }>;
  charts: {
    hourlyActivity: Array<{ hour: string; activities: number }>;
    lastActivities: Array<{ time: string; location: string; type: string; timeOfDay: string }>;
    topDestinations: Array<{ destination: string; count: number; type: string }>;
    dailyActivity: Array<{ date: string; directions: number; searches: number; explorations: number; other: number }>;
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
        // Check if the data is essentially empty
        if (parseInt(result.stats.totalActivities) === 0) {
          setError('No Google Maps activity data available.');
        } else {
          setTravelData(result);
          setError(null);
        }
      } catch (err) {
        console.error('Failed to fetch travel data:', err);
        setError('Failed to load travel data from the API.');
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

        {/* Error/No Data Message */}
        {error && !travelData && (
          <FadeIn delay={0.1}>
            <Card className="p-8 bg-yellow-500/10 border border-yellow-500/20 text-yellow-300">
              <div className="flex items-center gap-4">
                <AlertTriangle className="w-8 h-8" />
                <div>
                  <h2 className="text-xl font-bold">Data Not Available</h2>
                  <p className="text-yellow-300/80 mt-1">{error}</p>
                  <p className="text-yellow-300/60 text-sm mt-2">
                    Please check your Google Takeout export and the data ingestion pipeline to ensure specific location data is being processed.
                  </p>
                </div>
              </div>
            </Card>
          </FadeIn>
        )}

        {/* Data Display */}
        {travelData && (
          <>
            {/* KPI Section */}
            <section className="mb-12">
              <FadeIn delay={0.1}>
                <h2 className="text-2xl font-bold mb-4">Overview</h2>
                <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
                  <KPIMetric
                    label="Total Activities"
                    value={travelData.stats.totalActivities}
                    color="#A855F7"
                  />
                  <KPIMetric
                    label="Directions"
                    value={travelData.stats.totalDirections}
                    color="#10b981"
                  />
                  <KPIMetric
                    label="Searches"
                    value={travelData.stats.totalSearches}
                    color="#3b82f6"
                  />
                  <KPIMetric
                    label="Explorations"
                    value={travelData.stats.totalExplorations}
                    color="#f59e0b"
                  />
                  <KPIMetric
                    label="Destinations"
                    value={travelData.stats.uniqueDestinations}
                    color="#A855F7"
                  />
                  <KPIMetric
                    label="Avg/Day"
                    value={travelData.stats.avgActivitiesPerDay}
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
              <MapsCharts data={travelData.charts} />
            </FadeIn>
          </>
        )}
      </div>
    </div>
  );
}
