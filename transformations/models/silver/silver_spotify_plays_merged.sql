-- Lambda merge: authoritative history + the real-time stream tip, spliced at a
-- watermark so the gold Spotify metrics are streaming-first without double-counting.
--
--   metric source = history(played_at <= T)  +  stream(played_at > T, de-duped)
--
-- T = max(played_at) in bronze.spotify_plays_raw = the end of the most recent play
-- the every-minute recently-played pull has reconciled. The history side
-- (silver_spotify_plays) is the system of record and stays authoritative for
-- everything up to T; the stream side (silver_spotify_plays_stream) contributes
-- only the plays that happened after T — typically just the track playing right
-- now, surfaced ~30s into the song instead of after it finishes + the next pull.
--
-- Why this is safe (verified against live data: per-day counts equal history
-- exactly for every past day, only today carries the +1 live tip):
--   * Both sides use the END-time convention for `played_at` (see
--     silver_spotify_plays_stream), so the same play has the same timestamp on
--     both sides to within a few seconds.
--   * `played_at > T` keeps the stream to the live tip; as the minutely pull
--     advances T, each play is quietly absorbed into the authoritative count.
--   * The anti-join guard removes the one race the watermark can't: a play the
--     pull JUST reconciled (history played_at = T) whose stream copy landed a few
--     seconds later (stream end = T + small skew, so it slips past `> T`). We drop
--     a stream tip play when history already has the same track within
--     `spotify_stream_dedup_window_seconds` of it. Collecting boundary history at
--     the same window is provably sufficient: a stream play with played_at > T can
--     only collide with a history row (always <= T) inside (T - window, T].
--
-- Notes:
--   * Scalars are inlined (not a leading WITH) on purpose: a top-level WITH does
--     not reliably reach the second branch of a UNION ALL across analyzer/connection
--     settings. max(played_at) is read without FINAL — safe, because duplicate
--     ReplacingMergeTree rows share played_at, so the max is dedup-invariant.
--   * The branches are separate scans of an append-only table, so the splice is
--     exact for any single snapshot; a recently-played INSERT landing mid-query is
--     at worst a transient one-row blip on the next read, not a persistent error.
--   * A genuine same-track replay within the dedup window of T is briefly absorbed
--     by the anti-join (and the stream can't emit back-to-back same-track plays at
--     all); both self-heal once the pull reconciles the replay into history.
--   * Empty/cold-start history (max over no rows = the 1970 epoch) disables the
--     stream branch via the `> 2000` guard, so gold is never built from raw stream
--     output before any authoritative history exists.

{{ config(materialized='view', schema='silver') }}

SELECT * FROM {{ ref('silver_spotify_plays') }}
WHERE played_at <= (SELECT max(played_at) FROM {{ source('bronze', 'spotify_plays_raw') }})

UNION ALL

SELECT s.* FROM {{ ref('silver_spotify_plays_stream') }} s
WHERE s.played_at > (SELECT max(played_at) FROM {{ source('bronze', 'spotify_plays_raw') }})
  AND (SELECT max(played_at) FROM {{ source('bronze', 'spotify_plays_raw') }}) > toDateTime64('2000-01-01 00:00:00', 3)
  AND NOT arrayExists(
        x -> x.1 = s.track_id
          AND abs(dateDiff('second', x.2, s.played_at)) <= {{ var('spotify_stream_dedup_window_seconds', 120) }},
        (
          SELECT groupArray((track_id, played_at))
          FROM {{ source('bronze', 'spotify_plays_raw') }} FINAL
          WHERE played_at >= (SELECT max(played_at) FROM {{ source('bronze', 'spotify_plays_raw') }})
                             - INTERVAL {{ var('spotify_stream_dedup_window_seconds', 120) }} SECOND
        )
      )
