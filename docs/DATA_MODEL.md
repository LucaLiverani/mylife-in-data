# Data Model

The contract between pipelines and the dashboard. Every `gold.*` table here is
referenced by at least one Pages Function in `dashboard/functions/api/`, so
shape and naming are fixed — pipelines must match these, not the other way
round. Mocks in `dashboard/public/mocks/` are the visible source of truth for
field semantics.

## Layered shape

```
bronze.*    raw, append-only events from producers + parsers
              ↓ MV / dbt
silver.*    cleaned, deduped, entity-joined; one row per logical event
              ↓ MV
silver.events_unified    cross-source UNION ALL in a common schema
              ↓ MV
gold.*      dashboard-facing, pre-aggregated with AggregatingMergeTree
              ↓ direct query
dashboard   Pages Function → SELECT * FROM gold.<table>
```

Three databases in ClickHouse: `bronze`, `silver`, `gold`. The dashboard only
reads from `gold`; bronze and silver are internal.

Every silver→gold aggregate is an MV onto an `AggregatingMergeTree`/
`SummingMergeTree` storage table. New events propagate end-to-end without
batch jobs — KPIs are live by construction.

## Sources and their endpoint inventory

| Source | Bronze table(s) | Refresh | Ingest path |
|---|---|---|---|
| **Spotify currently-playing** | `bronze.spotify_player_current` | 5–10s | producer container (`spotify-current-producer`) → Redpanda topic `spotify.player.current` → ClickHouse Kafka engine. **The only streamed source** — everything below is a direct batch INSERT |
| **Spotify recently-played** | `bronze.spotify_plays_raw` | 60s | Dagster `@schedule`, direct INSERT, dedupe on `played_at` |
| **Spotify entity catalogs** | `bronze.spotify_tracks`, `bronze.spotify_artists` | enrichment | Dagster sensor on unknown IDs in bronze, direct INSERT |
| **Spotify saved tracks** | `bronze.spotify_saved_tracks` | 5 min | Dagster `@schedule` polls `me/tracks`; dedup on `added_at`. Powers the "Liked" rows in `/api/now/timeline` |
| **YouTube history** | `bronze.youtube_watch_history`, `bronze.youtube_search_history` | daily | Dagster schedule → Google **Data Portability** (Takeout-equivalent payload) |
| **YouTube metadata** | `bronze.youtube_videos`, `bronze.youtube_channels` | enrichment | Dagster sensor on unknown `video_id` in bronze → **YouTube Data API v3** (`videos?id=…&part=snippet,contentDetails`, `channels?id=…&part=snippet`), batched 50 IDs per call |
| **Maps** | `bronze.maps_visits`, `bronze.maps_path`, `bronze.maps_search` | daily | Same Data Portability flow, different resource scopes — shares the Google OAuth app with YouTube |
| **Calendar** | `bronze.calendar_events`, `bronze.calendar_sync_notifications` | event-driven (push) | **Google Calendar API + `events.watch` push notifications**: Pages Function webhook → ClickHouse sync queue → Dagster sensor pulls deltas via `events.list?syncToken=…`. Multi-calendar import, `calendar_name` is the category. Fallback: 60s incremental polling |

### Google Data Portability API — shared ingest path for YouTube + Maps

A single Google Cloud Console app, OAuth-authenticated once, covers both
YouTube and Maps (and Calendar if we choose). Scopes are namespaced per
resource:
`dataportability.youtube.activity`, `dataportability.youtube.searches`,
`dataportability.maps.starred_places`, etc.

Per-tick flow inside a Dagster schedule:

1. `archives.initiate` with the chosen resource list → returns a job ID.
2. Poll `archiveJobs.getPortabilityArchiveState` until status `COMPLETE`
   (minutes for incremental, longer for an initial backfill).
3. GET each signed URL → unpack the archive (zip of JSON files, same layout
   as Google Takeout — parsers are interchangeable).
4. INSERT into bronze; `ReplacingMergeTree(_ingested_at)` collapses any
   overlap across runs.

The schema doesn't care which export path the data came from — switching
between Takeout (manual) and Data Portability (programmatic) is purely an
ingest concern.

**Apps can stay in "testing" mode** in Google Cloud Console for self-only
use, same as the Spotify pattern (no Google brand verification needed for
one test user — yourself).

