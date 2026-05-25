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

  // Cloudflare Access service token — only set in production when
  // CLICKHOUSE_HOST is behind Cloudflare Access. Local dev hits ClickHouse
  // directly and leaves these unset.
  CF_ACCESS_CLIENT_ID?: string;
  CF_ACCESS_CLIENT_SECRET?: string;

  // Kafka connection (for polling endpoint)
  KAFKA_BOOTSTRAP_SERVERS?: string;
  KAFKA_TOPIC?: string;

  // Google OAuth — Web Application client (see IMPLEMENTATION_PLAN.md §1.2).
  // Used by /api/internal/google-auth-{redirect,callback}.
  GOOGLE_CLIENT_ID?: string;
  GOOGLE_CLIENT_SECRET?: string;
  GOOGLE_REDIRECT_URI?: string;
  GOOGLE_REAUTH_STATE_SECRET?: string;

  // Calendar webhook — shared secret between Pages Function and Google's
  // events.watch subscriptions. Validated on every notification POST.
  CALENDAR_WEBHOOK_TOKEN?: string;
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
