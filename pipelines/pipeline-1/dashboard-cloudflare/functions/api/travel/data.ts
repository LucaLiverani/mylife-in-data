/**
 * Travel Data API Route (Cloudflare Workers Function)
 * Provides travel locations and statistics
 *
 * Ported from: dashboard-nextjs/app/api/travel/data/route.ts
 */

import type { Env } from '../../_shared/types';

/**
 * GET /api/travel/data
 */
export async function onRequest(context: { env: Env }): Promise<Response> {
  try {
    // Try to get real data from ClickHouse
    // For now, return empty data since we don't have travel data in ClickHouse yet

    return Response.json({
      locations: [],
      stats: {
        totalDistance: '0 km',
        countries: '0',
        cities: '0',
        longestTrip: '0 days',
      },
    }, {
      headers: {
        'Cache-Control': 'public, max-age=60',
      },
    });
  } catch (error) {
    console.error('Error fetching travel data:', error);

    // Return empty data as fallback
    return Response.json({
      locations: [],
      stats: {
        totalDistance: '0 km',
        countries: '0',
        cities: '0',
        longestTrip: '0 days',
      },
    });
  }
}
