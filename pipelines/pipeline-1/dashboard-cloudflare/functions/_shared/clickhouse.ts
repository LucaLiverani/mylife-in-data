import type { Env } from './types';

/**
 * Query ClickHouse using HTTP API
 * Cloudflare Workers don't support the official ClickHouse Node.js client,
 * so we use the HTTP interface instead.
 */
export async function queryClickHouse<T = any>(
  env: Env,
  query: string
): Promise<T[]> {
  const { CLICKHOUSE_HOST, CLICKHOUSE_USER, CLICKHOUSE_PASSWORD, CLICKHOUSE_DATABASE } = env;

  // Construct authorization header
  const auth = btoa(`${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}`);

  // Build URL with database parameter
  const url = new URL(CLICKHOUSE_HOST);
  url.searchParams.set('database', CLICKHOUSE_DATABASE);
  url.searchParams.set('default_format', 'JSONEachRow');

  try {
    const response = await fetch(url.toString(), {
      method: 'POST',
      headers: {
        'Authorization': `Basic ${auth}`,
        'Content-Type': 'text/plain',
      },
      body: query,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`ClickHouse query failed (${response.status}): ${errorText}`);
    }

    const text = await response.text();

    // ClickHouse returns newline-delimited JSON in JSONEachRow format
    if (!text.trim()) {
      return [];
    }

    const results = text
      .trim()
      .split('\n')
      .map(line => JSON.parse(line));

    return results as T[];
  } catch (error) {
    console.error('ClickHouse query error:', error);
    console.error('Query:', query);
    throw error;
  }
}

/**
 * Execute a query and return a single row
 */
export async function queryClickHouseOne<T = any>(
  env: Env,
  query: string
): Promise<T | null> {
  const results = await queryClickHouse<T>(env, query);
  return results.length > 0 ? results[0] : null;
}
