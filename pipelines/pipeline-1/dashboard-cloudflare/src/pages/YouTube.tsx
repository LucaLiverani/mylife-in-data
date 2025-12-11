import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { FadeIn } from '@/components/animations/FadeIn';
import { ParticleBackground } from '@/components/animations/ParticleBackground';
import { KPIMetric } from '@/components/KPIMetric';
import { YouTubeCharts } from '@/components/charts/YouTubeCharts';
import { youtubeAPI } from '@/lib/api';

interface DailyWatchTimeBreakdown {
  date: string;
  watchedHours: number;
  searchesHours: number;
  visitsHours: number;
  adsHours: number;
  otherHours: number;
  totalHours: number;
  watchedCount: number;
  searchesCount: number;
  visitsCount: number;
  adsCount: number;
  dayName: string;
  isWeekend: boolean;
}

interface YouTubeFullData {
  kpis: {
    videosWatched: string;
    totalSearches: string;
    totalAdsWatched: string;
    adsPercentage: string;
    totalWatchTime: string;
    totalChannels: string;
    avgWatchTimePerDay: number;
    enrichmentPercentage: string;
    firstActivityDate: string;
    lastActivityDate: string;
  };
  topChannels: Array<{
    channelId: string;
    channelTitle: string;
    watchCount: number;
    totalWatchTime: string;
    watchTimeHours: number;
    category: string;
    uniqueVideos: number;
  }>;
  categoryBreakdown: Array<{
    name: string;
    watchCount: number;
    watchTime: string;
    watchPercentage: number;
    timePercentage: number;
    uniqueChannels: number;
  }>;
  dailyWatchTimeBreakdown: DailyWatchTimeBreakdown[];
  recentVideos: Array<{ title: string; time: string; relativeTime: string; timeOfDay: string; isFromAds: boolean }>;
  hourlyActivity: Array<{ hour: string; activities: number }>;
}

export default function YouTubePage() {
  const [data, setData] = useState<YouTubeFullData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const result = await youtubeAPI.getData() as YouTubeFullData;
        setData(result);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch YouTube data:', err);
        setError('Failed to load YouTube data');
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
            <div className="w-16 h-16 border-4 border-[#FF0000] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-xl text-white/60">Loading YouTube data...</p>
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
            <Link to="/" className="mt-4 inline-block text-[#FF0000] hover:underline">
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
              <span className="text-[#FF0000]">YouTube</span> Analytics
            </h1>
            <p className="text-xl text-white/60 italic">
              Where productivity goes to die, one autoplay at a time.
            </p>
          </div>
        </FadeIn>

        {/* KPI Section */}
        <section className="mb-12">
          <FadeIn delay={0.1}>
            <h2 className="text-2xl font-bold mb-4">Overview</h2>
            <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
              <KPIMetric
                label="Watch Time"
                value={data.kpis.totalWatchTime}
                color="#FF0000"
              />
              <KPIMetric
                label="Total Channels"
                value={data.kpis.totalChannels}
                color="#FF0000"
              />
              <KPIMetric
                label="Videos Watched"
                value={data.kpis.videosWatched}
                color="#FF0000"
              />
              <KPIMetric
                label="Searches"
                value={data.kpis.totalSearches}
                color="#3b82f6"
              />
              <KPIMetric
                label="Ads Watched"
                value={data.kpis.totalAdsWatched}
                color="#f59e0b"
              />
              <KPIMetric
                label="Ads %"
                value={`${data.kpis.adsPercentage}%`}
                color="#f59e0b"
              />
            </div>
          </FadeIn>
        </section>

        {/* Charts Section */}
        <FadeIn delay={0.2}>
          <YouTubeCharts data={data} />
        </FadeIn>
      </div>
    </div>
  );
}
