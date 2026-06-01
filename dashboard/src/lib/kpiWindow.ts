// The shared start date that every KPI card + chart is floored to in the
// warehouse. This is ONLY the human-facing label — the actual filtering happens
// in ClickHouse. It MUST stay in sync with the dbt var `kpi_start_date` in
// transformations/dbt_project.yml; change both together if you move the window.
export const KPI_START_DATE = '2025-01-01';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const [year, month] = KPI_START_DATE.split('-').map(Number);

// e.g. "since Jan 2025" — derived so there's a single value to edit.
export const KPI_SINCE_LABEL = `since ${MONTHS[month - 1]} ${year}`;