**Caveat (Maps Timeline)**: Google migrated Maps location history to
on-device storage in late 2024 / early 2025. Pre-migration data is still
exportable; new visits may only live on your phone unless you've enabled
encrypted cloud backup. Worth a probe call before depending on this path —
fallback is the on-device "Export Timeline" feature (manual, periodic).

### Backfill window

**Initial pull: 1 year** for every API-based source — Spotify
`recently-played`, YouTube Data Portability, Maps Data Portability,
Calendar via `events.list`. Long enough that "new places this year" and
year-over-year comparisons mean something on day one, short enough that
initial archive jobs finish in minutes-to-hours rather than days.

**Deeper history is a separate, one-shot manual operation, run only
after live pipelines are stable** — that ordering guarantees no data is
missed on the cutover. The same Dagster parser assets handle:
- Spotify "Account Privacy → Request data" (Extended Streaming History,
  full account lifetime),
- Google Takeout zips,
- on-device Maps Timeline exports.

Replay-ability is handled at the warehouse layer, not per producer: the
nightly `warehouse_r2_archive` Dagster job snapshots every bronze table plus
the non-derivable silver state tables to R2 as Parquet
(`archive/warehouse/dt=YYYY-MM-DD/<database>.<table>.parquet` plus a
`_MANIFEST.json` written last to mark the snapshot complete), and
`scripts/restore_warehouse_from_r2.py` INSERTs a snapshot back (idempotent,
since every archived table is ReplacingMergeTree on a natural key). See
OPERATIONS.md, "Warehouse cold archive (R2)", for coverage and the runbook.

---

## Bronze tables

### Spotify

```sql
-- Every poll of /me/player/currently-playing. ReplacingMergeTree by track_id
-- so reruns over the same minute collapse to one row.
CREATE TABLE bronze.spotify_player_current (
    captured_at        DateTime64(3),
    track_id           String,
    track_name         String,
    track_uri          String,
    track_duration_ms  Int32,
    progress_ms        Int32,
    is_playing         Bool,
    album_id           String,
    album_name         String,
    album_uri          String,
    album_images       Array(String),         -- URLs, largest-first
    artists_ids        Array(String),
    artists_names      Array(String),
    device_id          String,
    device_name        String,
    device_type        LowCardinality(String),
    device_volume_percent Int32,
    context_type       LowCardinality(String),  -- '', 'playlist', 'album', 'artist'
    context_uri        String,
    _ingested_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (track_id, captured_at);

-- Plays from /me/player/recently-played. Deduped on (track_id, played_at).
CREATE TABLE bronze.spotify_plays_raw (
    played_at          DateTime64(3),       -- Spotify's authoritative timestamp
    track_id           String,
    track_uri          String,
    artists_ids        Array(String),       -- usually 1, can be N for collabs
    duration_ms        Int32,               -- track's own duration; we have no "amount listened"
    context_type       LowCardinality(String),
    context_uri        String,
    _ingested_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (track_id, played_at);

-- Track metadata catalog, populated lazily by the enricher.
CREATE TABLE bronze.spotify_tracks (
    track_id           String,
    track_name         String,
    track_uri          String,
    duration_ms        Int32,
    explicit           Bool,
    popularity         Int32,
    isrc               String,
    album_id           String,
    album_name         String,
    album_uri          String,
    album_images       Array(String),
    album_release_date Date,
    artists_ids        Array(String),       -- preserved here for join-back
    _fetched_at        DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_fetched_at)
ORDER BY track_id;

-- Artist metadata catalog. genres is critical — it powers /api/spotify/data
-- top-artists `genre` field and the genres breakdown chart.
CREATE TABLE bronze.spotify_artists (
    artist_id          String,
    artist_name        String,
    artist_uri         String,
    genres             Array(LowCardinality(String)),
    popularity         Int32,
    followers          Int32,
    image_url          String,
    _fetched_at        DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_fetched_at)
ORDER BY artist_id;

-- Saved tracks ("Liked") — polled from /me/tracks every ~5 min. The
-- added_at timestamp is the user's like-event; dedup on (track_id,
-- added_at) so re-polls don't duplicate. Projects into events_unified
-- as kind='liked' for the now/timeline feed.
CREATE TABLE bronze.spotify_saved_tracks (
    added_at           DateTime64(3),
    track_id           String,
    track_uri          String,
    _ingested_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (track_id, added_at);
```

