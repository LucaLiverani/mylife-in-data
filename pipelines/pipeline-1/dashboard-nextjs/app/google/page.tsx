import { FadeIn } from '@/components/animations/FadeIn';
import { ParticleBackground } from '@/components/animations/ParticleBackground';
import { KPIMetric } from '@/components/KPIMetric';
import { GooglePageClient } from '@/components/google/GooglePageClient';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export const metadata = {
  title: 'Google Search Stats - My Life in Data',
  description: 'Detailed Google Search statistics and analytics',
};

// Mock data
const mockData = {
  kpis: {
    totalQueries: '12,847',
    categories: '23',
    avgDaily: '35',
    topCategory: 'Technology',
  },
  topSearches: [
    { query: 'nextjs best practices', count: 127 },
    { query: 'typescript generics', count: 98 },
    { query: 'react hooks optimization', count: 87 },
    { query: 'tailwind css dark mode', count: 76 },
    { query: 'fastapi python tutorial', count: 65 },
    { query: 'docker compose examples', count: 54 },
    { query: 'web performance tips', count: 43 },
    { query: 'javascript async await', count: 38 },
  ],
  categories: [
    { name: 'Technology', value: 35 },
    { name: 'Programming', value: 28 },
    { name: 'Web Development', value: 22 },
    { name: 'Data Science', value: 8 },
    { name: 'Other', value: 7 },
  ],
  dailySearches: Array.from({ length: 30 }, (_, i) => ({
    date: new Date(Date.now() - (29 - i) * 24 * 60 * 60 * 1000).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    searches: Math.floor(Math.random() * 30 + 20),
  })),
  timeOfDay: [
    { hour: '00-03', searches: 5 },
    { hour: '03-06', searches: 2 },
    { hour: '06-09', searches: 18 },
    { hour: '09-12', searches: 45 },
    { hour: '12-15', searches: 52 },
    { hour: '15-18', searches: 48 },
    { hour: '18-21', searches: 38 },
    { hour: '21-24', searches: 22 },
  ],
};

export default function GooglePage() {
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
              <span className="text-[#4285F4]">Google Search</span> Analytics
            </h1>
            <p className="text-xl text-white/60 italic">
              Proof that I don&apos;t know everything, but I know how to Google it.
            </p>
          </div>
        </FadeIn>

        {/* KPI Section */}
        <section className="mb-12">
          <FadeIn delay={0.1}>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <KPIMetric
                label="Total Queries"
                value={mockData.kpis.totalQueries}
                color="#4285F4"
              />
              <KPIMetric
                label="Categories"
                value={mockData.kpis.categories}
                color="#4285F4"
              />
              <KPIMetric
                label="Avg Daily"
                value={mockData.kpis.avgDaily}
                color="#4285F4"
              />
              <KPIMetric
                label="Top Category"
                value={mockData.kpis.topCategory}
                color="#4285F4"
              />
            </div>
          </FadeIn>
        </section>

        <FadeIn delay={0.2}>
          <GooglePageClient data={mockData} />
        </FadeIn>
      </div>
    </div>
  );
}
