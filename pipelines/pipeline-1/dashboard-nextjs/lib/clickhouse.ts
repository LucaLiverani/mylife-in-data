/**
 * ClickHouse client for querying analytics data
 * Uses the official @clickhouse/client package
 */

import { createClient, ClickHouseClient } from '@clickhouse/client';

let clickhouseClient: ClickHouseClient | null = null;

/**
 * Get or create singleton ClickHouse client
 */
export function getClickHouseClient(): ClickHouseClient {
  if (!clickhouseClient) {
    const host = process.env.CLICKHOUSE_HOST || 'http://localhost:8123';
    const username = process.env.CLICKHOUSE_USER || 'admin';
    const password = process.env.CLICKHOUSE_PASSWORD || 'clickhouse08062013';
    const database = process.env.CLICKHOUSE_DATABASE || 'analytics';

    clickhouseClient = createClient({
      host,
      username,
      password,
      database,
      request_timeout: 30000, // 30 seconds
    });

    console.log(`ClickHouse client initialized: ${host}/${database}`);
  }

  return clickhouseClient;
}

/**
 * Execute a query and return results as JSON array
 */
export async function queryClickHouse<T = any>(query: string): Promise<T[]> {
  const client = getClickHouseClient();

  try {
    const resultSet = await client.query({
      query,
      format: 'JSONEachRow',
    });

    const data = await resultSet.json<T>();
    return data;
  } catch (error) {
    console.error('ClickHouse query error:', error);
    console.error('Query:', query);
    throw error;
  }
}

/**
 * Execute a query and return a single row
 */
export async function queryClickHouseOne<T = any>(query: string): Promise<T | null> {
  const results = await queryClickHouse<T>(query);
  return results.length > 0 ? results[0] : null;
}

/**
 * Close the ClickHouse client connection
 * Call this during shutdown/cleanup
 */
export async function closeClickHouseClient() {
  if (clickhouseClient) {
    await clickhouseClient.close();
    clickhouseClient = null;
    console.log('ClickHouse client closed');
  }
}
