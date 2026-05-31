/**
 * Travel Data API Route (Cloudflare Workers Function)
 * Travel locations and statistics from ClickHouse gold tables.
 */

import { queryClickHouse } from '../../_shared/clickhouse';
import { queryWithFallback, addCacheHeaders } from '../../_shared/fallback';
import type { Env } from '../../_shared/types';

interface TravelKPIs {
  total_activities: number;
  total_directions: number;
  total_searches: number;
  total_explorations: number;
  total_likely_visits: number;
  days_with_activity: number;
  unique_destinations: number;
  cities_visited: number;
  countries_visited: number;
  first_activity: string;
  last_activity: string;
  days_tracked: number;
  avg_activities_per_day: number;
  directions_pct: number;
  search_pct: number;
  explore_pct: number;
  kilometers_traveled: number;
  days_away_from_home: number;
  longest_trip_days: number;
  new_places_this_year: number;
  home_locality: string;
  home_country: string;
}

interface Location {
  name: string;
  lat: number;
  lng: number;
  duration: string;
  dwell_time_category: string;
  distance_to_next_km: number;
}

interface HourlyActivity {
  hour: string;
  activities: number;
}

interface LastActivity {
  time: string;
  location: string;
  type: string;
  timeOfDay: string;
}

interface TopDestination {
  destination: string;
  count: number;
  type: string;
}

interface Trip {
  start: string;
  end: string;
  destination: string;
  days: number;
  km: number;
  title: string;
  trip_type: string;
  country: string;
  summary: string;
  confidence: number;
  temp_mean: number;
  precip_mm: number;
  weather: string;
  trip_key: string;
  localities: number;
  countries: number;
  max_km: number;
}

