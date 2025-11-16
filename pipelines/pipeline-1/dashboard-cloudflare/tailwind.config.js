/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        spotify: '#1DB954',
        youtube: '#FF0000',
        google: '#4285F4',
        maps: '#A855F7',
      },
    },
  },
  plugins: [],
}
