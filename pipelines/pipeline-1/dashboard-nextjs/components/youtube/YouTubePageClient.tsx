"use client";

import { Card } from '@/components/ui/card';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';

export function YouTubePageClient({ data }: { data: any }) {
  return (
    <>
      {/* Charts Section */}
      <section className="mb-12">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Top Channels */}
          <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
            <h2 className="text-2xl font-bold mb-6">Top Channels</h2>
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={data.topChannels} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis type="number" stroke="#fff" />
                <YAxis type="category" dataKey="name" stroke="#fff" width={140} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: '8px',
                  }}
                />
                <Bar dataKey="videos" fill="#FF0000" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          {/* Category Distribution */}
          <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
            <h2 className="text-2xl font-bold mb-6">Content Categories</h2>
            <div className="space-y-4 pt-8">
              {data.categories.map((cat: any, i: number) => (
                <div key={i} className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>{cat.name}</span>
                    <span className="text-[#FF0000] font-semibold">{cat.value}%</span>
                  </div>
                  <div className="w-full bg-white/10 rounded-full h-3">
                    <div
                      className="bg-gradient-to-r from-[#FF0000] to-[#CC0000] h-3 rounded-full transition-all duration-500"
                      style={{ width: `${cat.value}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </section>

      {/* Watch Time Trend */}
      <section className="mb-12">
        <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
          <h2 className="text-2xl font-bold mb-6">Daily Watch Time (Last 30 Days)</h2>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={data.watchTime}>
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
              <Area type="monotone" dataKey="hours" stroke="#FF0000" fill="#FF000040" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      </section>

      {/* Channel Details */}
      <section>
        <Card className="p-8 bg-white/5 backdrop-blur-sm border-white/10">
          <h2 className="text-2xl font-bold mb-6">Channel Details</h2>
          <div className="space-y-4">
            {data.topChannels.map((channel: any, i: number) => (
              <div
                key={i}
                className="flex items-center justify-between p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-all"
              >
                <div className="flex items-center gap-4">
                  <div className="text-2xl font-bold text-[#FF0000] w-8">#{i + 1}</div>
                  <div>
                    <div className="font-semibold text-lg">{channel.name}</div>
                    <div className="text-sm text-white/60">{channel.category}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-semibold">{channel.videos} videos</div>
                  <div className="text-sm text-white/60">{channel.hours} hours</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </section>
    </>
  );
}
