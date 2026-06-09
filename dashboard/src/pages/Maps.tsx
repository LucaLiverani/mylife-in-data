import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, AlertTriangle, Home, Lock, Unlock } from 'lucide-react';
import { FadeIn } from '@/components/animations/FadeIn';
import { KPIMetric } from '@/components/KPIMetric';
import { KpiSince } from '@/components/KpiSince';
import { TravelMap } from '@/components/maps/TravelMap';
import { MapsCharts } from '@/components/charts/MapsCharts';
import { TripTimeline, type Trip, type TripStatus } from '@/components/maps/TripTimeline';
import { Surface } from '@/components/Surface';
import { travelAPI } from '@/lib/api';

const OWNER_TOKEN_KEY = 'mlid_trip_label_token';

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
    homeLocality?: string;
    homeCountry?: string;
  };
  locations: Array<{ name: string; lat: number; lng: number; duration: string }>;
  trips?: Trip[];
  charts: {
    hourlyActivity: Array<{ hour: string; activities: number }>;
    lastActivities: Array<{ time: string; location: string; type: string }>;
    topDestinations: Array<{ destination: string; count: number; type: string; trend?: number[] }>;
    dailyActivity: Array<{ date: string; directions: number; searches: number; explorations: number; other: number }>;
  };
}

