/**
 * GET /api/google/calendar
 *
 * Aggregates seven Calendar gold tables into the single JSON shape the
 * dashboard's mock expects. ClickHouse round-trips run in parallel.
 */

import { queryClickHouse } from '../../_shared/clickhouse';
import { queryWithFallback, addCacheHeaders } from '../../_shared/fallback';
import type { Env } from '../../_shared/types';

interface CalendarKPIs {
  plansCount: number;
  freeDays: number;
  totalEvents: number;
  meetingHours: number;
  avgDaily: number;
  busiestDay: string;
}

interface BusyHour { hour: string; events: number }
interface Category { name: string; value: number; percentage: number }
interface WeekdayItem { day: string; events: number }
interface DailyItem { date: string; events: number }
interface WeekGridItem { day: number; hour: number; intensity: number }
interface UpcomingItem {
  title: string;
  category: string;
  time: string;
  durationMinutes: number;
}

export async function onRequest(context: { env: Env; request: Request }): Promise<Response> {
  const { env, request } = context;

  const { data, isFromCache, error } = await queryWithFallback<any>(
    async () => {
      const [kpisRes, busyHours, categories, weekdayBreakdown, dailyEvents, weekGrid, upcomingEvents] =
        await Promise.all([
          queryClickHouse<CalendarKPIs>(env, `SELECT * FROM gold.gold_calendar_kpis LIMIT 1`),
          queryClickHouse<BusyHour>(env, `SELECT * FROM gold.gold_calendar_busy_hours ORDER BY hour`),
          queryClickHouse<Category>(env, `SELECT * FROM gold.gold_calendar_categories`),
          queryClickHouse<WeekdayItem>(env, `SELECT * FROM gold.gold_calendar_weekday_breakdown`),
          queryClickHouse<DailyItem>(env, `SELECT * FROM gold.gold_calendar_daily_events`),
          queryClickHouse<WeekGridItem>(env, `SELECT * FROM gold.gold_calendar_week_grid`),
          queryClickHouse<UpcomingItem>(env, `SELECT * FROM gold.gold_calendar_upcoming_events`),
        ]);

      const kpis = kpisRes[0] || ({} as Partial<CalendarKPIs>);
      return {
        kpis,
        busyHours: busyHours.map(h => ({ hour: h.hour, events: Number(h.events) || 0 })),
        categories: categories.map(c => ({ name: c.name, value: Number(c.value) || 0, percentage: Number(c.percentage) || 0 })),
        weekdayBreakdown: weekdayBreakdown.map(w => ({ day: w.day, events: Number(w.events) || 0 })),
        dailyEvents: dailyEvents.map(d => ({ date: d.date, events: Number(d.events) || 0 })),
        weekGrid: weekGrid.map(w => ({ day: Number(w.day), hour: Number(w.hour), intensity: Number(w.intensity) || 0 })),
        upcomingEvents: upcomingEvents.map(u => ({
          title: u.title,
          category: u.category,
          time: u.time,
          durationMinutes: Number(u.durationMinutes) || 0,
        })),
      };
    },
    'google/calendar',
    request,
    {
      kpis: {},
      busyHours: [],
      categories: [],
      weekdayBreakdown: [],
      dailyEvents: [],
      weekGrid: [],
      upcomingEvents: [],
    }
  );

  const { body, headers } = addCacheHeaders(data, isFromCache, error);
  return Response.json(body, { headers });
}
