"use client";

import { Card } from '@/components/ui/card';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';

export function GooglePageClient({ data }: { data: any }) {
  return (
    <>
      {/* Charts Section */}
      <section className="mb-12">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Search Time Distribution */}
          <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
            <h2 className="text-2xl font-bold mb-6">Search Activity by Time</h2>
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={data.timeOfDay}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="hour" stroke="#fff" />
                <YAxis stroke="#fff" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: '8px',
                  }}
                />
                <Bar dataKey="searches" fill="#4285F4" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          {/* Category Distribution */}
          <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
            <h2 className="text-2xl font-bold mb-6">Search Categories</h2>
            <div className="space-y-4 pt-8">
              {data.categories.map((cat: any, i: number) => (
                <div key={i} className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>{cat.name}</span>
                    <span className="text-[#4285F4] font-semibold">{cat.value}%</span>
                  </div>
                  <div className="w-full bg-white/10 rounded-full h-3">
                    <div
                      className="bg-gradient-to-r from-[#4285F4] to-[#34A853] h-3 rounded-full transition-all duration-500"
                      style={{ width: `${cat.value}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </section>

      {/* Daily Search Trend */}
      <section className="mb-12">
        <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
          <h2 className="text-2xl font-bold mb-6">Daily Search Volume (Last 30 Days)</h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data.dailySearches}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
              <XAxis dataKey="date" stroke="#fff" />
              <YAxis stroke="#fff" />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(0,0,0,0.8)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '8px',
                }}
              />
              <Line type="monotone" dataKey="searches" stroke="#4285F4" strokeWidth={2} dot={{ fill: '#4285F4', r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      </section>

      {/* Top Searches */}
      <section>
        <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
          <h2 className="text-2xl font-bold mb-6">Top Searches</h2>
          <div className="space-y-3">
            {data.topSearches.map((search: any, i: number) => (
              <div
                key={i}
                className="flex items-center justify-between p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-all"
              >
                <div className="flex items-center gap-4">
                  <div className="text-2xl font-bold text-[#4285F4] w-8">#{i + 1}</div>
                  <div className="font-mono text-sm text-white/90">{search.query}</div>
                </div>
                <div className="text-right">
                  <div className="font-semibold text-[#4285F4]">{search.count} times</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </section>
    </>
  );
}
