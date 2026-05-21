import { useEffect, useState } from 'react';
import { nowAPI } from '@/lib/api';
import { type Channel } from '@/lib/channels';

export interface TimelineEvent {
  time: string;          // ISO
  channel: Channel;
  label: string;         // e.g. "Track started"
  value: string;         // e.g. "Strobe — Deadmau5"
  href?: string;
}

export interface NowTimeline {
  generatedAt: string;
  windowMinutes: number;
  events: TimelineEvent[];
  /** Per-source ingestion cadence label, optional. */
  ingestionCadence?: Record<Channel, string>;
}

export interface LiveTimelineState {
  data: NowTimeline | null;
  events: TimelineEvent[];        // sorted youngest first
  lastSync: Date | null;
  loading: boolean;
  error: string | null;
  /** Re-render token incremented every second; consumers reading relative time use this. */
  tick: number;
}

const DEFAULT_REFRESH_MS = 15_000;

/**
 * Polls /api/now/timeline at a fixed cadence (default 15s) and returns the
 * latest cross-channel event stream. Pauses while the tab is hidden so we
 * don't burn the network in the background.
 *
 * Shared by the `/now` page (full timeline) and the embedded LiveConsole on
 * Home (compact, top-N events). One hook = one polling loop per consumer
 * — keep call sites singular per page if you can.
 */
export function useLiveTimeline(refreshMs: number = DEFAULT_REFRESH_MS): LiveTimelineState {
  const [data, setData] = useState<NowTimeline | null>(null);
  const [lastSync, setLastSync] = useState<Date | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let active = true;
    let timeoutId: number | undefined;

    const poll = async () => {
      if (!active) return;
      if (typeof document !== 'undefined' && document.hidden) {
        timeoutId = window.setTimeout(poll, refreshMs);
        return;
      }
      try {
        const result = (await nowAPI.getTimeline()) as NowTimeline;
        if (!active) return;
        setData(result);
        setError(null);
        setLastSync(new Date());
      } catch (err) {
        if (!active) return;
        console.error('Live timeline poll failed:', err);
        setError('Could not reach /api/now/timeline');
        setLastSync(new Date());
      } finally {
        if (active) setLoading(false);
      }
      if (active) timeoutId = window.setTimeout(poll, refreshMs);
    };

    const onVisibilityChange = () => {
      if (!document.hidden && active) {
        if (timeoutId) clearTimeout(timeoutId);
        poll();
      }
    };

    poll();
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      active = false;
      if (timeoutId) clearTimeout(timeoutId);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [refreshMs]);

  // 1Hz tick so consumers can render smoothly-updating "Xs ago" lines.
  useEffect(() => {
    const id = window.setInterval(() => setTick((t) => t + 1), 1000);
    return () => window.clearInterval(id);
  }, []);

  const events = (data?.events ?? []).slice().sort(
    (a, b) => new Date(b.time).getTime() - new Date(a.time).getTime(),
  );

  return { data, events, lastSync, loading, error, tick };
}
