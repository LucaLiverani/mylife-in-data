/**
 * alert-mailer — Alertmanager webhook receiver that emails alerts.
 *
 * POST /  body = Alertmanager v4 webhook payload, auth = `Authorization:
 * Bearer <ALERT_WEBHOOK_TOKEN>`. One email per webhook delivery; Alertmanager
 * owns grouping/dedup/repeat cadence, this Worker only formats and sends.
 *
 * Sending prefers the Email Service `send()` API and falls back to the legacy
 * Email Routing `EmailMessage` path when the zone isn't onboarded to Email
 * Sending (the legacy path requires ALERT_EMAIL_TO to be a verified Email
 * Routing destination address).
 */

// @ts-ignore — runtime-provided module, no local type package for it.
import { EmailMessage } from "cloudflare:email";

interface AmAlert {
  status: "firing" | "resolved";
  labels: Record<string, string>;
  annotations: Record<string, string>;
  startsAt: string;
  endsAt: string;
  generatorURL?: string;
}

interface AmWebhook {
  version: string;
  status: "firing" | "resolved";
  receiver: string;
  groupLabels: Record<string, string>;
  commonLabels: Record<string, string>;
  commonAnnotations: Record<string, string>;
  externalURL: string;
  alerts: AmAlert[];
}

interface Env {
  EMAIL: {
    send(message: unknown): Promise<{ messageId?: string } | void>;
  };
  ALERT_WEBHOOK_TOKEN: string;
  ALERT_EMAIL_TO: string;
  ALERT_EMAIL_FROM: string;
}

function fmtSince(iso: string): string {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso;
  const mins = Math.round((Date.now() - t) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  if (mins < 48 * 60) return `${Math.round(mins / 60)}h ago`;
  return `${Math.round(mins / (60 * 24))}d ago`;
}

function subjectFor(p: AmWebhook): string {
  const names = [...new Set(p.alerts.map((a) => a.labels.alertname || "alert"))];
  const head = names.slice(0, 3).join(", ") + (names.length > 3 ? ` +${names.length - 3}` : "");
  const env = p.commonLabels.environment ? ` ${p.commonLabels.environment}` : "";
  const severity = p.commonLabels.severity ? ` [${p.commonLabels.severity}]` : "";
  const count = p.alerts.length > 1 ? ` (${p.alerts.length} alerts)` : "";
  return `[mylife-in-data${env}] ${p.status.toUpperCase()}${severity}: ${head}${count}`;
}

function alertLines(a: AmAlert): string[] {
  const lines = [
    `${a.status === "firing" ? "🔥" : "✅"} ${a.labels.alertname || "alert"}` +
      (a.labels.severity ? ` (${a.labels.severity})` : ""),
  ];
  if (a.annotations.summary) lines.push(`   ${a.annotations.summary}`);
  if (a.annotations.description) lines.push(`   ${a.annotations.description}`);
  const detail = Object.entries(a.labels)
    .filter(([k]) => !["alertname", "severity", "environment", "cluster"].includes(k))
    .map(([k, v]) => `${k}=${v}`)
    .join(" ");
  if (detail) lines.push(`   ${detail}`);
  lines.push(`   since: ${fmtSince(a.startsAt)}`);
  return lines;
}

function bodyFor(p: AmWebhook): { text: string; html: string } {
  const blocks = p.alerts.map((a) => alertLines(a).join("\n"));
  const text = [
    `${p.status === "firing" ? "Alerts firing" : "Alerts resolved"} on the data platform.`,
    "",
    ...blocks,
    "",
    `Grafana/Prometheus live behind the VM; Alertmanager group: ${
      Object.entries(p.groupLabels).map(([k, v]) => `${k}=${v}`).join(",") || "(none)"
    }`,
  ].join("\n");
  const esc = (s: string) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const html = `<pre style="font-family:ui-monospace,monospace;font-size:13px">${esc(text)}</pre>`;
  return { text, html };
}

/** Legacy Email Routing path: hand-rolled MIME, no extra deps. */
function rawMime(from: string, to: string, subject: string, text: string): string {
  const b64 = btoa(unescape(encodeURIComponent(text)));
  const wrapped = b64.replace(/(.{76})/g, "$1\r\n");
  return [
    `From: My Life in Data <${from}>`,
    `To: <${to}>`,
    `Subject: ${subject}`,
    `Date: ${new Date().toUTCString()}`,
    `Message-ID: <${crypto.randomUUID()}@${from.split("@")[1] || "alert-mailer"}>`,
    "MIME-Version: 1.0",
    'Content-Type: text/plain; charset="utf-8"',
    "Content-Transfer-Encoding: base64",
    "",
    wrapped,
  ].join("\r\n");
}

async function sendEmail(env: Env, subject: string, text: string, html: string): Promise<string> {
  try {
    await env.EMAIL.send({
      to: env.ALERT_EMAIL_TO,
      from: { email: env.ALERT_EMAIL_FROM, name: "My Life in Data" },
      subject,
      text,
      html,
    });
    return "email-service";
  } catch (err: any) {
    const code = err?.code ?? "";
    const fallbackCodes = ["E_SENDER_NOT_VERIFIED", "E_SENDER_DOMAIN_NOT_AVAILABLE", "E_VALIDATION_ERROR"];
    if (!fallbackCodes.includes(code)) throw err;
    // Zone not onboarded to Email Sending — fall back to Email Routing send.
    await env.EMAIL.send(
      new EmailMessage(
        env.ALERT_EMAIL_FROM,
        env.ALERT_EMAIL_TO,
        rawMime(env.ALERT_EMAIL_FROM, env.ALERT_EMAIL_TO, subject, text),
      ),
    );
    return "email-routing";
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === "GET") {
      return new Response("alert-mailer up\n", { status: 200 });
    }
    if (request.method !== "POST") {
      return new Response("method not allowed\n", { status: 405 });
    }
    const auth = request.headers.get("Authorization") || "";
    if (!env.ALERT_WEBHOOK_TOKEN || auth !== `Bearer ${env.ALERT_WEBHOOK_TOKEN}`) {
      return new Response("unauthorized\n", { status: 401 });
    }

    let payload: AmWebhook;
    try {
      payload = (await request.json()) as AmWebhook;
      if (!Array.isArray(payload.alerts) || payload.alerts.length === 0) {
        return new Response("no alerts in payload\n", { status: 400 });
      }
    } catch {
      return new Response("invalid JSON\n", { status: 400 });
    }

    const subject = subjectFor(payload);
    const { text, html } = bodyFor(payload);
    try {
      const via = await sendEmail(env, subject, text, html);
      return Response.json({ ok: true, alerts: payload.alerts.length, via });
    } catch (err: any) {
      console.error("send failed:", err?.code, err?.message);
      return Response.json(
        { ok: false, code: err?.code ?? null, error: String(err?.message ?? err) },
        { status: 502 },
      );
    }
  },
};
