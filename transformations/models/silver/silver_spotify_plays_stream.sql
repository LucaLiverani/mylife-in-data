-- Speed layer: clean plays derived from the noisy now-playing stream.
--
-- bronze.spotify_player_current holds state-transition events emitted by the
-- producer on every track change or play/pause flip (NOT one row per play). To
-- turn that into plays we apply dwell-time logic over the ordered events:
--   * a "segment" begins each time the current track_id changes (pause/resume
--     events keep the same track_id, so they fold into the same segment);
--   * the segment's dwell is the gap to the NEXT track change (or now() for the
--     still-playing track), CLAMPED to the track's own length (see below), and
--     we count it as a play once that dwell clears ~30s — long enough to discard
--     2s skips, short enough to surface the current track mid-play.
--
-- Timestamp convention (critical, see the merge in silver_spotify_plays_merged):
-- Spotify's recently-played `played_at` is the track's END time (measured on live
-- data: it lines up with the START of the next track), so we timestamp each
-- derived play by its segment END (`seg_end`), not its start. That makes these
-- rows directly comparable to silver_spotify_plays' `played_at`. The still-playing
-- track has no end yet, so its `seg_end` is now() and its row is non-deterministic
-- across queries (it renders as "now" / 0m ago and creeps forward) — intended:
-- it is the live tip, and it stabilises the instant history reconciles the play.
--
-- Duration clamp: a track cannot stay current longer than its own length (we
-- can't observe a same-track repeat, which emits no event). Clamping `seg_end` to
-- captured_at + duration + slack (a) stops the last track extending to now()
-- forever once playback stops or the producer dies, and (b) keeps a track that
-- straddles a producer-downtime gap timestamped at its real end (≈ captured +
-- duration) instead of at the far edge of the gap — so the merge's anti-join
-- still recognises it as already reconciled and never double-counts it.
--
-- Output columns + types are IDENTICAL to silver_spotify_plays so the merge view
-- can UNION ALL the two. The stream is lossy (can't see same-track repeats, drops
-- skips inside one 5s poll, misses producer downtime); it is only ever the
-- real-time tip on top of the authoritative history, never a substitute. Like
-- every other play row, a counted play contributes its FULL catalog duration_ms
-- to the hour metrics (consistent with how history counts partial plays).

{{ config(materialized='view', schema='silver') }}

WITH base AS (
    SELECT
        captured_at, track_id, track_name, track_duration_ms,
        artists_ids, artists_names, album_name, album_images,
        context_type, context_uri,
        -- chronological previous event's track. track_id tiebreaks same-ms ties
        -- so the segmentation is reproducible.
        lagInFrame(track_id, 1, '__none__')
            OVER (ORDER BY captured_at, track_id ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS prev_track_id
    FROM {{ source('bronze', 'spotify_player_current') }} FINAL
    -- Bound the window sort; only plays newer than the history watermark (~now)
    -- ever survive the merge, so a generous recent window is plenty. The first
    -- row in the window mis-detects as a segment start, but it is days old and
    -- never clears the watermark, so it is harmless.
    WHERE captured_at >= now() - INTERVAL 7 DAY
),
-- One row per time the current track actually CHANGED (segment start). Same-track
-- pause/resume events are dropped here, collapsing each track's tenure to one row.
seg AS (
    SELECT captured_at, track_id, track_name, track_duration_ms,
           artists_ids, artists_names, album_name, album_images, context_type, context_uri
    FROM base
    WHERE track_id != prev_track_id AND track_id != ''
),
-- Start of the next segment (next track change); a far-future sentinel marks the
-- still-playing tail segment that has no next change yet.
nxt AS (
    SELECT *,
        leadInFrame(captured_at, 1, toDateTime64('2200-01-01 00:00:00', 3))
            OVER (ORDER BY captured_at, track_id ROWS BETWEEN CURRENT ROW AND 1 FOLLOWING) AS next_start
    FROM seg
),
-- Segment end = min(next change | now(), captured_at + duration + slack). The
-- clamp is a no-op for a track played straight through (next change ≈ end) and
-- only bites on the open tail and on gaps (stopped playback / producer downtime).
bounded AS (
    SELECT *,
        least(
            if(next_start = toDateTime64('2200-01-01 00:00:00', 3), now64(3), next_start),
            if(track_duration_ms > 0,
               captured_at + toIntervalSecond(intDiv(track_duration_ms, 1000) + 15),
               now64(3))
        ) AS seg_end
    FROM nxt
),
plays AS (
    SELECT
        seg_end AS played_at,  -- END-time convention, aligns with recently-played
        track_id, track_name, track_duration_ms,
        artists_ids, artists_names, album_name, album_images, context_type, context_uri
    FROM bounded
    WHERE dateDiff('second', captured_at, seg_end) >= {{ var('spotify_stream_dwell_seconds', 30) }}
),
tracks AS (
    SELECT * FROM {{ source('bronze', 'spotify_tracks') }} FINAL
),
artists AS (
    SELECT * FROM {{ source('bronze', 'spotify_artists') }} FINAL
)
-- Enrich exactly like silver_spotify_plays: prefer the catalog value, fall back to
-- the metadata the stream already carries so a brand-new play still renders.
SELECT
    p.played_at                                                       AS played_at,
    p.track_id                                                        AS track_id,
    if(t.track_name != '', t.track_name, p.track_name)                AS track_name,
    if(t.duration_ms > 0, t.duration_ms, p.track_duration_ms)         AS duration_ms,
    if(notEmpty(p.artists_ids), arrayElement(p.artists_ids, 1), arrayElement(t.artists_ids, 1)) AS primary_artist_id,
    if(a.artist_name != '', a.artist_name, arrayElement(p.artists_names, 1))  AS primary_artist_name,
    a.genres                                                          AS genres,
    if(t.album_name != '', t.album_name, p.album_name)                AS album_name,
    if(notEmpty(t.album_images), arrayElement(t.album_images, 1), arrayElement(p.album_images, 1)) AS album_art_url,
    p.context_type                                                    AS context_type,
    p.context_uri                                                     AS context_uri
FROM plays p
LEFT JOIN tracks t ON t.track_id = p.track_id
LEFT JOIN artists a ON a.artist_id = if(notEmpty(p.artists_ids), arrayElement(p.artists_ids, 1), arrayElement(t.artists_ids, 1))
