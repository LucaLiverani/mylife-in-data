---
description: Audit warehouse/dbt/dashboard/docs for consistency drift
allowed-tools: Bash, Read, Grep, Glob, Agent
---

Run a consistency audit of this data platform and produce a findings report. Do NOT fix
anything. Use parallel Explore/general-purpose agents where it speeds things up. For each
check below, report "OK" or the specific issues with file:line evidence.

1. **Orphaned dbt models.** Every model in `transformations/models/gold/*.sql` should be
   queried by a `dashboard/functions/api/**` endpoint OR `ref()`'d by another model. List
   gold models that are neither. Do the reachability check for silver too (each silver
   model should feed a gold model, the `silver_events_unified` chain, or a Dagster asset).

2. **Sources vs reality.** Every `source()` in `transformations/models/sources.yml` should
   map to a real bronze table created in `warehouse/ddl/*.sql`. Flag declared sources with
   no table, and bronze tables read by models but not declared.

3. **Docs vs code.** Spot-check `docs/DATA_MODEL.md`'s source-inventory table and its
   gold→endpoint mapping against the actual models, DDL, and `dashboard/functions/api/**`.
   Flag claims that no longer hold (a table/topic that doesn't exist, an endpoint reading a
   different gold table, etc.).

4. **Mock parity.** Each `dashboard/public/mocks/*.json` should match the columns the
   corresponding gold model/endpoint returns. Flag obvious shape mismatches.

5. **Architecture invariants** (see CLAUDE.md). Confirm nothing describes Redpanda as a
   general ingestion layer (it streams only `spotify.player.current`), and that no Timeline
   path has reappeared (`bronze.maps_visits/path/search/directions`, `import_maps_timeline_export`,
   `probe_maps_data_portability`).

6. **Optional, live (read-only).** If asked, check the VM for orphaned `gold`/`silver`
   views not backed by a dbt model or DDL view (the prune target) and report counts only.

End with a short prioritized list of what to fix, if anything.
