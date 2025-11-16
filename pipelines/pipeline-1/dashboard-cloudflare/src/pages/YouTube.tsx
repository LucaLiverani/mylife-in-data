import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { FadeIn } from '@/components/animations/FadeIn';
import { ParticleBackground } from '@/components/animations/ParticleBackground';
import { KPIMetric } from '@/components/KPIMetric';
import { YouTubeCharts } from '@/components/charts/YouTubeCharts';

// Mock data
const mockData = {
  kpis: {
    totalVideos: '3,456',
    totalHours: '892 hrs',
    channels: '156',
    avgDaily: '2.4 hrs',
  },
  topChannels: [
    { name: 'Fireship', videos: 247, hours: 82.3, category: 'Tech' },
    { name: 'Web Dev Simplified', videos: 198, hours: 66.1, category: 'Tech' },
    { name: 'Traversy Media', videos: 156, hours: 52.0, category: 'Tech' },
    { name: 'Jack Herrington', videos: 143, hours: 47.7, category: 'Tech' },
    { name: 'Hussein Nasser', videos: 128, hours: 42.7, category: 'Tech' },
  ],
  categories: [
    { name: 'Technology', value: 45 },
    { name: 'Education', value: 25 },
    { name: 'Entertainment', value: 15 },
    { name: 'Music', value: 10 },
    { name: 'Gaming', value: 5 },
  ],
  watchTime: Array.from({ length: 30 }, (_, i) => ({
    date: new Date(Date.now() - (29 - i) * 24 * 60 * 60 * 1000).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    hours: Math.random() * 4 + 1,
  })),
};

export default function YouTubePage() {
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
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <KPIMetric
                label="Total Videos"
                value={mockData.kpis.totalVideos}
                color="#FF0000"
              />
              <KPIMetric
                label="Watch Time"
                value={mockData.kpis.totalHours}
                color="#FF0000"
              />
              <KPIMetric
                label="Channels"
                value={mockData.kpis.channels}
                color="#FF0000"
              />
              <KPIMetric
                label="Avg Daily"
                value={mockData.kpis.avgDaily}
                color="#FF0000"
              />
            </div>
          </FadeIn>
        </section>

        {/* Charts Section */}
        <FadeIn delay={0.2}>
          <YouTubeCharts data={mockData} />
        </FadeIn>
      </div>
    </div>
  );
}
