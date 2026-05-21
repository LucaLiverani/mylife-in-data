/**
 * Single source of truth for KPI / number formatting across the dashboard.
 *
 * The API may emit values as raw numbers (preferred) or as legacy pre-formatted
 * strings like `"84h"`, `"1,234"`, `"12.4%"`. Each formatter accepts either —
 * pre-formatted strings get parsed and re-formatted so the surface stays
 * consistent regardless of upstream drift.
 */

/** Coerce raw or pre-formatted input to a finite number, or null if unparseable. */
function toNumber(value: number | string | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  const cleaned = String(value).replace(/,/g, '').replace(/\s+/g, '').replace(/[a-zA-Z%]+$/u, '');
  const n = parseFloat(cleaned);
  return Number.isFinite(n) ? n : null;
}

/** `4325` → `"4,325"`, `"1234"` → `"1,234"`. Falls back to the input string on parse failure. */
export function formatCount(value: number | string | null | undefined): string {
  const n = toNumber(value);
  if (n === null) return String(value ?? '—');
  return Math.round(n).toLocaleString('en-US');
}

/**
 * Hours formatter. Precision adapts to magnitude:
 *   `253h`     when ≥ 100
 *   `42.8h`    when 10–99.9
 *   `2.8h`     when < 10
 * Accepts raw numbers, `"253 hrs"`, `"84h"`, etc.
 */
export function formatHours(value: number | string | null | undefined): string {
  const n = toNumber(value);
  if (n === null) return String(value ?? '—');
  if (n >= 100) return `${Math.round(n)}h`;
  if (n >= 10)  return `${n.toFixed(1)}h`;
  return `${n.toFixed(1)}h`;
}

/** `12.4` or `"12.4"` or `"12.4%"` → `"12.4%"`. */
export function formatPercent(value: number | string | null | undefined, decimals = 1): string {
  const n = toNumber(value);
  if (n === null) return String(value ?? '—');
  return `${n.toFixed(decimals)}%`;
}

/** `2.8` → `"2.8"`, with consistent decimal precision. */
export function formatDecimal(value: number | string | null | undefined, decimals = 1): string {
  const n = toNumber(value);
  if (n === null) return String(value ?? '—');
  return n.toFixed(decimals);
}

export type KpiKind = 'count' | 'hours' | 'percent' | 'decimal' | 'text';

/**
 * Absolute timestamp in `YYYY-MM-DD · HH:MM` (24h). Always shows both date
 * and time so every row aligns and the date is unambiguous regardless of
 * locale. Falls back to the input string if it cannot be parsed.
 */
export function formatEventTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);

  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const HH = String(d.getHours()).padStart(2, '0');
  const MM = String(d.getMinutes()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd} · ${HH}:${MM}`;
}

/** Polymorphic dispatcher for KPIMetric. */
export function formatKpi(value: number | string | null | undefined, kind: KpiKind): string {
  switch (kind) {
    case 'count':   return formatCount(value);
    case 'hours':   return formatHours(value);
    case 'percent': return formatPercent(value);
    case 'decimal': return formatDecimal(value);
    case 'text':    return value === null || value === undefined ? '—' : String(value);
  }
}
