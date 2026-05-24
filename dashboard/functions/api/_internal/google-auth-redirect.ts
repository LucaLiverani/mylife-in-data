/**
 * GET /api/_internal/google-auth-redirect
 *
 * Builds the Google OAuth consent URL with a signed `state` value and 302s
 * the browser there. The callback validates the state and persists tokens.
 */

import type { Env } from '../../_shared/types';
import { buildState, GOOGLE_SCOPES } from '../../_shared/google-auth';

export async function onRequest(context: { env: Env; request: Request }): Promise<Response> {
  const { env } = context;

  if (!env.GOOGLE_CLIENT_ID || !env.GOOGLE_REDIRECT_URI || !env.GOOGLE_REAUTH_STATE_SECRET) {
    return new Response(
      'Google OAuth env not configured. Set GOOGLE_CLIENT_ID, GOOGLE_REDIRECT_URI, and GOOGLE_REAUTH_STATE_SECRET as Pages secrets.',
      { status: 500 }
    );
  }

  const state = await buildState(env.GOOGLE_REAUTH_STATE_SECRET);
  const params = new URLSearchParams({
    client_id: env.GOOGLE_CLIENT_ID,
    redirect_uri: env.GOOGLE_REDIRECT_URI,
    response_type: 'code',
    access_type: 'offline',
    prompt: 'consent',  // forces refresh_token issue on every re-auth
    include_granted_scopes: 'true',
    scope: GOOGLE_SCOPES.join(' '),
    state,
  });

  return Response.redirect(`https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`, 302);
}
