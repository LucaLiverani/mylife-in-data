import { Card } from '@/components/ui/card';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { CHART_COLORS, CHART_STYLES } from './chartConfig';

interface MapsData {
  hourlyActivity: Array<{ hour: string; activities: number }>;
  topDestinations: Array<{ rank: number; city: string; visits: number; days: number }>;
}

export function MapsCharts({ data }: { data: MapsData }) {
  return (
    <>
      {/* Charts Section */}
      <section className="mb-12">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Hourly Activity */}
          <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
            <h2 className="text-2xl font-bold mb-6">Activity by Hour</h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data.hourlyActivity}>
                <CartesianGrid {...CHART_STYLES.cartesianGrid} />
                <XAxis dataKey="hour" stroke="#fff" />
                <YAxis stroke="#fff" />
                <Tooltip contentStyle={CHART_STYLES.tooltip.contentStyle} />
                <Bar dataKey="activities" fill={CHART_COLORS.maps} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          {/* Top Destinations */}
          <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
            <h2 className="text-2xl font-bold mb-6">Most Visited Destinations</h2>
            <div className="space-y-3">
              {data.topDestinations.map((dest) => (
                <div
                  key={dest.rank}
                  className="flex items-center justify-between p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-all"
                >
                  <div className="flex items-center gap-4">
                    <div className="text-2xl font-bold text-[#A855F7] w-8">#{dest.rank}</div>
                    <div>
                      <div className="font-semibold text-lg">{dest.city}</div>
                      <div className="text-sm text-white/60">{dest.visits} visits</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-semibold text-[#A855F7]">{dest.days} days</div>
                    <div className="text-sm text-white/60">total</div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </section>
    </>
  );
}
