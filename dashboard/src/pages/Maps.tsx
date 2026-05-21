import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, AlertTriangle } from 'lucide-react';
import { FadeIn } from '@/components/animations/FadeIn';
import { KPIMetric } from '@/components/KPIMetric';
import { TravelMap } from '@/components/maps/TravelMap';
import { MapsCharts } from '@/components/charts/MapsCharts';
import { Surface } from '@/components/Surface';
import { travelAPI } from '@/lib/api';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
function formatTripRange(start: string, end: string): string {
  const s = new Date(start);
  const e = new Date(end);
  const sm = MONTHS[s.getMonth()];
  const em = MONTHS[e.getMonth()];
  if (sm === em) return `${sm} ${s.getDate()}–${e.getDate()}`;
  return `${sm} ${s.getDate()} – ${em} ${e.getDate()}`;
}

interface TravelData {
  stats: {
    citiesVisited: number | string;
    countriesVisited: number | string;
    totalActivities: number | string;
    totalDirections: number | string;
    totalSearches: number | string;
    totalExplorations: number | string;
    likelyVisits: number | string;
    uniqueDestinations: number | string;
    daysWithActivity: number | string;
    daysTracked: number | string;
    avgActivitiesPerDay: number | string;
    directionsPct: number | string;
    searchPct: number | string;
    explorePct: number | string;
    firstActivity: string;
    lastActivity: string;
    kilometersTraveled?: number | string;
    daysAwayFromHome?: number | string;
    newPlacesThisYear?: number | string;
    longestTripDays?: number | string;
  };
  locations: Array<{ name: string; lat: number; lng: number; duration: string }>;
  trips?: Array<{ start: string; end: string; destination: string; days: number; km: number }>;
  charts: {
    hourlyActivity: Array<{ hour: string; activities: number }>;
    lastActivities: Array<{ time: string; location: string; type: string; timeOfDay: string }>;
    topDestinations: Array<{ destination: string; count: number; type: string; trend?: number[] }>;
    dailyActivity: Array<{ date: string; directions: number; searches: number; explorations: number; other: number }>;
  };
}

export default function MapsPage() {
  const [travelData, setTravelData] = useState<TravelData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const result = await travelAPI.getData() as TravelData;
        // Check if the data is essentially empty
        if (parseInt(String(result.stats.totalActivities)) === 0) {
          setError('No Google Maps activity data available.');
        } else {
          setTravelData(result);
          setError(null);
        }
      } catch (err) {
        console.error('Failed to fetch travel data:', err);
        setError('Failed to load travel data from the API.');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-rack-black to-rack-charcoal text-signal-white">
        <p className="font-mono text-sm uppercase tracking-wider text-signal-white/60">Plotting the route…</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-rack-black to-rack-charcoal text-signal-white">

      <div className="relative z-10 max-w-7xl mx-auto px-6 py-20">
        {/* Header */}
        <FadeIn>
          <Link to="/" className="inline-flex items-center gap-2 text-signal-white/60 hover:text-signal-white transition-colors mb-8">
            <ArrowLeft className="w-4 h-4" />
            Back to Dashboard
          </Link>
          <div className="mb-12">
            <h1 className="text-5xl lg:text-7xl font-bold mb-4">
              <span className="text-channel-violet">Travel</span> Analytics
            </h1>
            <p className="text-xl text-signal-white/60 italic">
              Collecting passport stamps and existential crises since 2024.
            </p>
          </div>
        </FadeIn>

        {/* Error/No data — flat trace-down panel, on-system */}
        {error && !travelData && (
          <FadeIn delay={0.1}>
            <div className="rounded-md border border-trace-down/30 bg-trace-down/10 p-6" role="alert">
              <div className="flex items-start gap-3">
                <AlertTriangle className="size-5 shrink-0 text-trace-down" aria-hidden="true" />
                <div>
                  <p className="font-mono text-xs uppercase tracking-wider text-trace-down">No travel signal</p>
                  <p className="mt-2 text-sm text-signal-white/80">{error}</p>
                  <p className="mt-2 max-w-prose text-xs text-signal-white/50">
                    Google Takeout location history hasn't reached ClickHouse yet — or the export didn't include place visits.
                  </p>
                </div>
              </div>
            </div>
          </FadeIn>
        )}

        {/* Data Display */}
        {travelData && (
          <>
            {/* Primary KPIs */}
            <section className="mb-8">
              <FadeIn delay={0.1}>
                <h2 className="mb-4 font-mono text-xs uppercase tracking-wider text-signal-white/60">Overview</h2>
                <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                  <KPIMetric label="Cities"    value={travelData.stats.citiesVisited}    kind="count" channel="maps" />
                  <KPIMetric label="Countries" value={travelData.stats.countriesVisited} kind="count" channel="maps" />
                  <KPIMetric label="Activities" value={travelData.stats.totalActivities} kind="count" channel="maps" />
                  <KPIMetric label="Active days" value={travelData.stats.daysWithActivity} kind="count" channel="maps" />
                </div>
              </FadeIn>
            </section>

            {/* Producer-console signature row — actual movement, not just activity */}
            <section className="mb-12">
              <FadeIn delay={0.15}>
                <h2 className="mb-4 font-mono text-xs uppercase tracking-wider text-signal-white/60">Movement</h2>
                <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                  <KPIMetric label="Kilometers"    value={travelData.stats.kilometersTraveled ?? '—'} kind="count" channel="maps" />
                  <KPIMetric label="Days away"     value={travelData.stats.daysAwayFromHome ?? '—'}   kind="count" channel="maps" />
                  <KPIMetric label="New places"    value={travelData.stats.newPlacesThisYear ?? '—'}  kind="count" channel="maps" />
                  <KPIMetric label="Longest trip"  value={travelData.stats.longestTripDays ?? '—'}    kind="count" channel="maps" />
                </div>
              </FadeIn>
            </section>

            {/* Trip segments */}
            {travelData.trips && travelData.trips.length > 0 && (
              <section className="mb-12">
                <FadeIn delay={0.18}>
                  <Surface>
                    <h2 className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
                      Trip segments
                    </h2>
                    <ul className="-mx-6 -mb-6">
                      {travelData.trips.map((t, i) => (
                        <li
                          key={i}
                          className="flex items-center gap-4 border-t border-signal-white/5 px-6 py-3 transition-colors duration-150 ease-snap hover:bg-signal-white/[0.03]"
                        >
                          <span className="block size-2 rounded-sm bg-channel-violet" aria-hidden="true" />
                          <div className="min-w-0 flex-1">
                            <div className="truncate text-sm font-medium text-signal-white">{t.destination}</div>
                            <div className="font-mono text-[10px] uppercase tracking-wider text-signal-white/50">
                              {formatTripRange(t.start, t.end)}
                            </div>
                          </div>
                          <div className="text-right font-mono text-xs">
                            <div className="text-channel-violet tabular-nums">{t.days}d · {t.km.toLocaleString()} km</div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </Surface>
                </FadeIn>
              </section>
            )}

            {/* Map Section */}
            <section className="mb-12">
              <FadeIn delay={0.2}>
                <Surface>
                  <h2 className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">Travel map</h2>
                  <div className="h-[500px] overflow-hidden rounded-md">
                    <TravelMap locations={travelData.locations} />
                  </div>
                </Surface>
              </FadeIn>
            </section>

            {/* Charts Section */}
            <FadeIn delay={0.3}>
              <MapsCharts data={travelData.charts} />
            </FadeIn>
          </>
        )}
      </div>
    </div>
  );
}