Stream path: only `spotify.player.current` is a Redpanda topic. It has a
matching ClickHouse Kafka-engine consumer table
(`bronze.kafka_spotify_player_current`) and a 1:1 MV that pumps each row into
`bronze.spotify_player_current`. Everything else on this page, including
`spotify_plays_raw` and the tracks/artists catalogs, is a plain batch INSERT
from Dagster (recently-played, saved tracks, enrichment) or the one-time
history import. These are low-volume API responses with natural dedup keys:
Kafka would be overkill, and the `ReplacingMergeTree` UPSERT semantics are
exactly what we want.

### YouTube (Data Portability for history + Data API v3 for metadata)

```sql
CREATE TABLE bronze.youtube_watch_history (
    watched_at         DateTime64(3),
    video_id           String,
    video_title        String,
    video_url          String,
    channel_id         String,                 -- often empty (Takeout omits it)
    channel_title      String,                 -- often empty
    activity_type      LowCardinality(String), -- 'watched' (only value in YouTube history export)
    is_from_ads        Bool,                   -- from `fromYoutubeMusic`/`details`
    _ingested_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (video_id, watched_at);

CREATE TABLE bronze.youtube_search_history (
    searched_at        DateTime64(3),
    query              String,
    _ingested_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (searched_at, query);

-- v3 enricher: populated by a Dagster sensor on unknown video_id in
-- bronze.youtube_watch_history. 50 IDs/call to videos?part=snippet,
-- contentDetails. Tracks the channel_id + category_id + duration so
-- silver/gold tiles can resolve them without bronze having to know.
CREATE TABLE bronze.youtube_videos (
    video_id           String,
    video_title        String,
    channel_id         String,
    category_id        String,
    duration_seconds   Int32,                  -- ISO8601 PT#H#M#S parsed on ingest
    published_at       DateTime,
    default_language   LowCardinality(String),
    _fetched_at        DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_fetched_at)
ORDER BY video_id;

-- Channel metadata catalog. primary_category_name derived from a static
-- mapping of YouTube category IDs → names (videoCategories.list, fetched
-- once and cached). Subscriber count kept for context, not surfaced today.
CREATE TABLE bronze.youtube_channels (
    channel_id              String,
    channel_title           String,
    primary_category_name   LowCardinality(String),
    subscriber_count        Int32,
    thumbnail_url           String,
    _fetched_at             DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_fetched_at)
ORDER BY channel_id;
```

**Hybrid ingest, committed**: Data Portability for the raw history rows
(`bronze.youtube_watch_history`, `bronze.youtube_search_history`);
YouTube Data API v3 as a `video_id → channel/category/duration` enricher
that populates `bronze.youtube_videos` + `bronze.youtube_channels`. A
Dagster sensor watches for unknown `video_id`s in bronze and batches them
50/call against the v3 endpoints.

**Watch time stays an explicit proxy** — Google doesn't track partial-watch
duration anywhere. Gold views compute `watch_time ≈ count ×
videos.duration_seconds`, assuming a full watch. SQL view comments on
every `gold.gold_youtube_*` view that uses this should call it out so
future readers don't trust the number past what it is. (Dashboard can
add a tooltip if desired — frontend concern.)

### Maps (Data Portability API)

```sql
CREATE TABLE bronze.maps_visits (
    started_at         DateTime64(3),
    ended_at           DateTime64(3),
    place_name         String,
    place_id           String,                 -- Google Places ID when present
    place_address      String,                 -- formatted address from Timeline (usually "City, Country")
    lat                Float64,
    lng                Float64,
    confidence         Float32,                -- 0–1, from Timeline JSON
    _ingested_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (started_at, place_id);

CREATE TABLE bronze.maps_path (
    started_at         DateTime64(3),
    ended_at           DateTime64(3),
    start_lat          Float64,
    start_lng          Float64,
    end_lat            Float64,
    end_lng            Float64,
    distance_m         Int32,
    activity_type      LowCardinality(String), -- 'walking', 'driving', etc.
    _ingested_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (started_at);

CREATE TABLE bronze.maps_search (
    searched_at        DateTime64(3),
    query              String,
    _ingested_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (searched_at);

CREATE TABLE bronze.maps_directions (
    requested_at       DateTime64(3),
    origin             String,
    destination        String,
    _ingested_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (requested_at);
```

### Calendar (Google Calendar API + push notifications)

