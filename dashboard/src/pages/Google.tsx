import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { FadeIn } from '@/components/animations/FadeIn';
import { Surface } from '@/components/Surface';
import { KPIMetric } from '@/components/KPIMetric';
import { ChannelPie } from '@/components/charts/ChannelPie';
import { ChannelHistogram } from '@/components/charts/ChannelHistogram';
import { CalendarHeatmap } from '@/components/charts/CalendarHeatmap';
import { calendarAPI } from '@/lib/api';
import { CHANNEL_HEX, CHANNEL_RAMP } from '@/lib/channels';
import { CHART_STYLES, formatChartDate } from '@/components/charts/chartConfig';

interface CalendarData {
  kpis: {
    plansCount: number | string;
    freeDays: number | string;
    totalEvents: number | string;
    meetingHours: number | string;
    avgDaily: number | string;
    busiestDay: string;
    freeTimePerDay?: number | string;          // minutes
    longestUnscheduledHours?: number | string; // hours
    weekendLeakage?: number | string;
    fragmentation?: number | string;
  };
  busyHours: Array<{ hour: string; events: number }>;
  categories: Array<{ name: string; value: number; percentage: number }>;
  weekdayBreakdown: Array<{ day: string; events: number }>;
  upcomingEvents: Array<{ title: string; category: string; time: string; relativeTime: string; durationMinutes: number }>;
  dailyEvents: Array<{ date: string; events: number }>;
  weekGrid?: Array<{ day: number; hour: number; intensity: number }>;
}

