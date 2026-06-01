import { useState, type ReactNode } from 'react';
import { Check, X, Pencil, ChevronDown, CloudRain, Thermometer } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface Trip {
  start: string;
  end: string;
  destination: string;
  days: number;
  km: number;
  title?: string;
  type?: string;
  country?: string;
  summary?: string;
  confidence?: number;
  weather?: string;
  tempMean?: number;
  precipMm?: number;
  tripKey?: string;
  localities?: number;
  countries?: number;
  maxKm?: number;
}

export type TripStatus = 'confirm' | 'reject' | 'edit';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
function formatRange(start: string, end: string): string {
  const s = new Date(start);
  const e = new Date(end);
  const sm = MONTHS[s.getUTCMonth()];
  const em = MONTHS[e.getUTCMonth()];
  const sy = s.getUTCFullYear();
  const ey = e.getUTCFullYear();
  if (start === end) return `${sm} ${s.getUTCDate()}, ${sy}`;
  if (sy !== ey) return `${sm} ${s.getUTCDate()}, ${sy} – ${em} ${e.getUTCDate()}, ${ey}`;
  if (sm === em) return `${sm} ${s.getUTCDate()}–${e.getUTCDate()}, ${sy}`;
  return `${sm} ${s.getUTCDate()} – ${em} ${e.getUTCDate()}, ${sy}`;
}

const TYPE_LABEL: Record<string, string> = {
  leisure: 'Leisure',
  business: 'Business',
  weekend: 'Weekend',
  day_trip: 'Day trip',
  relocation: 'Relocation',
  visiting: 'Visiting',
  other: 'Trip',
};

const TYPES = ['leisure', 'business', 'weekend', 'day_trip', 'relocation', 'visiting', 'other'];

interface TripTimelineProps {
  trips: Trip[];
  ownerMode: boolean;
  /** trip_key → applied label this session (optimistic). */
  statusByKey: Record<string, TripStatus>;
  /** trip_key currently being written. */
  busyKey: string | null;
  onLabel: (
    trip: Trip,
    label: TripStatus,
    edited?: { title: string; destination: string; type: string },
  ) => void;
}

