import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { FadeIn } from '@/components/animations/FadeIn';
import { KPIMetric } from '@/components/KPIMetric';
import { KpiSince } from '@/components/KpiSince';
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
    videosWatched: number | string;
    totalSearches: number | string;
    totalAdsWatched: number | string;
    adsPercentage: number | string;
    totalWatchTime: number | string;
    totalChannels: number | string;
    avgWatchTimePerDay: number;
    enrichmentPercentage: number | string;
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
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-rack-black to-rack-charcoal text-signal-white">
        <p className="font-mono text-sm uppercase tracking-wider text-signal-white/60">Loading the watch log…</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-rack-black to-rack-charcoal text-signal-white">
        <div className="mx-auto max-w-2xl px-6 py-20">
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

      <div className="relative z-10 max-w-7xl mx-auto px-6 py-20">
        {/* Header */}
        <FadeIn>
          <Link to="/" className="inline-flex items-center gap-2 text-signal-white/60 hover:text-signal-white transition-colors mb-8">
            <ArrowLeft className="w-4 h-4" />
            Back to Dashboard
          </Link>
          <div className="mb-12">
            <h1 className="text-5xl lg:text-7xl font-bold mb-4">
              <span className="text-channel-red">YouTube</span> Analytics
            </h1>
            <p className="text-xl text-signal-white/60 italic">
              Where productivity goes to die, one autoplay at a time.
            </p>
          </div>
        </FadeIn>

        {/* KPI Section */}
        <section className="mb-12">
          <FadeIn delay={0.1}>
            <h2 className="mb-4 font-mono text-xs uppercase tracking-wider text-signal-white/60">Overview<KpiSince /></h2>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <KPIMetric label="Hours"    value={data.kpis.totalWatchTime} kind="hours"   channel="youtube" />
              <KPIMetric label="Channels" value={data.kpis.totalChannels}  kind="count"   channel="youtube" />
              <KPIMetric label="Videos"   value={data.kpis.videosWatched}  kind="count"   channel="youtube" />
              <KPIMetric label="Ads"      value={data.kpis.adsPercentage}  kind="percent" channel="youtube" />
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