export default function GooglePage() {
  const [data, setData] = useState<CalendarData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    calendarAPI.getData()
      .then((d) => setData(d as CalendarData))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-[80vh] items-center justify-center text-signal-white">
        <p className="font-mono text-sm uppercase tracking-wider text-signal-white/60">Loading the schedule…</p>
      </div>
    );
  }

  if (!data) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-20 text-signal-white">
        <p className="font-mono text-xs uppercase tracking-wider text-trace-down">
          No calendar data yet. Calendar ingestion is still being wired up.
        </p>
      </main>
    );
  }

  const dailyChart = data.dailyEvents.slice(-30).map((d) => ({
    date: formatChartDate(d.date),
    events: d.events,
  }));

  // Stable per-category color drawn from the calendar tonal ramp,
  // so the "Coming up" LED matches what the Categories donut uses.
  const categoryOrder: string[] = Array.from(new Set(data.categories.map((c) => c.name)));
  const colorForCategory = (name: string): string => {
    const idx = categoryOrder.indexOf(name);
    if (idx < 0) return CHANNEL_HEX.calendar;
    return CHANNEL_RAMP.calendar[idx % CHANNEL_RAMP.calendar.length];
  };

  // Map dailyEvents to the CalendarHeatmap shape (date → value).
  const heatmapData: Record<string, number> = {};
  for (const d of data.dailyEvents) heatmapData[d.date] = d.events;

  const freeTimeMins = toNum(data.kpis.freeTimePerDay);
  const freeTimeHours = freeTimeMins !== null ? (freeTimeMins / 60).toFixed(1) : '—';

  return (
    <main className="min-h-screen text-signal-white">
      <div className="mx-auto max-w-7xl px-6 py-12">
        <FadeIn>
          <Link
            to="/"
            className="mb-8 inline-flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-signal-white/60 transition-colors hover:text-signal-white"
          >
            <ArrowLeft className="size-4" aria-hidden="true" />
            Back to console
          </Link>
          <div className="mb-12">
            <h1 className="mb-4 text-5xl font-bold leading-[1.0] tracking-tight lg:text-7xl">
              <span className="text-channel-blue">Calendar</span> Analytics
            </h1>
            <p className="text-xl italic text-signal-white/60">
              Meetings I'll show up to, plans I might honor, white space I should defend.
            </p>
          </div>
        </FadeIn>

        {/* Primary KPI row */}
        <section className="mb-8" aria-labelledby="calendar-kpis">
          <FadeIn delay={0.1}>
            <h2 id="calendar-kpis" className="mb-4 font-mono text-xs uppercase tracking-wider text-signal-white/60">Overview</h2>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <KPIMetric label="Plans"     value={data.kpis.plansCount}   kind="count"   channel="calendar" />
              <KPIMetric label="Free days" value={data.kpis.freeDays}     kind="count"   channel="calendar" />
              <KPIMetric label="Hours"     value={data.kpis.meetingHours} kind="hours"   channel="calendar" />
              <KPIMetric label="Avg / day" value={data.kpis.avgDaily}     kind="decimal" channel="calendar" />
            </div>
          </FadeIn>
        </section>

        {/* Producer-console signature row — free time, gaps, fragmentation */}
        <section className="mb-12" aria-labelledby="calendar-signature">
          <FadeIn delay={0.15}>
            <h2 id="calendar-signature" className="mb-4 font-mono text-xs uppercase tracking-wider text-signal-white/60">
              Negative space
            </h2>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <KPIMetric label="Free / day"        value={freeTimeHours}                       kind="text"    channel="calendar" />
              <KPIMetric label="Longest gap"       value={data.kpis.longestUnscheduledHours ?? '—'} kind="hours"   channel="calendar" />
              <KPIMetric label="Fragmentation"     value={data.kpis.fragmentation ?? '—'}      kind="decimal" channel="calendar" />
              <KPIMetric label="Weekend leakage"   value={data.kpis.weekendLeakage ?? 0}       kind="count"   channel="calendar" />
            </div>
          </FadeIn>
        </section>

        {/* 1. Daily time-series */}
        <FadeIn delay={0.2}>
          <section className="mb-12" aria-labelledby="calendar-daily">
            <Surface>
              <h2 id="calendar-daily" className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
                Daily events · last 30 days
              </h2>
              <div className="h-80">
                <ResponsiveContainer>
                  <LineChart data={dailyChart}>
                    <CartesianGrid {...CHART_STYLES.cartesianGrid} />
                    <XAxis
                      dataKey="date"
                      stroke="rgba(255,255,255,0.25)"
                      tickLine={false}
                      axisLine={false}
                      tick={{ fill: 'rgba(255,255,255,0.6)', fontSize: 10, fontFamily: '"IBM Plex Mono", ui-monospace, monospace' }}
                    />
                    <YAxis
                      stroke="rgba(255,255,255,0.25)"
                      tickLine={false}
                      axisLine={false}
                      width={32}
                      tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10, fontFamily: '"IBM Plex Mono", ui-monospace, monospace' }}
                    />
                    <Tooltip contentStyle={CHART_STYLES.tooltip.contentStyle} itemStyle={CHART_STYLES.tooltip.itemStyle} labelStyle={CHART_STYLES.tooltip.labelStyle} cursor={CHART_STYLES.tooltip.cursor} />
                    <Line
                      type="monotone"
                      dataKey="events"
                      stroke={CHANNEL_HEX.calendar}
                      strokeWidth={2}
                      dot={{ fill: CHANNEL_HEX.calendar, r: 2 }}
                      activeDot={{ r: 4 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Surface>
          </section>
        </FadeIn>

        {/* 2. Distribution + Histogram (side-by-side) */}
        <FadeIn delay={0.22}>
          <section className="mb-12 grid grid-cols-1 gap-6 lg:grid-cols-2" aria-labelledby="calendar-mix">
            <Surface className="flex h-full flex-col">
              <h2 id="calendar-mix" className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
                Category distribution
              </h2>
              <ChannelPie channel="calendar" data={data.categories} topN={5} />
            </Surface>

            <Surface className="flex h-full flex-col">
              <h2 className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">By weekday</h2>
              <ChannelHistogram
                channel="calendar"
                bins={data.weekdayBreakdown.map((d) => ({ label: d.day, value: d.events }))}
                unitLabel="Events"
                highlightLabel={data.kpis.busiestDay}
              />
            </Surface>
          </section>
        </FadeIn>

        {/* 4. Heatmap — full year */}
        <FadeIn delay={0.25}>
          <section className="mb-12" aria-labelledby="calendar-heatmap">
            <Surface>
              <h2 id="calendar-heatmap" className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
                Activity · last 12 months
              </h2>
              <CalendarHeatmap channel="calendar" data={heatmapData} weeks={53} unitLabel="events" />
            </Surface>
          </section>
        </FadeIn>

        {/* 5. Coming events */}
        <FadeIn delay={0.3}>
          <section aria-labelledby="calendar-upcoming">
            <Surface>
              <h2 id="calendar-upcoming" className="mb-6 font-mono text-xs uppercase tracking-wider text-signal-white/60">
                Coming up
              </h2>
              <ul className="-mx-6 -mb-6">
                {data.upcomingEvents.map((e, i) => (
                  <li
                    key={i}
                    className="flex items-center gap-4 border-t border-signal-white/5 px-6 py-3 transition-colors duration-150 ease-snap hover:bg-signal-white/[0.03]"
                  >
                    <span
                      className="block size-2 rounded-sm"
                      style={{ backgroundColor: colorForCategory(e.category) }}
                      aria-hidden="true"
                    />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">{e.title}</div>
                      <div className="font-mono text-[10px] uppercase tracking-wider text-signal-white/50">{e.category}</div>
                    </div>
                    <div className="text-right font-mono text-xs">
                      <div className="text-signal-white/70">{e.relativeTime}</div>
                      <div className="font-mono text-[10px] text-signal-white/50">{e.durationMinutes} min</div>
                    </div>
                  </li>
                ))}
              </ul>
            </Surface>
          </section>
        </FadeIn>
      </div>
    </main>
  );
}

function toNum(v: number | string | undefined | null): number | null {
  if (v === null || v === undefined) return null;
  if (typeof v === 'number') return Number.isFinite(v) ? v : null;
  const n = parseFloat(String(v));
  return Number.isFinite(n) ? n : null;
}
