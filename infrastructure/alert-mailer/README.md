# alert-mailer

Cloudflare Worker that turns Alertmanager webhook deliveries into email, using
Cloudflare Email Service on the dashboard's own zone. It is the single email
egress for the platform: Prometheus alert rules and the Dagster
`run_failure_alert_sensor` both reach it through Alertmanager
(`infrastructure/compose/monitoring/alertmanager.yml`), never directly.

```
Prometheus rules ─┐
                  ├─> Alertmanager ──POST (Bearer token)──> alert-mailer ──> inbox
Dagster failures ─┘      (VM)              (Worker)
```

## Deploy / update

Uses the wrangler already pinned by `dashboard/` (no deps of its own):

```bash
cd infrastructure/alert-mailer
../../dashboard/node_modules/.bin/wrangler deploy
```

First-time secrets (values in the password manager / `infrastructure/.env` on
the VM):

```bash
W=../../dashboard/node_modules/.bin/wrangler
$W secret put ALERT_WEBHOOK_TOKEN   # same value as ALERT_WEBHOOK_TOKEN in the VM .env
$W secret put ALERT_EMAIL_TO        # where alerts go
$W secret put ALERT_EMAIL_FROM      # alerts@<DOMAIN>
```

## Test the channel end to end

```bash
curl -sS -X POST "$ALERT_WEBHOOK_URL" \
  -H "Authorization: Bearer $ALERT_WEBHOOK_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"version":"4","status":"firing","receiver":"email","groupLabels":{},
       "commonLabels":{"severity":"critical","environment":"vm"},
       "commonAnnotations":{},"externalURL":"",
       "alerts":[{"status":"firing","labels":{"alertname":"TestAlert","severity":"critical"},
                  "annotations":{"summary":"Synthetic test alert"},
                  "startsAt":"2026-01-01T00:00:00Z","endsAt":"0001-01-01T00:00:00Z"}]}'
```

`{"ok":true,...,"via":"email-service"}` plus an email in the inbox means the
whole channel works. `via":"email-routing"` means the zone is not onboarded to
Email Sending and the Worker used the legacy Email Routing path (recipient must
then be a verified Email Routing destination address).

## Notes

- The Worker URL and token are not committed; they live in `infrastructure/.env`
  (`ALERT_WEBHOOK_URL`, `ALERT_WEBHOOK_TOKEN`) and the password manager.
- Rotation: `openssl rand -hex 32`, update the Worker secret and the VM `.env`,
  recreate Alertmanager (`docker compose --profile alerting up -d alertmanager`).
- Ops runbook: `docs/OPERATIONS.md` → "Monitoring & alerting".
