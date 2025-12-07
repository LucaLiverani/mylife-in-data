/**
 * Shared chart configuration for consistent styling across all charts
 */

export const CHART_COLORS = {
  spotify: '#1DB954', // Green for Spotify
  youtube: '#FF0000',
  google: '#4285F4',
  maps: '#A855F7',    // Purple for Maps
  // Gradient shades for multi-series charts
  spotifyShades: ['#1DB954', '#1ED760', '#1AA34A', '#168B3E', '#117A32'],
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
      backgroundColor: 'rgba(0, 0, 0, 0.9)',
      border: '1px solid rgba(255, 255, 255, 0.2)',
      borderRadius: '8px',
      color: '#fff',
    },
    cursor: {
      stroke: 'rgba(255, 255, 255, 0.2)',
      strokeWidth: 1,
    },
  },
  // Shared configuration for time-series X-axis (for consistent date formatting)
  timeSeriesXAxis: {
    stroke: '#fff',
    angle: -45,
    textAnchor: 'end' as const,
    height: 80,
    tick: { fontSize: 12 },
  },
} as const;

/**
 * Standard height for time-series charts
 */
export const TIME_SERIES_CHART_HEIGHT = 300;

/**
 * Format date for chart display
 */
export const formatChartDate = (date: string | Date): string => {
  const d = new Date(date);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

/**
 * Format date for detailed view (with year)
 */
export const formatDetailedDate = (date: string | Date): string => {
  const d = new Date(date);
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${months[d.getMonth()]} ${d.getDate()}`;
};
