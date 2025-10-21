'use client';

import { useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface DataGenerationChartProps {
  data: {
    dates: string[];
    spotify: number[];
    youtube: number[];
    google: number[];
    maps: number[];
  };
  totalEvents: string;
  avgPerDay: string;
}

export function DataGenerationChart({ data, totalEvents, avgPerDay }: DataGenerationChartProps) {
  const [visibleSeries, setVisibleSeries] = useState({
    Spotify: true,
    YouTube: true,
    Google: true,
    Maps: true,
  });

  // Transform the data for Recharts
  const chartData = data.dates.map((date, i) => ({
    date: new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    Spotify: data.spotify[i],
    YouTube: data.youtube[i],
    Google: data.google[i],
    Maps: data.maps[i],
  }));

  const toggleSeries = (series: keyof typeof visibleSeries) => {
    setVisibleSeries(prev => ({ ...prev, [series]: !prev[series] }));
  };

  const series = [
    { name: 'Spotify', color: '#1DB954' },
    { name: 'YouTube', color: '#FF0000' },
    { name: 'Google', color: '#4285F4' },
    { name: 'Maps', color: '#A855F7' },
  ];

  // Calculate KPIs
  const totalSpotify = data.spotify.reduce((a, b) => a + b, 0);
  const totalYouTube = data.youtube.reduce((a, b) => a + b, 0);
  const totalGoogle = data.google.reduce((a, b) => a + b, 0);
  const totalMaps = data.maps.reduce((a, b) => a + b, 0);

  const mostActive = [
    { name: 'Spotify', total: totalSpotify, color: '#1DB954' },
    { name: 'YouTube', total: totalYouTube, color: '#FF0000' },
    { name: 'Google', total: totalGoogle, color: '#4285F4' },
    { name: 'Maps', total: totalMaps, color: '#A855F7' },
  ].sort((a, b) => b.total - a.total)[0];

  return (
    <div className="flex flex-col h-full">
      {/* Stats and KPIs */}
      <div className="flex justify-between items-start mb-6">
        {/* Left side: Main stats */}
        <div className="flex gap-8">
          <div>
            <p className="text-xs text-white/50 mb-1">This Month</p>
            <p className="text-2xl font-bold text-white">{totalEvents}</p>
            <p className="text-xs text-white/40">events</p>
          </div>
          <div>
            <p className="text-xs text-white/50 mb-1">Daily Average</p>
            <p className="text-2xl font-bold text-white">{avgPerDay}</p>
            <p className="text-xs text-white/40">events/day</p>
          </div>
        </div>

        {/* Right side: Most Active KPI */}
        <div className="text-right">
          <p className="text-xs text-white/50 mb-1">Most Active</p>
          <p className="text-xl font-bold" style={{ color: mostActive.color }}>{mostActive.name}</p>
          <p className="text-xs text-white/40">{mostActive.total.toLocaleString()} events</p>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-4 mb-4">
        {series.map((s) => (
          <button
            key={s.name}
            onClick={() => toggleSeries(s.name as keyof typeof visibleSeries)}
            className="flex items-center gap-2 transition-opacity"
            style={{ opacity: visibleSeries[s.name as keyof typeof visibleSeries] ? 1 : 0.4 }}
          >
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: s.color }}
            />
            <span className="text-sm text-white/80">{s.name}</span>
          </button>
        ))}
      </div>

      {/* Chart */}
      <div className="flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="colorSpotify" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#1DB954" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#1DB954" stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="colorYouTube" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#FF0000" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#FF0000" stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="colorGoogle" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#4285F4" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#4285F4" stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="colorMaps" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#A855F7" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#A855F7" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.1)" />
            <XAxis
              dataKey="date"
              stroke="rgba(255, 255, 255, 0.5)"
              tick={{ fill: 'rgba(255, 255, 255, 0.7)' }}
              tickLine={{ stroke: 'rgba(255, 255, 255, 0.1)' }}
            />
            <YAxis
              stroke="rgba(255, 255, 255, 0.5)"
              tick={{ fill: 'rgba(255, 255, 255, 0.7)' }}
              tickLine={{ stroke: 'rgba(255, 255, 255, 0.1)' }}
              label={{ value: 'Events', angle: -90, position: 'insideLeft', fill: 'rgba(255, 255, 255, 0.7)' }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'rgba(0, 0, 0, 0.9)',
                border: '1px solid rgba(255, 255, 255, 0.2)',
                borderRadius: '8px',
                color: '#fff'
              }}
              cursor={{ stroke: 'rgba(255, 255, 255, 0.2)', strokeWidth: 1 }}
            />
            {visibleSeries.Spotify && (
              <Area
                type="monotone"
                dataKey="Spotify"
                stackId="1"
                stroke="#1DB954"
                strokeWidth={2}
                fill="url(#colorSpotify)"
                dot={{ fill: '#1DB954', r: 3 }}
                activeDot={{ r: 5 }}
              />
            )}
            {visibleSeries.YouTube && (
              <Area
                type="monotone"
                dataKey="YouTube"
                stackId="1"
                stroke="#FF0000"
                strokeWidth={2}
                fill="url(#colorYouTube)"
                dot={{ fill: '#FF0000', r: 3 }}
                activeDot={{ r: 5 }}
              />
            )}
            {visibleSeries.Google && (
              <Area
                type="monotone"
                dataKey="Google"
                stackId="1"
                stroke="#4285F4"
                strokeWidth={2}
                fill="url(#colorGoogle)"
                dot={{ fill: '#4285F4', r: 3 }}
                activeDot={{ r: 5 }}
              />
            )}
            {visibleSeries.Maps && (
              <Area
                type="monotone"
                dataKey="Maps"
                stackId="1"
                stroke="#A855F7"
                strokeWidth={2}
                fill="url(#colorMaps)"
                dot={{ fill: '#A855F7', r: 3 }}
                activeDot={{ r: 5 }}
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
