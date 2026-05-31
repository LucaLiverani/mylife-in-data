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

  // Google OAuth — Web Application client.
  // Used by /api/internal/google-auth-{redirect,callback}.
  GOOGLE_CLIENT_ID?: string;
  GOOGLE_CLIENT_SECRET?: string;
  GOOGLE_REDIRECT_URI?: string;
  GOOGLE_REAUTH_STATE_SECRET?: string;
  // Fallback for the portability flow, whose response carries no id_token
  // (no openid/userinfo.email scopes) and otherwise lands as unknown@unknown.
  GOOGLE_ACCOUNT_EMAIL?: string;

  // Calendar webhook — shared secret between Pages Function and Google's
  // events.watch subscriptions. Validated on every notification POST.
  CALENDAR_WEBHOOK_TOKEN?: string;

  // Owner-only trip labeling. The /api/travel/trip-label endpoint accepts a
  // write only when the request carries this token; the dashboard's "owner
  // mode" stores it client-side. Absent (public) → labeling is read-only.
  TRIP_LABEL_TOKEN?: string;
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
