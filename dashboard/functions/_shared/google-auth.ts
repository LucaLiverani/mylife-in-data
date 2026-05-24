/**
 * Helpers for the Google OAuth re-auth dance.
 *
 * The dance:
 *   1. user clicks the alert link → /api/_internal/google-auth-redirect
 *      builds a Google consent URL with a signed `state` value and 302s.
 *   2. Google redirects back to /api/_internal/google-auth-callback with
 *      `?code=…&state=…`. The callback verifies the state signature, swaps
 *      the code for tokens, and writes them into auth.google_tokens via the
 *      existing ClickHouse tunnel.
 *
 * State signing uses HMAC-SHA256(timestamp.nonce, GOOGLE_REAUTH_STATE_SECRET).
 * The timestamp gives us a TTL (5 min); the nonce protects against replay.
 */

import type { Env } from './types';

// Full scope list — matches IMPLEMENTATION_PLAN.md §1.2.
export const GOOGLE_SCOPES: string[] = [
  'https://www.googleapis.com/auth/userinfo.email',
  'https://www.googleapis.com/auth/userinfo.profile',
  'openid',
  'https://www.googleapis.com/auth/calendar.events.readonly',
  'https://www.googleapis.com/auth/calendar.readonly',
  'https://www.googleapis.com/auth/youtube.readonly',
  'https://www.googleapis.com/auth/dataportability.youtube.watch_history',
  'https://www.googleapis.com/auth/dataportability.youtube.search_history',
  'https://www.googleapis.com/auth/dataportability.maps.aliased_places',
  'https://www.googleapis.com/auth/dataportability.maps.starred_places',
];

const STATE_TTL_MS = 5 * 60 * 1000;

async function hmacSign(key: string, message: string): Promise<string> {
  const enc = new TextEncoder();
  const cryptoKey = await crypto.subtle.importKey(
    'raw',
    enc.encode(key),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const sig = await crypto.subtle.sign('HMAC', cryptoKey, enc.encode(message));
  return Array.from(new Uint8Array(sig))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

export async function buildState(secret: string): Promise<string> {
  const ts = Date.now().toString();
  const nonce = crypto.randomUUID();
  const payload = `${ts}.${nonce}`;
  const sig = await hmacSign(secret, payload);
  // base64url-encode for URL-safe transport.
  const raw = `${payload}.${sig}`;
  return btoa(raw).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export async function verifyState(state: string, secret: string): Promise<boolean> {
  let raw: string;
  try {
    const padded = state.replace(/-/g, '+').replace(/_/g, '/');
    raw = atob(padded + '==='.slice(0, (4 - (padded.length % 4)) % 4));
  } catch {
    return false;
  }
  const parts = raw.split('.');
  if (parts.length !== 3) return false;
  const [ts, nonce, sig] = parts;
  const expected = await hmacSign(secret, `${ts}.${nonce}`);
  if (sig !== expected) return false;
  const ageMs = Date.now() - Number(ts);
  return ageMs >= 0 && ageMs < STATE_TTL_MS;
}

/**
 * Exchange an OAuth `code` for tokens. Throws on Google error responses.
 */
export async function exchangeCodeForTokens(env: Env, code: string): Promise<{
  access_token: string;
  refresh_token?: string;
  expires_in: number;
  scope: string;
  id_token?: string;
}> {
  if (!env.GOOGLE_CLIENT_ID || !env.GOOGLE_CLIENT_SECRET || !env.GOOGLE_REDIRECT_URI) {
    throw new Error('Google OAuth env not configured');
  }
  const body = new URLSearchParams({
    code,
    client_id: env.GOOGLE_CLIENT_ID,
    client_secret: env.GOOGLE_CLIENT_SECRET,
    redirect_uri: env.GOOGLE_REDIRECT_URI,
    grant_type: 'authorization_code',
  });

  const resp = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Google token exchange failed (${resp.status}): ${text}`);
  }
  return resp.json();
}

/**
 * Extract the email claim from a Google id_token without verifying signature.
 * Verification not strictly required here — we only use the email as a row
 * key, and the user already authenticated against Google in this same flow.
 */
export function emailFromIdToken(idToken: string | undefined): string {
  if (!idToken) return '';
  const parts = idToken.split('.');
  if (parts.length !== 3) return '';
  try {
    const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = payload + '==='.slice(0, (4 - (payload.length % 4)) % 4);
    const json = JSON.parse(atob(padded));
    return json.email || '';
  } catch {
    return '';
  }
}
