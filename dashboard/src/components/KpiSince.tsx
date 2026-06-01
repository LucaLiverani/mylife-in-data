import { KPI_SINCE_LABEL } from '@/lib/kpiWindow';

/**
 * Subtle caption appended to a KPI / "Overview" section header so the shared
 * start date (kpi_start_date in the warehouse) is visible — all KPI cards and
 * charts span the same window, this says which. Inherits the header's uppercase
 * mono styling, rendered dimmer than the heading itself.
 */
export function KpiSince() {
  return <span className="font-normal text-signal-white/35"> · {KPI_SINCE_LABEL}</span>;
}
