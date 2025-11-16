import { useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { CHART_COLORS, CHART_STYLES, formatChartDate } from './chartConfig';

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

  // Transform the data for Recharts - ensure numeric values
  const chartData = data.dates.map((date, i) => ({
    date: formatChartDate(date),
    Spotify: Number(data.spotify[i]) || 0,
    YouTube: Number(data.youtube[i]) || 0,
    Google: Number(data.google[i]) || 0,
    Maps: Number(data.maps[i]) || 0,
  }));

  const toggleSeries = (series: keyof typeof visibleSeries) => {
    setVisibleSeries(prev => ({ ...prev, [series]: !prev[series] }));
  };

  const series = [
    { name: 'Spotify', color: CHART_COLORS.spotify },
    { name: 'YouTube', color: CHART_COLORS.youtube },
    { name: 'Google', color: CHART_COLORS.google },
    { name: 'Maps', color: CHART_COLORS.maps },
  ] as const;

  // Calculate KPIs - ensure values are numbers to prevent string concatenation
  const totalSpotify = data.spotify.reduce((a, b) => Number(a) + Number(b), 0);
  const totalYouTube = data.youtube.reduce((a, b) => Number(a) + Number(b), 0);
  const totalGoogle = data.google.reduce((a, b) => Number(a) + Number(b), 0);
  const totalMaps = data.maps.reduce((a, b) => Number(a) + Number(b), 0);

  const mostActive = [
    { name: 'Spotify', total: totalSpotify, color: CHART_COLORS.spotify },
    { name: 'YouTube', total: totalYouTube, color: CHART_COLORS.youtube },
    { name: 'Google', total: totalGoogle, color: CHART_COLORS.google },
    { name: 'Maps', total: totalMaps, color: CHART_COLORS.maps },
  ].sort((a, b) => b.total - a.total)[0];

  return (
    <div className="flex flex-col h-full">
      {/* Stats and KPIs */}
      <div className="flex justify-between items-start mb-6">
        {/* Left side: Main stats */}
        <div className="flex gap-8">
          <div>
            <p className="text-xs text-white/50 mb-1">This Month</p>
            <p className="text-2xl font-bold text-white">{parseInt(totalEvents).toLocaleString()}</p>
            <p className="text-xs text-white/40">events</p>
          </div>
          <div>
            <p className="text-xs text-white/50 mb-1">Daily Average</p>
            <p className="text-2xl font-bold text-white">{parseInt(avgPerDay).toLocaleString()}</p>
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
            onClick={() => toggleSeries(s.name)}
            className="flex items-center gap-2 transition-opacity"
            style={{ opacity: visibleSeries[s.name] ? 1 : 0.4 }}
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
                <stop offset="5%" stopColor={CHART_COLORS.spotify} stopOpacity={0.3}/>
                <stop offset="95%" stopColor={CHART_COLORS.spotify} stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="colorYouTube" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={CHART_COLORS.youtube} stopOpacity={0.3}/>
                <stop offset="95%" stopColor={CHART_COLORS.youtube} stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="colorGoogle" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={CHART_COLORS.google} stopOpacity={0.3}/>
                <stop offset="95%" stopColor={CHART_COLORS.google} stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="colorMaps" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={CHART_COLORS.maps} stopOpacity={0.3}/>
                <stop offset="95%" stopColor={CHART_COLORS.maps} stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid {...CHART_STYLES.cartesianGrid} />
            <XAxis
              dataKey="date"
              {...CHART_STYLES.timeSeriesXAxis}
            />
            <YAxis
              stroke="#fff"
              tick={{ fill: 'rgba(255, 255, 255, 0.7)' }}
              tickLine={{ stroke: 'rgba(255, 255, 255, 0.1)' }}
              label={{ value: 'Events', angle: -90, position: 'insideLeft', fill: 'rgba(255, 255, 255, 0.7)' }}
            />
            <Tooltip
              contentStyle={CHART_STYLES.tooltip.contentStyle}
              cursor={CHART_STYLES.tooltip.cursor}
            />
            {visibleSeries.Spotify && (
              <Area
                type="monotone"
                dataKey="Spotify"
                stackId="1"
                stroke={CHART_COLORS.spotify}
                strokeWidth={2}
                fill="url(#colorSpotify)"
                dot={{ fill: CHART_COLORS.spotify, r: 3 }}
                activeDot={{ r: 5 }}
              />
            )}
            {visibleSeries.YouTube && (
              <Area
                type="monotone"
                dataKey="YouTube"
                stackId="1"
                stroke={CHART_COLORS.youtube}
                strokeWidth={2}
                fill="url(#colorYouTube)"
                dot={{ fill: CHART_COLORS.youtube, r: 3 }}
                activeDot={{ r: 5 }}
              />
            )}
            {visibleSeries.Google && (
              <Area
                type="monotone"
                dataKey="Google"
                stackId="1"
                stroke={CHART_COLORS.google}
                strokeWidth={2}
                fill="url(#colorGoogle)"
                dot={{ fill: CHART_COLORS.google, r: 3 }}
                activeDot={{ r: 5 }}
              />
            )}
            {visibleSeries.Maps && (
              <Area
                type="monotone"
                dataKey="Maps"
                stackId="1"
                stroke={CHART_COLORS.maps}
                strokeWidth={2}
                fill="url(#colorMaps)"
                dot={{ fill: CHART_COLORS.maps, r: 3 }}
                activeDot={{ r: 5 }}
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
