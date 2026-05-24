/**
 * Helpers for the Google OAuth re-auth dance.
 *
 * Google enforces a hard split: Data Portability scopes can only be requested
 * in an OAuth flow that requests nothing else. So the re-auth flow takes a
 * `?group=standard|portability` query param and uses the appropriate scope
 * list. Each flow writes its own row in `auth.google_tokens`, keyed by
 * `scope_group`.
 *
 * State signing uses HMAC-SHA256(timestamp.nonce.group, GOOGLE_REAUTH_STATE_SECRET).
 * The timestamp gives us a TTL (5 min); the nonce protects against replay;
 * the group flows back through state so the callback knows which row to write.
 */

import type { Env } from './types';

export type ScopeGroup = 'standard' | 'portability';

export const GOOGLE_SCOPES: Record<ScopeGroup, string[]> = {
  standard: [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/calendar.events.readonly',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/youtube.readonly',
  ],
  portability: [
    'https://www.googleapis.com/auth/dataportability.myactivity.youtube',
    'https://www.googleapis.com/auth/dataportability.myactivity.maps',
    'https://www.googleapis.com/auth/dataportability.maps.aliased_places',
    'https://www.googleapis.com/auth/dataportability.maps.starred_places',
  ],
};

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

export async function buildState(secret: string, group: ScopeGroup): Promise<string> {
  const ts = Date.now().toString();
  const nonce = crypto.randomUUID();
  const payload = `${ts}.${nonce}.${group}`;
  const sig = await hmacSign(secret, payload);
  return btoa(`${payload}.${sig}`).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export async function verifyState(
  state: string,
  secret: string
): Promise<{ ok: true; group: ScopeGroup } | { ok: false }> {
  let raw: string;
  try {
    const padded = state.replace(/-/g, '+').replace(/_/g, '/');
    raw = atob(padded + '==='.slice(0, (4 - (padded.length % 4)) % 4));
  } catch {
    return { ok: false };
  }
  const parts = raw.split('.');
  if (parts.length !== 4) return { ok: false };
  const [ts, nonce, group, sig] = parts;
  if (group !== 'standard' && group !== 'portability') return { ok: false };
  const expected = await hmacSign(secret, `${ts}.${nonce}.${group}`);
  if (sig !== expected) return { ok: false };
  const ageMs = Date.now() - Number(ts);
  if (ageMs < 0 || ageMs >= STATE_TTL_MS) return { ok: false };
  return { ok: true, group };
}

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
    throw new Error(`Google token exchange failed (${resp.status}): ${await resp.text()}`);
  }
  return resp.json();
}

export function emailFromIdToken(idToken: string | undefined): string {
  if (!idToken) return '';
  const parts = idToken.split('.');
  if (parts.length !== 3) return '';
  try {
    const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = payload + '==='.slice(0, (4 - (payload.length % 4)) % 4);
    return JSON.parse(atob(padded)).email || '';
  } catch {
    return '';
  }
}
