# My Life in Data - Cloudflare Dashboard

A real-time personal analytics dashboard built with React and deployed on Cloudflare Pages, visualizing data from Spotify, YouTube, Google Search, and travel activities.

## Architecture

### Frontend
- **Framework**: React 19 + TypeScript
- **Build Tool**: Vite 6
- **Styling**: TailwindCSS
- **Charts**: Recharts
- **Maps**: Leaflet
- **Animations**: Framer Motion
- **Routing**: React Router v7

### Backend
- **API Layer**: Cloudflare Workers Functions
- **Database**: ClickHouse (via HTTP API)
- **Fallback System**: Static JSON files for resilience
- **Streaming**: Polling-based (every 5-10 seconds)

### Deployment
- **Hosting**: Cloudflare Pages
- **CDN**: 300+ global edge locations
- **Cold Starts**: <10ms (V8 isolates)
- **Cost**: Free tier

## Project Structure

```
dashboard-cloudflare/
├── public/
│   └── fallback-data/      # Static fallback data
│       ├── overview-stats.json
│       ├── spotify-current.json
│       └── ...
├── src/
│   ├── components/
│   │   ├── animations/     # FadeIn, ParticleBackground, Typewriter
│   │   ├── charts/         # Reusable chart components
│   │   │   ├── chartConfig.ts
│   │   │   ├── SpotifyCharts.tsx
│   │   │   ├── YouTubeCharts.tsx
│   │   │   ├── GoogleCharts.tsx
│   │   │   └── MapsCharts.tsx
│   │   ├── maps/           # TravelMap (Leaflet integration)
│   │   ├── spotify/        # SpotifyLiveStream
│   │   └── ui/             # Button, Card, etc.
│   ├── lib/                # API client and utilities
│   ├── pages/              # Home, Spotify, YouTube, Google, Maps
│   ├── App.tsx
│   └── main.tsx
├── functions/
│   ├── _shared/
│   │   ├── clickhouse.ts   # ClickHouse HTTP client
│   │   ├── fallback.ts     # Fallback data loader
│   │   └── types.ts
│   └── api/
│       ├── overview/stats.ts
│       ├── spotify/
│       │   ├── current.ts  # Polling endpoint (with fallback)
│       │   ├── data.ts
│       │   ├── recent.ts
│       │   └── summary.ts
│       └── travel/data.ts
├── scripts/
│   ├── deploy-to-pages.sh  # Deploy to Cloudflare Pages
│   └── export-fallback-data.sh
├── wrangler.toml
├── vite.config.ts
└── package.json
```

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn
- Cloudflare account (for deployment)
- ClickHouse database (optional for development - fallback data available)

### Local Development

1. **Clone and install dependencies**

```bash
cd dashboard-cloudflare
npm install
```

2. **Configure environment variables**

Create a `.dev.vars` file (git-ignored):

```bash
CLICKHOUSE_HOST=http://your-clickhouse-host:8123
CLICKHOUSE_USER=admin
CLICKHOUSE_PASSWORD=your_password
CLICKHOUSE_DATABASE=analytics
```

If you don't have ClickHouse running, the app will use fallback data automatically.

3. **Start development server**

Run the Vite dev server:

```bash
npm run dev
```

Visit http://localhost:3000

4. **Test with Workers Functions (optional)**

To test the full stack including API functions:

**Terminal 1** - Build frontend:
```bash
npm run build
```

**Terminal 2** - Run Pages dev server:
```bash
npm run pages:dev
```

Visit http://localhost:8788

## Deployment to Cloudflare

### Option 1: Using the deployment script (easiest)

```bash
./scripts/deploy-to-pages.sh
```

This will build your project and deploy it to Cloudflare Pages. On first deployment, you'll need to set environment variables in the Cloudflare Dashboard (the script will show you instructions).

### Option 2: Manual deployment

```bash
# Build and deploy in one command
npm run pages:deploy

# Or step by step
npm run build
npx wrangler pages deploy dist
```

### Option 3: GitHub integration (recommended for production)

