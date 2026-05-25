/**
 * GET /api/internal/google-auth-redirect?group=standard|portability
 *
 * Builds the Google OAuth consent URL with a signed `state` value (which
 * encodes the chosen scope group so the callback knows which row to write)
 * and 302s the browser there.
 */

import type { Env } from '../../_shared/types';
import { buildState, GOOGLE_SCOPES, type ScopeGroup } from '../../_shared/google-auth';

export async function onRequest(context: { env: Env; request: Request }): Promise<Response> {
  const { env, request } = context;

  if (!env.GOOGLE_CLIENT_ID || !env.GOOGLE_REDIRECT_URI || !env.GOOGLE_REAUTH_STATE_SECRET) {
    return new Response(
      'Google OAuth env not configured. Set GOOGLE_CLIENT_ID, GOOGLE_REDIRECT_URI, and GOOGLE_REAUTH_STATE_SECRET as Pages secrets.',
      { status: 500 }
    );
  }

  const url = new URL(request.url);
  const requested = (url.searchParams.get('group') || 'standard') as ScopeGroup;
  if (requested !== 'standard' && requested !== 'portability') {
    return new Response(
      'Invalid group. Use ?group=standard or ?group=portability.',
      { status: 400 }
    );
  }

  const state = await buildState(env.GOOGLE_REAUTH_STATE_SECRET, requested);
  const params = new URLSearchParams({
    client_id: env.GOOGLE_CLIENT_ID,
    redirect_uri: env.GOOGLE_REDIRECT_URI,
    response_type: 'code',
    access_type: 'offline',
    prompt: 'consent',
    // `include_granted_scopes` is rejected by Data Portability scopes
    // ("Incremental auth is not allowed"). prompt=consent already forces a
    // fresh grant, so incremental auth was redundant anyway.
    scope: GOOGLE_SCOPES[requested].join(' '),
    state,
  });

  return Response.redirect(`https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`, 302);
}
