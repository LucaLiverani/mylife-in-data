/**
 * Travel Data API Route (Cloudflare Workers Function)
 * Provides travel locations and statistics from ClickHouse gold tables
 */

import { queryClickHouse } from '../../_shared/clickhouse';
import type { Env } from '../../_shared/types';

// Define interfaces for the data structures
interface TravelKPIs {
  total_distance: string;
  unique_countries: number;
  unique_cities: number;
  longest_trip: string; // This will be a formatted string
}

interface Location {
  name: string;
  lat: number;
  lng: number;
  duration: string;
}

interface HourlyActivity {
  hour: string;
  activities: number;
}

interface TopDestination {
  rank: number;
  city: string;
  visits: number;
  days: number;
}

/**
 * GET /api/travel/data
 */
export async function onRequest(context: { env: Env }): Promise<Response> {
  const { env } = context;

  try {
    // Query gold tables created by dbt
    const kpisQuery = `
      SELECT
        (SELECT formatReadableQuantity(sum(total_distance_traveled_km)) FROM gold.gold_maps_geographic_range) AS total_distance,
        0 AS unique_countries, -- Country data not available
        (SELECT count(DISTINCT location_name) FROM silver.silver_google_maps_activities WHERE location_name IS NOT NULL AND location_name != '') AS unique_cities,
        '0 days' AS longest_trip -- Placeholder for longest_trip
    `;

    const locationsQuery = `
      SELECT
        location_name AS name,
        latitude AS lat,
        longitude AS lng,
        formatReadableTimeDelta(minutes_until_next_activity * 60) AS duration
      FROM gold.gold_maps_location_timeline
      WHERE latitude IS NOT NULL AND longitude IS NOT NULL
      ORDER BY activity_time DESC
      LIMIT 500
    `;

    const hourlyActivityQuery = `
      SELECT
        format('%02d:00', activity_hour) AS hour,
        sum(total_activities) AS activities
      FROM gold.gold_maps_activity_patterns
      GROUP BY activity_hour
      ORDER BY activity_hour
    `;

    const topDestinationsQuery = `
      SELECT
        visit_rank AS rank,
        location_name AS city,
        total_visits AS visits,
        unique_visit_days AS days
      FROM gold.gold_maps_most_visited_places
      ORDER BY visit_rank
      LIMIT 10
    `;

    // Execute all queries in parallel
    const [kpisResult, locations, hourlyActivity, topDestinations] = await Promise.all([
      queryClickHouse<TravelKPIs>(env, kpisQuery),
      queryClickHouse<Location>(env, locationsQuery),
      queryClickHouse<HourlyActivity>(env, hourlyActivityQuery),
      queryClickHouse<TopDestination>(env, topDestinationsQuery),
    ]);

    const kpis = kpisResult[0] || {
      total_distance: '0 km',
      unique_countries: 0,
      unique_cities: 0,
      longest_trip: '0 days',
    };

    // Format response
    const response = {
      stats: {
        totalDistance: kpis.total_distance,
        countries: kpis.unique_countries.toString(),
        cities: kpis.unique_cities.toString(),
        longestTrip: kpis.longest_trip,
      },
      locations: locations.filter(l => l.lat && l.lng),
      charts: {
        hourlyActivity,
        topDestinations,
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
        totalDistance: '0 km',
        countries: '0',
        cities: '0',
        longestTrip: '0 days',
      },
      locations: [],
      charts: {
        hourlyActivity: [],
        topDestinations: [],
      },
    }, { status: 500 });
  }
}