1. Push your code to GitHub
2. Go to [Cloudflare Dashboard](https://dash.cloudflare.com)
3. Navigate to **Pages** > **Create a project**
4. Connect your GitHub repository
5. Configure build settings:
   - **Build command**: `npm run build`
   - **Build output directory**: `dist`
   - **Root directory**: `dashboard-cloudflare`
6. Add environment variables:
   - `CLICKHOUSE_HOST`
   - `CLICKHOUSE_USER`
   - `CLICKHOUSE_PASSWORD`
   - `CLICKHOUSE_DATABASE`

Cloudflare will automatically deploy on every push to your main branch.

## Features

### Pages

- **Home**: Overview dashboard with KPIs and recent activity
- **Spotify**: Live streaming track, top artists, genre distribution, listening trends
- **YouTube**: Watch time analytics, top channels, category distribution
- **Google**: Search history analytics, search volume trends, top searches
- **Maps**: Interactive travel map with Leaflet, trip visualization by continent

### Key Features

- Real-time Spotify track display with polling
- Consistent chart styling across all pages
- Fallback data system for offline resilience
- Interactive travel map with custom markers
- Responsive design with Tailwind CSS
- Smooth animations with Framer Motion
- Reusable component library

### Fallback System

When ClickHouse is unavailable, the app automatically serves static data from `public/fallback-data/`:

- `/api/overview/stats` → `overview-stats.json`
- `/api/spotify/current` → `spotify-current.json`

Responses include `_meta.cached: true` to indicate fallback mode.

## API Endpoints

| Endpoint | Description | Fallback |
|----------|-------------|----------|
| `/api/overview/stats` | Dashboard overview KPIs | ✅ Yes |
| `/api/spotify/current` | Current playing track (polling) | ✅ Yes |
| `/api/spotify/data` | Full Spotify analytics data | ❌ No |
| `/api/spotify/recent` | Recent tracks list | ❌ No |
| `/api/spotify/summary` | Spotify summary statistics | ❌ No |
| `/api/travel/data` | Travel locations and stats | ❌ No |

## Scripts

### `deploy-to-pages.sh`

Builds and deploys the application to Cloudflare Pages:

```bash
./scripts/deploy-to-pages.sh
```

### `export-fallback-data.sh`

Exports fresh data from ClickHouse to fallback JSON files:

```bash
./scripts/export-fallback-data.sh
```

Requires ClickHouse credentials to be configured.

## Configuration

### `wrangler.toml`

Cloudflare Pages configuration:

```toml
name = "mylife-dashboard"
compatibility_date = "2024-11-16"
pages_build_output_dir = "dist"
```

### `vite.config.ts`

Vite build configuration with React plugin and path aliases.

### `tailwind.config.js`

TailwindCSS configuration with custom theme extensions.

## Troubleshooting

### ClickHouse connection errors

- Verify `CLICKHOUSE_HOST` is accessible (may require tunnel/proxy for local ClickHouse)
- Check ClickHouse HTTP interface is enabled (port 8123)
- Ensure credentials are correct in `.dev.vars` or Cloudflare secrets

### Build errors

```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json dist
npm install
npm run build
```

### CORS issues

- Workers Functions handle CORS automatically for same-origin requests
- For cross-origin, add CORS headers in function responses

### Fallback data not loading

- Ensure JSON files are in `public/fallback-data/`
- Check file names match the loader in `functions/_shared/fallback.ts`
- Verify build includes public directory (`dist/fallback-data/`)

## Performance

- **Global CDN**: Deployed to 300+ Cloudflare edge locations
- **Cold starts**: <10ms (V8 isolates, not containers)
- **Build time**: ~6 seconds
- **Bundle size**: ~150KB (gzipped)
- **Lighthouse score**: 95+ across all metrics

## Resources

- [Cloudflare Pages Docs](https://developers.cloudflare.com/pages/)
- [Cloudflare Workers Docs](https://developers.cloudflare.com/workers/)
- [Wrangler CLI](https://developers.cloudflare.com/workers/wrangler/)
- [ClickHouse HTTP Interface](https://clickhouse.com/docs/en/interfaces/http)
- [Recharts Documentation](https://recharts.org/)
- [Leaflet Documentation](https://leafletjs.com/)

## License

Private project - All rights reserved