export async function onRequest(context: { env: Env; request: Request }): Promise<Response> {
  const { env, request } = context;

  const { data, isFromCache, error } = await queryWithFallback<any>(
    async () => {
      const [kpisResult, locations, hourlyActivity, lastActivities, dailyActivity, topDestinations, tripsResult] =
        await Promise.all([
          queryClickHouse<TravelKPIs>(env, `SELECT * FROM gold.gold_maps_kpis_dashboard LIMIT 1`),
          queryClickHouse<Location>(env, `SELECT * FROM gold.gold_maps_locations_dashboard LIMIT 500`),
          queryClickHouse<HourlyActivity>(env, `SELECT * FROM gold.gold_maps_hourly_activity_dashboard`),
          queryClickHouse<LastActivity>(env, `SELECT * FROM gold.gold_maps_recent_activities LIMIT 10`),
          queryClickHouse<{ date: string; directions: number; searches: number; explorations: number; other: number }>(
            env,
            `SELECT * FROM gold.gold_maps_daily_activity_dashboard`
          ),
          queryClickHouse<TopDestination>(env, `SELECT * FROM gold.gold_maps_destinations_dashboard LIMIT 10`),
          queryClickHouse<Trip>(env, `SELECT * FROM gold.gold_maps_trips LIMIT 100`),
        ]);

      const kpis = kpisResult[0] || {
        total_activities: 0,
        total_directions: 0,
        total_searches: 0,
        total_explorations: 0,
        total_likely_visits: 0,
        days_with_activity: 0,
        unique_destinations: 0,
        cities_visited: 0,
        countries_visited: 0,
        first_activity: '',
        last_activity: '',
        days_tracked: 0,
        avg_activities_per_day: 0,
        directions_pct: 0,
        search_pct: 0,
        explore_pct: 0,
        kilometers_traveled: 0,
        days_away_from_home: 0,
        longest_trip_days: 0,
        new_places_this_year: 0,
        home_locality: '',
        home_country: '',
      };

      // Null-safe coercion: ClickHouse can return NULL for ratio columns
      // (divide-by-zero) — calling .toFixed()/.toLocaleString() on null throws.
      const num = (v: unknown): number => Number(v) || 0;
      return {
        stats: {
          totalActivities: num(kpis.total_activities).toLocaleString(),
          totalDirections: num(kpis.total_directions).toLocaleString(),
          totalSearches: num(kpis.total_searches).toLocaleString(),
          totalExplorations: num(kpis.total_explorations).toLocaleString(),
          likelyVisits: num(kpis.total_likely_visits).toLocaleString(),
          uniqueDestinations: num(kpis.unique_destinations).toLocaleString(),
          citiesVisited: num(kpis.cities_visited).toLocaleString(),
          countriesVisited: num(kpis.countries_visited).toLocaleString(),
          daysWithActivity: num(kpis.days_with_activity).toString(),
          daysTracked: num(kpis.days_tracked).toString(),
          avgActivitiesPerDay: num(kpis.avg_activities_per_day).toFixed(1),
          directionsPct: num(kpis.directions_pct).toFixed(1),
          searchPct: num(kpis.search_pct).toFixed(1),
          explorePct: num(kpis.explore_pct).toFixed(1),
          kilometersTraveled: num(kpis.kilometers_traveled).toLocaleString(),
          daysAwayFromHome: num(kpis.days_away_from_home).toString(),
          longestTripDays: num(kpis.longest_trip_days).toString(),
          newPlacesThisYear: num(kpis.new_places_this_year).toString(),
          homeLocality: kpis.home_locality || '',
          homeCountry: kpis.home_country || '',
          firstActivity: kpis.first_activity,
          lastActivity: kpis.last_activity,
        },
        locations: locations
          .filter(l => l.lat && l.lng)
          .map(l => ({
            name: l.name,
            lat: Number(l.lat),
            lng: Number(l.lng),
            duration: l.duration || 'Unknown',
          })),
        trips: tripsResult.map(t => ({
          start: t.start,
          end: t.end,
          destination: t.destination,
          days: Number(t.days),
          km: Number(t.km),
          title: t.title,
          type: t.trip_type,
          country: t.country,
          summary: t.summary,
          confidence: Number(t.confidence),
          weather: t.weather || '',
          tempMean: Number(t.temp_mean),
          precipMm: Number(t.precip_mm),
          tripKey: t.trip_key,
          localities: Number(t.localities),
          countries: Number(t.countries),
          maxKm: Number(t.max_km),
        })),
        charts: {
          hourlyActivity: hourlyActivity.map(h => ({ hour: h.hour, activities: Number(h.activities) })),
          lastActivities: lastActivities.map(a => ({
            time: a.time,
            location: a.location,
            type: a.type,
            timeOfDay: a.timeOfDay,
          })),
          topDestinations: topDestinations.map(d => ({
            destination: d.destination,
            count: Number(d.count),
            type: d.type,
          })),
          dailyActivity: dailyActivity.map(d => ({
            date: d.date,
            directions: Number(d.directions),
            searches: Number(d.searches),
            explorations: Number(d.explorations),
            other: Number(d.other),
          })),
        },
      };
    },
    'travel/data',
    request,
    {
      stats: {
        totalActivities: '0',
        totalDirections: '0',
        totalSearches: '0',
        totalExplorations: '0',
        likelyVisits: '0',
        uniqueDestinations: '0',
        daysWithActivity: '0',
        daysTracked: '0',
        avgActivitiesPerDay: '0',
        directionsPct: '0',
        searchPct: '0',
        explorePct: '0',
        kilometersTraveled: '0',
        daysAwayFromHome: '0',
        longestTripDays: '0',
        newPlacesThisYear: '0',
        homeLocality: '',
        homeCountry: '',
        firstActivity: '',
        lastActivity: '',
      },
      locations: [],
      trips: [],
      charts: {
        hourlyActivity: [],
        lastActivities: [],
        topDestinations: [],
        dailyActivity: [],
      },
    }
  );

  const { body, headers } = addCacheHeaders(data, isFromCache, error, 'public, max-age=3600');
  return Response.json(body, { headers });
}
