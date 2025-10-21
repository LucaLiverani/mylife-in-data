"use client";

import { Card } from '@/components/ui/card';
import { TravelMap } from '@/components/TravelMap';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export function MapsPageClient({ travelData, mockData }: { travelData: any, mockData: any }) {
  return (
    <>
      {/* Map Section */}
      <section className="mb-12">
        <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
          <h2 className="text-2xl font-bold mb-6">Travel Map</h2>
          <div className="h-[500px] rounded-lg overflow-hidden">
            <TravelMap locations={travelData.locations} />
          </div>
        </Card>
      </section>

      {/* Charts Section */}
      <section className="mb-12">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Monthly Trips */}
          <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
            <h2 className="text-2xl font-bold mb-6">Trips by Month</h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={mockData.monthlyTrips}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="month" stroke="#fff" />
                <YAxis stroke="#fff" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: '8px',
                  }}
                />
                <Bar dataKey="trips" fill="#A855F7" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          {/* Continents Distribution */}
          <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
            <h2 className="text-2xl font-bold mb-6">Cities by Continent</h2>
            <div className="space-y-4 pt-8">
              {mockData.continents.map((continent: any, i: number) => (
                <div key={i} className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>{continent.name}</span>
                    <span className="text-[#A855F7] font-semibold">{continent.cities} cities</span>
                  </div>
                  <div className="w-full bg-white/10 rounded-full h-3">
                    <div
                      className="bg-gradient-to-r from-[#A855F7] to-[#9333EA] h-3 rounded-full transition-all duration-500"
                      style={{ width: `${continent.percentage}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </section>

      {/* Top Destinations */}
      <section>
        <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
          <h2 className="text-2xl font-bold mb-6">Most Visited Destinations</h2>
          <div className="space-y-3">
            {mockData.topDestinations.map((dest: any, i: number) => (
              <div
                key={i}
                className="flex items-center justify-between p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-all"
              >
                <div className="flex items-center gap-4">
                  <div className="text-2xl font-bold text-[#A855F7] w-8">#{i + 1}</div>
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
      </section>
    </>
  );
}