```sql
CREATE TABLE bronze.calendar_events (
    event_id           String,                 -- stable across edits (Google's event id)
    calendar_id        String,                 -- which calendar this event came from
    calendar_name      String,                 -- denormalized once at ingest; doubles as the "category"
    started_at         DateTime64(3),
    ended_at           DateTime64(3),
    title              String,
    description        String,
    location           String,
    status             LowCardinality(String), -- 'confirmed','tentative','cancelled'
    attendee_count     Int16,
    recurrence_id      String,                 -- empty for non-recurring; group key for series
    _ingested_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (event_id, started_at);

-- Push notifications from Google land here via the Pages Function
-- webhook. A Dagster sensor processes unprocessed rows by calling
-- events.list?syncToken=… for the affected calendar and INSERTing the
-- delta into bronze.calendar_events.
CREATE TABLE bronze.calendar_sync_notifications (
    received_at        DateTime64(3),
    channel_id         String,                 -- our channel ID from events.watch
    resource_id        String,                 -- Google's resource ID for the watched calendar
    calendar_id        String,                 -- resolved from channel_id
    message_number     UInt64,                 -- monotonic per channel
    processed_at       Nullable(DateTime64(3)),
    _ingested_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (channel_id, message_number);
```

Multi-calendar import + `calendar_name` as the category means we never
need NLP on event titles to assign categories. Optional
`silver.calendar_category_aliases(calendar_name → display_category)`
lookup for pretty-printing (e.g., raw email-prefix calendar names →
"Personal" / "Work").

---

## Silver tables

Silver does three things: dedupes, joins entity catalogs, derives convenience
fields. One row per logical event.

```sql
-- One row per play, fully denormalized so downstream gold tables don't need
-- to JOIN.
CREATE MATERIALIZED VIEW silver.mv_spotify_plays
TO silver.spotify_plays AS
SELECT
    p.played_at                                                   AS played_at,
    p.track_id                                                    AS track_id,
    coalesce(t.track_name, '')                                    AS track_name,
    p.duration_ms                                                 AS duration_ms,
    p.artists_ids[1]                                              AS primary_artist_id,
    coalesce(arrayElement(a.artist_names, 1), '')                 AS primary_artist_name,
    a.all_genres                                                  AS genres,
    coalesce(t.album_name, '')                                    AS album_name,
    arrayElement(coalesce(t.album_images, []), 1)                 AS album_art_url,
    p.context_type                                                AS context_type,
    p.context_uri                                                 AS context_uri
FROM bronze.spotify_plays_raw p
LEFT JOIN bronze.spotify_tracks t USING (track_id)
LEFT JOIN (
    SELECT
        artists_ids[1] AS first_artist_id,
        groupArray(artist_name) AS artist_names,
        arrayDistinct(arrayFlatten(groupArray(genres))) AS all_genres
    FROM bronze.spotify_artists
    GROUP BY first_artist_id
) a ON a.first_artist_id = p.artists_ids[1];

-- silver.spotify_current — the most recent poll, fully resolved.
CREATE VIEW silver.spotify_current AS
SELECT argMax(c, captured_at) FROM bronze.spotify_player_current FINAL;
```

(YouTube, Maps, Calendar each get a matching `silver.<source>_<entity>` MV
that does the equivalent cleanup. Schemas mirror bronze with derived columns
added — `is_weekend`, `day_name`, `time_of_day` typically live here, not in
gold. Relative-time labels are NOT computed in SQL: gold emits ISO-8601 UTC
timestamps and the dashboard renders "4m ago" client-side, so labels stay
fresh between dbt builds.)

### The cross-source merge — `silver.events_unified`

This is the seam where Spotify plays, YouTube watches, Maps visits, and
Calendar meetings cross. Six MVs (one per source × event-kind) project into
this single shape, which feeds both `home/recent-events` and `overview/stats`.

```sql
CREATE TABLE silver.events_unified (
    event_ts          DateTime64(3),
    source            LowCardinality(String),  -- 'spotify','youtube','maps','calendar'
    kind              LowCardinality(String),  -- e.g. 'play','watch','place_visit','meeting'
    title             String,                  -- primary label (track name / video title / place name / meeting title)
    subtitle          String,                  -- secondary (artist name / relative time / visit type / duration label)
    image_url         String,                  -- album art / video thumb / blank
    is_from_ads       UInt8,                   -- youtube-specific flag, 0 elsewhere
    metadata          String,                  -- JSON catch-all (time_of_day, activity_type, context, etc.)
    event_id          UUID                     -- stable per logical event for dedup
) ENGINE = MergeTree
ORDER BY (event_ts, source, event_id);
```

