/**
 * Travel Data API Route
 * Provides travel locations and statistics
 */

import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const revalidate = 60;

export async function GET() {
  try {
    // Try to get real data from ClickHouse
    // For now, return empty data since we don't have travel data in ClickHouse yet

    return NextResponse.json({
      locations: [],
      stats: {
        totalDistance: '0 km',
        countries: '0',
        cities: '0',
        longestTrip: '0 days',
      },
    });
  } catch (error) {
    console.error('Error fetching travel data:', error);

    // Return empty data as fallback
    return NextResponse.json({
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
