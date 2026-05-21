/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'channel-green':  '#1DB954', // Spotify lane
        'channel-red':    '#FF0000', // YouTube lane
        'channel-violet': '#A855F7', // Maps lane
        'channel-blue':   '#4285F4', // Calendar lane
        'rack-black':     '#1A1A1A',
        'rack-charcoal':  '#2D2D2D',
        'signal-white':   '#FFFFFF',
        'trace-up':       '#34D399',
        'trace-down':     '#F87171',
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      boxShadow: {
        lift: '0 8px 24px rgba(0, 0, 0, 0.4)',
        'glow-green':  '0 0 32px rgba(29, 185, 84, 0.30)',
        'glow-red':    '0 0 32px rgba(255, 0, 0, 0.30)',
        'glow-violet': '0 0 32px rgba(168, 85, 247, 0.30)',
        'glow-blue':   '0 0 32px rgba(66, 133, 244, 0.30)',
      },
      borderRadius: {
        sm: '4px',
        md: '8px',
        lg: '12px',
      },
      transitionTimingFunction: {
        snap: 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
      fontFeatureSettings: {
        tnum: '"tnum"',
      },
    },
  },
  plugins: [],
}