Per-source projection example (Spotify plays):

```sql
CREATE MATERIALIZED VIEW silver.mv_events_unified_spotify
TO silver.events_unified AS
SELECT
    played_at                                          AS event_ts,
    'spotify'                                          AS source,
    'play'                                             AS kind,
    track_name                                         AS title,
    primary_artist_name                                AS subtitle,
    album_art_url                                      AS image_url,
    0                                                  AS is_from_ads,
    toJSONString(map(
        'context_type', context_type,
        'duration_ms', toString(duration_ms),
        'genres', toString(genres)
    ))                                                 AS metadata,
    generateUUIDv4()                                   AS event_id
FROM silver.spotify_plays;
```

Equivalent MVs for `silver.youtube_watches` → events_unified (kind='watch'),
`silver.maps_visits` → events_unified (kind='place_visit'), and
`silver.calendar_events` → events_unified (kind='meeting').

Optional state-transition events for the "now/timeline" mock (Track started,
Track ended, Liked, Skipped, Playlist queued, Album opened) are derived in
a `silver.spotify_state_events` MV by lagging over `bronze.spotify_player_current`
with `neighbor()` — these also project into `events_unified` so the timeline
feed and home feed share the same source table.

### Maps — home anchor + trip segmentation

Several Maps KPIs (`days_away_from_home`, `longest_trip_days`, the trips
list, `new_places_this_year`) are derived from raw visits + a **home
anchor**. Without an explicit home, those values can't be computed — and
inferring home as "most-dwelt place" misclassifies things like a multi-week
vacation. Make it explicit.

```sql
-- Configured home anchor. One active row at any point in time; multi-row
-- history if you move (valid_from gives a piecewise lookup).
CREATE TABLE silver.maps_home_locations (
    valid_from   Date,
    lat          Float64,
    lng          Float64,
    radius_km    Float32,            -- visits within this distance = "at home"
    label        String,             -- 'Home', 'Zurich apt', etc.
    _set_at      DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_set_at)
ORDER BY valid_from;

-- Helper: which home was active at a given date (piecewise from valid_from).
CREATE VIEW silver.home_at AS
SELECT
    valid_from,
    lead(valid_from, 1, toDate('2100-01-01'))
        OVER (ORDER BY valid_from)                  AS valid_until,
    lat, lng, radius_km, label
FROM silver.maps_home_locations FINAL;

-- One row per trip. Materialized so gold tables hit an indexed table
-- rather than re-segmenting on every query.
CREATE TABLE silver.maps_trips (
    started_at           Date,
    ended_at             Date,
    days                 Int16,
    destination          String,            -- most-dwelt place in the window
    destination_country  String,            -- parsed from place_address
    km                   Int32              -- sum of overlapping path distances
) ENGINE = MergeTree
ORDER BY started_at;
```

**Segmentation algorithm** (Dagster asset, re-runs after each Maps ingest):

1. For each `bronze.maps_visits` row, compute haversine distance to the
   `silver.home_at` row whose `[valid_from, valid_until)` contains the visit.
2. Mark visits **away** if `distance_km > home.radius_km`.
3. Group consecutive away-visits into trip clusters; break the chain when
   either a visit falls inside the home radius **or** there's a gap > 24h
   between consecutive away-visits.
4. Per cluster: `min(started_at)` → trip start, `max(ended_at)` → trip end,
   `argMax(place_name, dwell_time)` → destination, parse country from
   `place_address`, sum `bronze.maps_path.distance_m` overlapping the
   window → `km`. INSERT into `silver.maps_trips`.

Why a Dagster asset rather than a streaming MV: trip boundaries can shift
retroactively when late-arriving visits land in bronze (you import a
Timeline export covering a gap and a 2-day trip becomes a 9-day trip).
A batch recompute is correct; a stream MV would lock in stale boundaries.
The job is fast — single-digit seconds at personal-history scale.

**Gold dependencies on this silver layer:**

