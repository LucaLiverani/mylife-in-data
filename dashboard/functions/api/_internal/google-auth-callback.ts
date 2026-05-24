/**
 * GET /api/_internal/google-auth-callback?code=...&state=...
 *
 * - validates `state` (HMAC + 5-min TTL)
 * - exchanges `code` for tokens at Google's OAuth endpoint
 * - upserts into auth.google_tokens via the ClickHouse HTTP interface
 *   (same tunnel + Access service token as the dashboard's other handlers)
 */

import type { Env } from '../../_shared/types';
import { exchangeCodeForTokens, verifyState, emailFromIdToken, GOOGLE_SCOPES } from '../../_shared/google-auth';
import { queryClickHouse } from '../../_shared/clickhouse';

const NEXT_RENEWAL_DAYS = 7;

function htmlPage(title: string, body: string): Response {
  return new Response(
    `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>${title}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
           margin: 0; min-height: 100vh; display: grid; place-items: center; background: #0f172a; color: #e2e8f0; }
    .card { max-width: 480px; padding: 2rem; background: #1e293b; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,.3); }
    h1 { margin-top: 0; font-size: 1.25rem; }
    p { line-height: 1.5; }
    .ok { color: #4ade80; }
    .err { color: #f87171; }
  </style>
</head>
<body>
  <div class="card">${body}</div>
</body>
</html>`,
    { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
  );
}

export async function onRequest(context: { env: Env; request: Request }): Promise<Response> {
  const { env, request } = context;
  const url = new URL(request.url);
  const code = url.searchParams.get('code');
  const state = url.searchParams.get('state');
  const errorParam = url.searchParams.get('error');

  if (errorParam) {
    return htmlPage(
      'Auth failed',
      `<h1 class="err">Auth failed</h1><p>Google returned: <code>${errorParam}</code></p>`
    );
  }

  if (!code || !state) {
    return htmlPage(
      'Auth failed',
      '<h1 class="err">Auth failed</h1><p>Missing <code>code</code> or <code>state</code> parameter.</p>'
    );
  }

  if (!env.GOOGLE_REAUTH_STATE_SECRET) {
    return htmlPage(
      'Server misconfigured',
      '<h1 class="err">Server misconfigured</h1><p>GOOGLE_REAUTH_STATE_SECRET not set in Pages env.</p>'
    );
  }

  const stateOk = await verifyState(state, env.GOOGLE_REAUTH_STATE_SECRET);
  if (!stateOk) {
    return htmlPage(
      'Invalid state',
      '<h1 class="err">Invalid state</h1><p>The link expired or was tampered with. Re-start the re-auth flow.</p>'
    );
  }

  let tokens;
  try {
    tokens = await exchangeCodeForTokens(env, code);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return htmlPage('Auth failed', `<h1 class="err">Token exchange failed</h1><pre>${msg}</pre>`);
  }

  const accountEmail = emailFromIdToken(tokens.id_token) || 'unknown@unknown';
  const expiresAt = new Date(Date.now() + (tokens.expires_in - 30) * 1000).toISOString().replace('T', ' ').slice(0, 19);
  const nextRenewal = new Date(Date.now() + NEXT_RENEWAL_DAYS * 24 * 3600 * 1000).toISOString().slice(0, 10);

  // Build INSERT and run via the same queryClickHouse wrapper.
  // ClickHouse arrays are passed as `['scope1','scope2']` — JSON would also work but we go with array literal.
  const escSql = (s: string) => s.replace(/'/g, "''");
  const scopes = (tokens.scope || GOOGLE_SCOPES.join(' ')).split(/\s+/).filter(Boolean);
  const scopesArr = `[${scopes.map(s => `'${escSql(s)}'`).join(', ')}]`;

  const insertSql =
    `INSERT INTO auth.google_tokens ` +
    `(account_email, refresh_token, access_token, expires_at, scopes, issued_at) ` +
    `VALUES (` +
      `'${escSql(accountEmail)}', ` +
      `'${escSql(tokens.refresh_token || '')}', ` +
      `'${escSql(tokens.access_token)}', ` +
      `toDateTime('${expiresAt}'), ` +
      `${scopesArr}, ` +
      `now()` +
    `)`;

  try {
    await queryClickHouse(env, insertSql);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return htmlPage(
      'ClickHouse write failed',
      `<h1 class="err">ClickHouse write failed</h1><p>Tokens were issued by Google but could not be persisted.</p><pre>${msg}</pre>`
    );
  }

  return htmlPage(
    'Re-auth complete',
    `<h1 class="ok">Re-auth complete</h1>` +
    `<p>Account: <code>${accountEmail}</code></p>` +
    `<p>Next renewal due: <strong>${nextRenewal}</strong>.</p>` +
    `<p>You can close this tab.</p>`
  );
}
