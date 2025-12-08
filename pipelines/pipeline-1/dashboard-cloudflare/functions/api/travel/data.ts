/**
 * Travel Data API Route (Cloudflare Workers Function)
 * Provides travel locations and statistics from ClickHouse gold tables
 *
 * Uses dbt gold models:
 * - gold_maps_kpis: Overall statistics and KPIs
 * - gold_maps_location_timeline: Location visits with timeline data
 * - gold_maps_hourly_heatmap: Activity patterns by hour and day
 * - gold_maps_top_destinations: Top destinations by activity type
 * - gold_maps_daily_activity_breakdown: Daily activity breakdown
 * - gold_maps_recent_activities: Recent activity timeline
 */

import { queryClickHouse } from '../../_shared/clickhouse';
import type { Env } from '../../_shared/types';

// Define interfaces for the data structures
interface TravelKPIs {
  total_activities: number;
  total_directions: number;
  total_searches: number;
  total_explorations: number;
  total_likely_visits: number;
  days_with_activity: number;
  unique_destinations: number;
  first_activity: string;
  last_activity: string;
  days_tracked: number;
  avg_activities_per_day: number;
  directions_pct: number;
  search_pct: number;
  explore_pct: number;
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

/**
 * GET /api/travel/data
 */
export async function onRequest(context: { env: Env }): Promise<Response> {
  const { env } = context;

  try {
    // Query 1: Get KPIs from dashboard view
    const kpisQuery = `
      SELECT *
      FROM gold.gold_maps_kpis_dashboard
      LIMIT 1
    `;

    // Query 2: Get recent locations from dashboard view
    const locationsQuery = `
      SELECT *
      FROM gold.gold_maps_locations_dashboard
      LIMIT 500
    `;

    // Query 3: Get hourly activity from dashboard view
    const hourlyActivityQuery = `
      SELECT *
      FROM gold.gold_maps_hourly_activity_dashboard
    `;

    // Query 4: Get last 10 activities from dashboard view
    const lastActivitiesQuery = `
      SELECT *
      FROM gold.gold_maps_recent_activities
      LIMIT 10
    `;

    // Query 5: Get daily activity breakdown from dashboard view (last 30 days)
    const dailyActivityQuery = `
      SELECT *
      FROM gold.gold_maps_daily_activity_dashboard
    `;

    // Query 6: Get top 10 destinations from dashboard view
    const topDestinationsQuery = `
      SELECT *
      FROM gold.gold_maps_destinations_dashboard
      LIMIT 10
    `;

    // Execute all queries in parallel
    const [kpisResult, locations, hourlyActivity, lastActivities, dailyActivity, topDestinations] = await Promise.all([
      queryClickHouse<TravelKPIs>(env, kpisQuery),
      queryClickHouse<Location>(env, locationsQuery),
      queryClickHouse<HourlyActivity>(env, hourlyActivityQuery),
      queryClickHouse<LastActivity>(env, lastActivitiesQuery),
      queryClickHouse<{ date: string; directions: number; searches: number; explorations: number; other: number }>(env, dailyActivityQuery),
      queryClickHouse<TopDestination>(env, topDestinationsQuery),
    ]);

    const kpis = kpisResult[0] || {
      total_activities: 0,
      total_directions: 0,
      total_searches: 0,
      total_explorations: 0,
      total_likely_visits: 0,
      days_with_activity: 0,
      unique_destinations: 0,
      first_activity: '',
      last_activity: '',
      days_tracked: 0,
      avg_activities_per_day: 0,
      directions_pct: 0,
      search_pct: 0,
      explore_pct: 0,
    };

    // Format response to match frontend expectations
    const response = {
      stats: {
        totalActivities: kpis.total_activities.toLocaleString(),
        totalDirections: kpis.total_directions.toLocaleString(),
        totalSearches: kpis.total_searches.toLocaleString(),
        totalExplorations: kpis.total_explorations.toLocaleString(),
        likelyVisits: kpis.total_likely_visits.toLocaleString(),
        uniqueDestinations: kpis.unique_destinations.toLocaleString(),
        daysWithActivity: kpis.days_with_activity.toString(),
        daysTracked: kpis.days_tracked.toString(),
        avgActivitiesPerDay: kpis.avg_activities_per_day.toFixed(1),
        directionsPct: kpis.directions_pct.toFixed(1),
        searchPct: kpis.search_pct.toFixed(1),
        explorePct: kpis.explore_pct.toFixed(1),
        firstActivity: kpis.first_activity,
        lastActivity: kpis.last_activity,
      },
      locations: locations.filter(l => l.lat && l.lng).map(l => ({
        name: l.name,
        lat: Number(l.lat),
        lng: Number(l.lng),
        duration: l.duration || 'Unknown',
      })),
      charts: {
        hourlyActivity: hourlyActivity.map(h => ({
          hour: h.hour,
          activities: Number(h.activities),
        })),
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

    return Response.json(response, {
      headers: {
        'Cache-Control': 'public, max-age=3600', // Cache for 1 hour
      },
    });
  } catch (error) {
    console.error('Error fetching travel data:', error);

    // Return empty data as fallback
    return Response.json({
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
        firstActivity: '',
        lastActivity: '',
      },
      locations: [],
      charts: {
        hourlyActivity: [],
        lastActivities: [],
        topDestinations: [],
        dailyActivity: [],
      },
    }, { status: 500 });
  }
}