| Dashboard field | Computed from |
|---|---|
| `kilometers_traveled` | `sum(bronze.maps_path.distance_m) / 1000` (no home anchor needed) |
| `new_places_this_year` | window over `bronze.maps_visits.place_id`, first appearance in current year (no home anchor needed) |
| `cities_visited`, `countries_visited` | parse from `bronze.maps_visits.place_address` |
| `days_away_from_home` | `count(DISTINCT date)` exploded from `silver.maps_trips` ranges |
| `longest_trip_days` | `max(days)` over `silver.maps_trips` |
| `trips[]` (mock-only today) | `gold.gold_maps_trips` → `SELECT * FROM silver.maps_trips` |

---

## Gold tables — one per dashboard tile

Each row below corresponds to a `SELECT * FROM gold.<table>` issued by a
Pages Function. Column names match what the TS handlers destructure.

### `/api/spotify/current` → `gold.gold_spotify_current_track`

One row, latest currently-playing.

```sql
CREATE VIEW gold.gold_spotify_current_track AS
SELECT
    captured_at         AS captured_at,
    track_id, track_name, track_uri,
    album_id, album_name, album_uri, album_images,
    artists_ids[1]      AS artist_id,
    arrayElement(artists_names, 1) AS artist_name,
    concat('spotify:artist:', artists_ids[1]) AS artist_uri,
    artists_ids         AS artists_ids,
    artists_names       AS artists_names,
    is_playing, progress_ms, track_duration_ms,
    device_id, device_name, device_type, device_volume_percent,
    context_type, context_uri
FROM bronze.spotify_player_current FINAL
ORDER BY captured_at DESC
LIMIT 1;
```

### `/api/spotify/recent` → `gold.gold_spotify_recent_tracks`

Last 50 plays. The handler maps `played_at`→`time`; the dashboard renders
the relative label ("4m ago") client-side from it.

```sql
CREATE VIEW gold.gold_spotify_recent_tracks AS
SELECT
    track, artist,
    formatDateTime(played_at_raw, '%Y-%m-%dT%H:%i:%SZ', 'UTC') AS played_at,
    album_art
FROM (
    SELECT track_name AS track, primary_artist_name AS artist,
           played_at AS played_at_raw, album_art_url AS album_art
    FROM silver.spotify_plays
    ORDER BY played_at_raw DESC          -- window picked on the raw DateTime
    LIMIT 50
)
ORDER BY played_at DESC;
```

### `/api/spotify/summary` → `gold.gold_spotify_kpis_summary`

One row. Powers the home-page Spotify card.

```sql
CREATE MATERIALIZED VIEW gold.mv_spotify_kpis_summary
TO gold.spotify_kpis_summary_state AS
SELECT
    countState(DISTINCT primary_artist_id)               AS artists,
    countState(DISTINCT track_id)                        AS songs,
    sumState(duration_ms)                                AS total_duration_ms
FROM silver.spotify_plays;

CREATE VIEW gold.gold_spotify_kpis_summary AS
SELECT
    uniqMerge(artists)                                   AS artists,
    uniqMerge(songs)                                     AS songs,
    concat(toString(round(sumMerge(total_duration_ms) / 3600000.0, 1)), ' hrs') AS total_hours
FROM gold.spotify_kpis_summary_state;
```

### `/api/spotify/data` → four gold tables

The handler runs four parallel queries:

```sql
-- KPI row
CREATE VIEW gold.gold_spotify_kpis_dashboard AS
SELECT
    concat(toString(round(sumMerge(total_duration_ms) / 3600000.0, 1)), ' hrs') AS total_time,
    uniqMerge(songs)                                                            AS songs_streamed,
    uniqMerge(artists)                                                          AS unique_artists,
    concat(toString(round(sumMerge(total_duration_ms) / 3600000.0 / countMerge(active_days), 1)), ' hrs') AS avg_daily
FROM gold.spotify_kpis_summary_state;  -- same state table as above, extra columns

-- Top artists with 30-day trend
CREATE VIEW gold.gold_spotify_top_artists AS
SELECT
    row_number() OVER (ORDER BY plays DESC)                       AS rank,
    primary_artist_name                                            AS name,
    count()                                                        AS plays,
    round(sum(duration_ms) / 3600000.0, 1)                         AS hours,
    arrayElement(genres, 1)                                        AS genre,
    arrayMap(d -> coalesce(daily_plays[d], 0),
             arrayMap(i -> today() - 29 + i, range(30)))           AS trend
FROM silver.spotify_plays
ARRAY JOIN ...   -- 30-day per-day plays per artist
GROUP BY primary_artist_name, genres
ORDER BY plays DESC
LIMIT 15;

-- Genre breakdown
CREATE VIEW gold.gold_spotify_genres AS
SELECT
    genre              AS name,
    count()            AS value
FROM silver.spotify_plays
ARRAY JOIN genres AS genre
GROUP BY genre
ORDER BY value DESC
LIMIT 20;

-- Daily listening hours, last 90 days
CREATE VIEW gold.gold_spotify_daily_listening AS
SELECT
    toDate(played_at)                            AS date,
    round(sum(duration_ms) / 3600000.0, 1)       AS hours
FROM silver.spotify_plays
WHERE played_at >= today() - 90
GROUP BY date
ORDER BY date;
```

