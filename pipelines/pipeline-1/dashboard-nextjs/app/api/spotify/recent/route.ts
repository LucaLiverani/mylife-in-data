/**
 * Spotify Recent Tracks API Route
 * Returns recently played tracks
 */

import { NextResponse } from 'next/server';
import { queryClickHouse } from '@/lib/clickhouse';
import { formatDistanceToNow } from 'date-fns';

export const dynamic = 'force-dynamic';
export const revalidate = 10; // More frequent updates for recent tracks

interface RecentTrack {
  track: string;
  artist: string;
  played_at: string;
  album_art: string;
}

export async function GET() {
  try {
    // Query pre-aggregated gold recent tracks table
    const query = `
      SELECT
        track,
        artist,
        played_at,
        album_art
      FROM analytics_gold.gold_spotify_recent_tracks
      ORDER BY recency_rank
      LIMIT 50
    `;

    const results = await queryClickHouse<RecentTrack>(query);

    // Format the results with relative timestamps
    const formattedResults = results.map(track => ({
      track: track.track,
      artist: track.artist,
      time: formatDistanceToNow(new Date(track.played_at), { addSuffix: true }),
      albumArt: track.album_art || `https://picsum.photos/seed/${track.artist}/100`,
    }));

    return NextResponse.json(formattedResults.slice(0, 10));
  } catch (error) {
    console.error('Error fetching recent tracks:', error);
    // Return empty array instead of error to allow page to load
    return NextResponse.json([]);
  }
}
