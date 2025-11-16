/**
 * Cloudflare Workers environment bindings
 * Add your environment variables and secrets here
 */
export interface Env {
  // ClickHouse connection
  CLICKHOUSE_HOST: string;
  CLICKHOUSE_USER: string;
  CLICKHOUSE_PASSWORD: string;
  CLICKHOUSE_DATABASE: string;

  // Kafka connection (for polling endpoint)
  KAFKA_BOOTSTRAP_SERVERS?: string;
  KAFKA_TOPIC?: string;
}

/**
 * Context object passed to Workers Functions
 */
export interface Context {
  request: Request;
  env: Env;
  params: Record<string, string>;
  waitUntil: (promise: Promise<any>) => void;
}