### `/api/youtube/data` → six gold tables

```
gold.gold_youtube_kpis_with_watch_time_dashboard       -- 1 row of KPIs
gold.gold_youtube_top_channels_dashboard               -- top N channels by watch time
gold.gold_youtube_category_breakdown_dashboard         -- by primary_category
gold.gold_youtube_daily_watch_time_breakdown_dashboard -- per-day breakdown w/ weekend flag
gold.gold_youtube_recent_videos_dashboard              -- last 10
gold.gold_youtube_hourly_activity_dashboard            -- hour-of-day histogram
```

Column lists are exactly the TS handler's `interface` definitions in
`functions/api/youtube/data.ts` — bronze `watch_count` proxies for
watch time (Takeout limitation).

### `/api/travel/data` → six (+1) gold tables

```
gold.gold_maps_kpis_dashboard
gold.gold_maps_locations_dashboard
gold.gold_maps_hourly_activity_dashboard
gold.gold_maps_recent_activities
gold.gold_maps_daily_activity_dashboard
gold.gold_maps_destinations_dashboard
gold.gold_maps_trips                      -- new; not yet queried by travel/data.ts but the mock's `trips[]` already expects it
```

KPI columns from `functions/api/travel/data.ts:10-26`. The
`dwell_time_category` and `distance_to_next_km` columns on
`gold_maps_locations_dashboard`, plus the trip-aware KPIs
(`days_away_from_home`, `longest_trip_days`) and the `trips[]` array,
all depend on the **Maps — home anchor + trip segmentation** silver
subsection above. `gold.gold_maps_trips` is a thin `SELECT * FROM
silver.maps_trips ORDER BY started_at DESC` once that exists; the handler
needs a follow-up to surface it.

### `/api/overview/stats` → two gold tables

```sql
-- One row, cross-source totals for the home page.
CREATE VIEW gold.gold_home_overview_stats AS
SELECT
    (SELECT uniqMerge(songs) FROM gold.spotify_kpis_summary_state)         AS songsStreamed,
    (SELECT uniqMerge(artists) FROM gold.spotify_kpis_summary_state)       AS artistsListened,
    (SELECT count() FROM silver.youtube_watches)                           AS videosWatched,
    (SELECT count(DISTINCT channel_id) FROM silver.youtube_watches WHERE channel_id != '') AS youtubeChannels,
    (SELECT count() FROM bronze.youtube_search_history) + (SELECT count() FROM bronze.maps_search) AS searchQueries,
    (SELECT count(DISTINCT place_name) FROM bronze.maps_visits)            AS citiesVisited;

-- Per-day event counts across sources, last 90 days.
CREATE VIEW gold.gold_home_daily_data_generation AS
SELECT
    toDate(event_ts)                                                   AS date,
    countIf(source = 'spotify')                                        AS spotify,
    countIf(source = 'youtube')                                        AS youtube,
    countIf(source = 'calendar')                                       AS google,   -- handler names it `google`
    countIf(source = 'maps')                                           AS maps
FROM silver.events_unified
WHERE event_ts >= today() - 90
GROUP BY date
ORDER BY date;
```

### `/api/home/recent-events` → `gold.gold_home_recent_events`

The query: `SELECT * FROM gold.gold_home_recent_events ORDER BY source, recency_rank`.

```sql
CREATE VIEW gold.gold_home_recent_events AS
SELECT
    source                                                                   AS source,
    row_number() OVER (PARTITION BY source ORDER BY event_ts DESC)           AS recency_rank,
    title,
    multiIf(
        source = 'spotify',  subtitle,                                  -- artist name
        source = 'maps',     kind,                                      -- "place_visit"
        ''
    )                                                                        AS subtitle,
    formatDateTime(event_ts, '%Y-%m-%dT%H:%i:%SZ', 'UTC')                    AS time,
    image_url,
    kind                                                                     AS activity_type,
    is_from_ads
FROM silver.events_unified
QUALIFY recency_rank <= 10;
```