export default function MapsPage() {
  const [travelData, setTravelData] = useState<TravelData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Owner mode — a token (stored client-side) unlocks confirm/reject/edit.
  // Absent → the page is read-only for the public.
  const [ownerToken, setOwnerToken] = useState<string>(() => {
    try { return localStorage.getItem(OWNER_TOKEN_KEY) || ''; } catch { return ''; }
  });
  const [showTokenInput, setShowTokenInput] = useState(false);
  const [tokenDraft, setTokenDraft] = useState('');
  const [statusByKey, setStatusByKey] = useState<Record<string, TripStatus>>({});
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [labelError, setLabelError] = useState<string | null>(null);
  const ownerMode = ownerToken.length > 0;

  const enableOwner = () => {
    const t = tokenDraft.trim();
    if (!t) return;
    try { localStorage.setItem(OWNER_TOKEN_KEY, t); } catch { /* ignore */ }
    setOwnerToken(t);
    setShowTokenInput(false);
    setTokenDraft('');
  };
  const disableOwner = () => {
    try { localStorage.removeItem(OWNER_TOKEN_KEY); } catch { /* ignore */ }
    setOwnerToken('');
  };

  const handleLabel = async (
    trip: Trip,
    label: TripStatus,
    edited?: { title: string; destination: string; type: string },
  ) => {
    if (!trip.tripKey || !ownerToken) return;
    setBusyKey(trip.tripKey);
    setLabelError(null);
    try {
      await travelAPI.postTripLabel(ownerToken, {
        trip_key: trip.tripKey,
        label,
        edited_title: edited?.title,
        edited_destination: edited?.destination,
        edited_trip_type: edited?.type,
      });
      setStatusByKey(prev => ({ ...prev, [trip.tripKey as string]: label }));
      if (label === 'edit' && edited) {
        setTravelData(prev => prev ? {
          ...prev,
          trips: prev.trips?.map(x =>
            x.tripKey === trip.tripKey
              ? { ...x, title: edited.title, destination: edited.destination, type: edited.type }
              : x),
        } : prev);
      }
    } catch (e) {
      setLabelError(e instanceof Error ? e.message : 'Could not save label');
      if (e instanceof Error && e.message === 'forbidden') disableOwner();
    } finally {
      setBusyKey(null);
    }
  };

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

  // Trips — inferred, LLM-named; owner can confirm/reject/edit. Rendered lower
  // on the page (after "Activity by hour") via MapsCharts' tripsSlot, but built
  // here so the owner-mode state/handlers stay co-located with the page.
  const tripsSection = travelData?.trips && travelData.trips.length > 0 ? (
    <section className="mb-12">
      <FadeIn delay={0.18}>
        <Surface>
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3 gap-y-2">
            <h2 className="font-mono text-xs uppercase tracking-wider text-signal-white/60">
              Trips · {travelData.trips.length}
            </h2>
            <div className="flex items-center gap-2">
              {labelError && <span className="font-mono text-[10px] text-trace-down">{labelError}</span>}
              {ownerMode ? (
                <button
                  type="button"
                  onClick={disableOwner}
                  className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-channel-violet transition-colors hover:text-channel-violet/80"
                >
                  <Unlock className="size-3.5" /> Owner
                </button>
              ) : showTokenInput ? (
                <div className="flex items-center gap-1.5">
                  <input
                    type="password"
                    value={tokenDraft}
                    autoFocus
                    onChange={(e) => setTokenDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') enableOwner();
                      if (e.key === 'Escape') setShowTokenInput(false);
                    }}
                    placeholder="owner token"
                    className="w-32 rounded-sm border border-signal-white/15 bg-rack-black/80 px-2 py-0.5 font-mono text-[10px] text-signal-white focus-visible:outline focus-visible:outline-1 focus-visible:outline-channel-violet"
                  />
                  <button type="button" onClick={enableOwner} className="font-mono text-[10px] uppercase tracking-wider text-channel-violet">
                    Unlock
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setShowTokenInput(true)}
                  aria-label="Enter owner mode"
                  className="-m-2.5 p-2.5 text-signal-white/25 transition-colors hover:text-signal-white/60"
                >
                  <Lock className="size-3.5" />
                </button>
              )}
            </div>
          </div>
          <TripTimeline
            trips={travelData.trips}
            ownerMode={ownerMode}
            statusByKey={statusByKey}
            busyKey={busyKey}
            onLabel={handleLabel}
          />
        </Surface>
      </FadeIn>
    </section>
  ) : null;

  return (
    <div className="min-h-screen bg-gradient-to-br from-rack-black to-rack-charcoal text-signal-white">

      <div className="relative z-10 max-w-7xl mx-auto px-4 py-12 sm:px-6 sm:py-20">
        {/* Header */}
        <FadeIn>
          <Link to="/" className="inline-flex items-center gap-2 text-signal-white/60 hover:text-signal-white transition-colors mb-8">
            <ArrowLeft className="w-4 h-4" />
            Back to Dashboard
          </Link>
          <div className="mb-12">
            <h1 className="text-4xl sm:text-5xl lg:text-7xl font-bold mb-4">
              <span className="text-channel-violet">Travel</span> Analytics
            </h1>
            <p className="text-xl text-signal-white/60 italic">
              An overview of the passport stamps and existential crises I've collected.
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
                <h2 className="mb-4 font-mono text-xs uppercase tracking-wider text-signal-white/60">Overview<KpiSince /></h2>
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
                  <KPIMetric label="Kilometers"    value={travelData.stats.kilometersTraveled ?? '-'} kind="count" channel="maps" />
                  <KPIMetric label="Days away"     value={travelData.stats.daysAwayFromHome ?? '-'}   kind="count" channel="maps" />
                  <KPIMetric label="New places"    value={travelData.stats.newPlacesThisYear ?? '-'}  kind="count" channel="maps" />
                  <KPIMetric label="Longest trip"  value={travelData.stats.longestTripDays ?? '-'}    kind="count" channel="maps" />
                </div>
              </FadeIn>
            </section>

            {/* Home base */}
            {travelData.stats.homeLocality && (
              <FadeIn delay={0.16}>
                <div className="mb-12 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border border-signal-white/10 bg-rack-black/60 px-5 py-3">
                  <Home className="size-4 shrink-0 text-channel-violet" aria-hidden="true" />
                  <span className="font-mono text-xs uppercase tracking-wider text-signal-white/60">Home base</span>
                  <span className="text-sm font-medium text-signal-white">
                    {travelData.stats.homeLocality}{travelData.stats.homeCountry ? `, ${travelData.stats.homeCountry}` : ''}
                  </span>
                  <span className="font-mono text-[10px] uppercase tracking-wider text-signal-white/40">· trips measured from here</span>
                </div>
              </FadeIn>
            )}

            {/* Map Section */}
            <section className="mb-12">
              <FadeIn delay={0.2}>
                <Surface>
                  <h2 className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">Travel map</h2>
                  <div className="h-[320px] overflow-hidden rounded-md sm:h-[500px]">
                    <TravelMap locations={travelData.locations} />
                  </div>
                </Surface>
              </FadeIn>
            </section>

            {/* Charts Section — Trips inject after "Activity by hour" */}
            <FadeIn delay={0.3}>
              <MapsCharts data={travelData.charts} tripsSlot={tripsSection} />
            </FadeIn>
          </>
        )}
      </div>
    </div>
  );
}