export function TripTimeline({ trips, ownerMode, statusByKey, busyKey, onLabel }: TripTimelineProps) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [editKey, setEditKey] = useState<string | null>(null);
  const [form, setForm] = useState({ title: '', destination: '', type: 'leisure' });

  const startEdit = (t: Trip) => {
    setForm({
      title: t.title || t.destination || '',
      destination: t.destination || '',
      type: t.type || 'leisure',
    });
    setEditKey(t.tripKey || null);
    setExpanded(t.tripKey || null);
  };

  return (
    <ul className="-mx-6 -mb-6">
      {trips.map((t) => {
        const key = t.tripKey || `${t.start}_${t.end}`;
        const status = statusByKey[key];
        const open = expanded === key;
        const busy = busyKey === key;
        const isEditing = editKey === key;
        const heading = t.title || t.destination;
        const typeLabel = TYPE_LABEL[t.type || ''] || (t.type || 'Trip');
        const conf = typeof t.confidence === 'number' ? Math.round(t.confidence * 100) : null;

        return (
          <li
            key={key}
            className={cn(
              'border-t border-signal-white/5 first:border-t-0 transition-colors duration-150 ease-snap',
              status === 'reject' && 'opacity-45',
            )}
          >
            <button
              type="button"
              onClick={() => setExpanded(open ? null : key)}
              aria-expanded={open}
              className="flex w-full items-center gap-4 px-6 py-3 text-left hover:bg-signal-white/[0.03] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-channel-violet"
            >
              <span className="block size-2 shrink-0 rounded-sm bg-channel-violet" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className={cn('truncate text-sm font-medium text-signal-white', status === 'reject' && 'line-through')}>
                    {heading}
                  </span>
                  <span className="shrink-0 rounded-sm bg-channel-violet/15 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-channel-violet">
                    {typeLabel}
                  </span>
                  {status && (
                    <span
                      className={cn(
                        'shrink-0 font-mono text-[9px] uppercase tracking-wider',
                        status === 'confirm' && 'text-trace-up',
                        status === 'reject' && 'text-trace-down',
                        status === 'edit' && 'text-signal-white/60',
                      )}
                    >
                      · {status === 'confirm' ? 'Confirmed' : status === 'reject' ? 'Rejected' : 'Edited'}
                    </span>
                  )}
                </div>
                <div className="mt-0.5 font-mono text-[10px] uppercase tracking-wider text-signal-white/50">
                  {formatRange(t.start, t.end)}
                </div>
              </div>
              <div className="shrink-0 text-right font-mono text-xs">
                <div className="tabular-nums text-channel-violet">
                  {t.days}d · {t.km.toLocaleString()} km
                </div>
                {t.weather && <div className="mt-0.5 text-[10px] text-signal-white/50">{t.weather}</div>}
              </div>
              <ChevronDown
                className={cn('size-4 shrink-0 text-signal-white/40 transition-transform duration-150', open && 'rotate-180')}
                aria-hidden="true"
              />
            </button>

            {open && (
              <div className="space-y-4 px-6 pb-4 pl-12">
                {t.summary && <p className="text-sm leading-relaxed text-signal-white/80">{t.summary}</p>}

                <div className="flex flex-wrap gap-x-6 gap-y-2 font-mono text-[10px] uppercase tracking-wider text-signal-white/50">
                  {t.country && <span>Country · <span className="text-signal-white/80">{t.country}</span></span>}
                  {typeof t.localities === 'number' && t.localities > 0 && (
                    <span>Localities · <span className="text-signal-white/80">{t.localities}</span></span>
                  )}
                  {typeof t.countries === 'number' && t.countries > 0 && (
                    <span>Countries · <span className="text-signal-white/80">{t.countries}</span></span>
                  )}
                  {typeof t.maxKm === 'number' && t.maxKm > 0 && (
                    <span>Farthest · <span className="text-signal-white/80">{t.maxKm.toLocaleString()} km</span></span>
                  )}
                </div>

                {(t.tempMean !== undefined || t.weather) && t.weather && (
                  <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-signal-white/60">
                    <span className="inline-flex items-center gap-1.5">
                      <Thermometer className="size-3.5 text-channel-violet" aria-hidden="true" />
                      {Math.round(t.tempMean ?? 0)}°C avg
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <CloudRain className="size-3.5 text-channel-violet" aria-hidden="true" />
                      {Math.round(t.precipMm ?? 0)} mm
                    </span>
                  </div>
                )}

                {conf !== null && (
                  <div className="max-w-xs">
                    <div className="mb-1 flex items-center justify-between font-mono text-[9px] uppercase tracking-wider text-signal-white/40">
                      <span>Model confidence</span>
                      <span className="tabular-nums">{conf}%</span>
                    </div>
                    <div className="h-1 overflow-hidden rounded-full bg-signal-white/10">
                      <div className="h-full rounded-full bg-channel-violet" style={{ width: `${conf}%` }} />
                    </div>
                  </div>
                )}

                {ownerMode && !isEditing && (
                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    <OwnerButton onClick={() => onLabel(t, 'confirm')} disabled={busy} tone="up">
                      <Check className="size-3.5" /> Confirm
                    </OwnerButton>
                    <OwnerButton onClick={() => onLabel(t, 'reject')} disabled={busy} tone="down">
                      <X className="size-3.5" /> Reject
                    </OwnerButton>
                    <OwnerButton onClick={() => startEdit(t)} disabled={busy} tone="neutral">
                      <Pencil className="size-3.5" /> Edit
                    </OwnerButton>
                    {busy && <span className="font-mono text-[10px] text-signal-white/40">saving…</span>}
                  </div>
                )}

                {ownerMode && isEditing && (
                  <div className="space-y-2 pt-1">
                    <EditField label="Title" value={form.title} onChange={(v) => setForm((f) => ({ ...f, title: v }))} />
                    <EditField label="Destination" value={form.destination} onChange={(v) => setForm((f) => ({ ...f, destination: v }))} />
                    <div>
                      <label className="mb-1 block font-mono text-[9px] uppercase tracking-wider text-signal-white/40">Type</label>
                      <select
                        value={form.type}
                        onChange={(e) => setForm((f) => ({ ...f, type: e.target.value }))}
                        className="w-full rounded-sm border border-signal-white/15 bg-rack-black/80 px-2 py-1 font-mono text-xs text-signal-white focus-visible:outline focus-visible:outline-1 focus-visible:outline-channel-violet"
                      >
                        {TYPES.map((ty) => (
                          <option key={ty} value={ty}>{TYPE_LABEL[ty]}</option>
                        ))}
                      </select>
                    </div>
                    <div className="flex gap-2 pt-1">
                      <OwnerButton
                        onClick={() => { onLabel(t, 'edit', form); setEditKey(null); }}
                        disabled={busy}
                        tone="up"
                      >
                        <Check className="size-3.5" /> Save
                      </OwnerButton>
                      <OwnerButton onClick={() => setEditKey(null)} disabled={busy} tone="neutral">
                        Cancel
                      </OwnerButton>
                    </div>
                  </div>
                )}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function OwnerButton({
  children,
  onClick,
  disabled,
  tone,
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  tone: 'up' | 'down' | 'neutral';
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-sm border px-2 py-1 font-mono text-[10px] uppercase tracking-wider transition-colors duration-150 ease-snap disabled:opacity-40',
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-channel-violet',
        tone === 'up' && 'border-trace-up/30 text-trace-up hover:bg-trace-up/10',
        tone === 'down' && 'border-trace-down/30 text-trace-down hover:bg-trace-down/10',
        tone === 'neutral' && 'border-signal-white/15 text-signal-white/70 hover:bg-signal-white/[0.05]',
      )}
    >
      {children}
    </button>
  );
}

function EditField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="mb-1 block font-mono text-[9px] uppercase tracking-wider text-signal-white/40">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-sm border border-signal-white/15 bg-rack-black/80 px-2 py-1 font-mono text-xs text-signal-white focus-visible:outline focus-visible:outline-1 focus-visible:outline-channel-violet"
      />
    </div>
  );
}