Relative labels ("18 min ago") and time-of-day labels are rendered
client-side from `time`, in the viewer's timezone.

The handler does the per-source projection (spotify→{track,artist,...},
youtube→{title,activityType,...}, maps→{location,type,...}) — see
`functions/api/home/recent-events.ts:40-67`.

---

## Cross-cutting / derived endpoints

> All endpoints below are now live real Pages Functions — the "mock-only"
> framing is historical. Kept because the gold-table breakdowns are still an
> accurate reference for what each endpoint reads.

### `/api/now/timeline`

A unified, source-tagged event feed with rich state transitions
(`Track started`, `Track ended`, `Liked`, `Skipped`, `Playlist queued`,
`Album opened`, `Now playing`). All derivable from existing sources:

- Plays → `silver.spotify_plays` (already in events_unified).
- State transitions (`Track started`/`ended`/`Skipped`) → derived in
  `silver.spotify_state_events` by lagging over `bronze.spotify_player_current`.
- `Liked` → needs `me/tracks` (saved tracks) — separate Dagster schedule
  every ~5 min, dedupe on `added_at`. New bronze table:
  `bronze.spotify_saved_tracks (added_at, track_id, _ingested_at)`.
- `Playlist queued`/`Album opened` → derived from `context_type` transitions
  in `bronze.spotify_player_current`.

Built as a Pages Function (`functions/api/now/timeline.ts`) that queries
`silver.silver_events_unified` directly for the latest 60 events (`event_ts <=
now()`), mapping `kind` → a friendly `label` and joining `title`/`subtitle`
into `value`. No dedicated gold table — the unified silver view is enough.

### `/api/google/calendar`

The richest single mock. Implies `silver.calendar_events` plus an entire
sub-model for calendar analytics (busyHours, categories, weekdayBreakdown,
weekGrid, fragmentation score, longest unscheduled span). Each gold table:

```
gold.gold_calendar_kpis            -- 1 row of meeting KPIs
gold.gold_calendar_busy_hours      -- 24-row hour-of-day histogram
gold.gold_calendar_categories      -- per-category event count + percentage
gold.gold_calendar_weekday_breakdown
gold.gold_calendar_daily_events    -- per-day count
gold.gold_calendar_week_grid       -- 7×24 day×hour intensity
gold.gold_calendar_upcoming_events -- next N events
```

The `fragmentation` KPI and `longestUnscheduledHours` need a gap-analysis
window function over `silver.calendar_events` — feasible in ClickHouse with
`neighbor()`.

### `/api/system/health`

Not data-model. Comes from observability state (Dagster API for
ingestionCadence/lastBatchAgo/errors24h, ClickHouse `system.parts` for
row counts + disk, dbt for testsPass/Total). This endpoint will likely be a
Worker that aggregates from multiple sources at request time, not a
`gold.*` table.

---

## Build status

The full model is built and live — every gold table above is a dbt view the
dashboard reads, and every `/api/*` route is a real Pages Function. Maps + YouTube
share one daily Data Portability job; Calendar lands via the Calendar API
`events.watch` webhook. See `git log` for the build sequence and `OPERATIONS.md`
for how it runs day to day.

## Conventions

- Snake_case in ClickHouse, camelCase in the JSON the Pages Functions return
  (handler does the rename). Don't try to match the front-end naming in SQL.
- `event_ts` not `timestamp` (reserved-feeling), `played_at`/`watched_at`/
  `started_at` at the bronze level (source-specific verb), `event_ts` at
  silver and above (cross-source).
- `Array(...)` for fan-out fields (artists, genres, album_images) — don't
  flatten until the gold view if a downstream tile needs the array.
- `LowCardinality(String)` for any enum-like column (source, kind,
  context_type, activity_type) — saves disk and speeds up `WHERE x = 'foo'`.
- One `_ingested_at DateTime DEFAULT now()` on every bronze table for
  `ReplacingMergeTree`'s tiebreaker version column.
- All `gold.gold_*` views/tables are read by the dashboard. Internal
  aggregate states (`gold.spotify_kpis_summary_state` etc.) drop the
  `gold_` prefix so a `SHOW TABLES FROM gold LIKE 'gold_%'` lists exactly
  the dashboard surface.
