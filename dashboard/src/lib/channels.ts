// Single source of truth for channel colors at runtime.
// Tailwind classes use channel-{green,red,violet,blue}; this map covers the
// places where we still need a literal hex string (Recharts, Leaflet, inline
// SVG fill on icons). Don't paste raw hex anywhere else.
export type Channel = 'spotify' | 'youtube' | 'maps' | 'calendar';

export const CHANNEL_HEX: Record<Channel, string> = {
  spotify:  '#1DB954',
  youtube:  '#FF0000',
  maps:     '#A855F7',
  calendar: '#4285F4',
};

/**
 * 5-step tonal ramps per channel, dark → light around the channel hex.
 * Used for multi-segment charts (pie/donut) so the source page stays in its
 * own lane per DESIGN.md's Channel-Lane Rule, while remaining segments stay
 * legible.
 */
export const CHANNEL_RAMP: Record<Channel, readonly string[]> = {
  spotify:  ['#138C40', '#1AA34A', '#1DB954', '#3FC972', '#73D998'],
  youtube:  ['#B00000', '#D80000', '#FF0000', '#FF4D4D', '#FF8585'],
  maps:     ['#7339BD', '#8C42D8', '#A855F7', '#BC7DFA', '#D2A6FC'],
  calendar: ['#2167CF', '#3276E8', '#4285F4', '#6FA3F7', '#9DC2F9'],
};

export const CHANNEL_CLASS = {
  text: {
    spotify:  'text-channel-green',
    youtube:  'text-channel-red',
    maps:     'text-channel-violet',
    calendar: 'text-channel-blue',
  },
  bg: {
    spotify:  'bg-channel-green',
    youtube:  'bg-channel-red',
    maps:     'bg-channel-violet',
    calendar: 'bg-channel-blue',
  },
  border: {
    spotify:  'border-channel-green',
    youtube:  'border-channel-red',
    maps:     'border-channel-violet',
    calendar: 'border-channel-blue',
  },
  glow: {
    spotify:  'shadow-glow-green',
    youtube:  'shadow-glow-red',
    maps:     'shadow-glow-violet',
    calendar: 'shadow-glow-blue',
  },
  hoverGlow: {
    spotify:  'hover:shadow-glow-green',
    youtube:  'hover:shadow-glow-red',
    maps:     'hover:shadow-glow-violet',
    calendar: 'hover:shadow-glow-blue',
  },
  hoverBorder: {
    spotify:  'hover:border-channel-green/40',
    youtube:  'hover:border-channel-red/40',
    maps:     'hover:border-channel-violet/40',
    calendar: 'hover:border-channel-blue/40',
  },
  focusRing: {
    spotify:  'focus-visible:outline-channel-green',
    youtube:  'focus-visible:outline-channel-red',
    maps:     'focus-visible:outline-channel-violet',
    calendar: 'focus-visible:outline-channel-blue',
  },
  groupHoverText: {
    spotify:  'group-hover:text-channel-green',
    youtube:  'group-hover:text-channel-red',
    maps:     'group-hover:text-channel-violet',
    calendar: 'group-hover:text-channel-blue',
  },
  scrollbar: {
    spotify:  'scrollbar-thin scrollbar-thumb-channel-green/50 scrollbar-track-transparent',
    youtube:  'scrollbar-thin scrollbar-thumb-channel-red/50 scrollbar-track-transparent',
    maps:     'scrollbar-thin scrollbar-thumb-channel-violet/50 scrollbar-track-transparent',
    calendar: 'scrollbar-thin scrollbar-thumb-channel-blue/50 scrollbar-track-transparent',
  },
} as const;
