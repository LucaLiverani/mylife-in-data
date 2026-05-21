/**
 * Shared chart configuration — uses tokens from tailwind.config.js + lib/channels.ts.
 * Recharts needs literal CSS color strings, so we expose them via CHANNEL_HEX.
 */
import { CHANNEL_HEX } from '@/lib/channels';

export const CHART_COLORS = {
  spotify:  CHANNEL_HEX.spotify,
  youtube:  CHANNEL_HEX.youtube,
  maps:     CHANNEL_HEX.maps,
  calendar: CHANNEL_HEX.calendar,
  traceUp:   '#34D399',
  traceDown: '#F87171',
  // Tonal shades for multi-series Spotify charts (kept for now; consider replacing
  // with a single accent + neutral siblings during a future /impeccable colorize pass).
  spotifyShades: ['#1DB954', '#1ED760', '#1AA34A', '#168B3E', '#117A32'],
  youtubeShades: ['#FF0000', '#FF3333', '#FF6666', '#FF9999', '#FFCCCC'],
} as const;

export const CHART_STYLES = {
  cartesianGrid: {
    strokeDasharray: '3 3',
    stroke: 'rgba(255, 255, 255, 0.1)',
  },
  axis: {
    stroke: 'rgba(255, 255, 255, 0.5)',
    tick: { fill: 'rgba(255, 255, 255, 0.7)' },
    tickLine: { stroke: 'rgba(255, 255, 255, 0.1)' },
  },
  tooltip: {
    contentStyle: {
      backgroundColor: 'rgba(26, 26, 26, 0.95)',
      border: '1px solid rgba(255, 255, 255, 0.2)',
      borderRadius: '8px',
      color: '#fff',
      fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
    },
    // Recharts renders these as separate nodes that don't inherit contentStyle.color.
    itemStyle:  { color: '#fff' },
    labelStyle: { color: 'rgba(255,255,255,0.7)' },
    cursor: {
      stroke: 'rgba(255, 255, 255, 0.2)',
      strokeWidth: 1,
    },
  },
  timeSeriesXAxis: {
    stroke: '#fff',
    angle: -45,
    textAnchor: 'end' as const,
    height: 80,
    tick: { fontSize: 12 },
  },
} as const;

export const TIME_SERIES_CHART_HEIGHT = 300;

export const formatChartDate = (date: string | Date): string => {
  const d = new Date(date);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

export const formatDetailedDate = (date: string | Date): string => {
  const d = new Date(date);
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${months[d.getMonth()]} ${d.getDate()}`;
};
