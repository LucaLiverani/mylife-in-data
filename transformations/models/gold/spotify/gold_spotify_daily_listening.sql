{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Daily Listening Time Series

    Daily aggregated listening hours for charts.
    Includes moving averages for trend analysis.
*/

WITH daily_plays AS (
    SELECT
        played_date AS date,
        COUNT(*) AS play_count,
        COUNT(DISTINCT track_id) AS unique_tracks,
        COUNT(DISTINCT artist_id) AS unique_artists,
        SUM(track_duration_ms) / 1000.0 / 3600.0 AS hours_listened
    FROM {{ ref('silver_spotify_tracks') }}
    GROUP BY played_date
),

with_moving_avg AS (
    SELECT
        date,
        play_count,
        unique_tracks,
        unique_artists,
        ROUND(hours_listened, 2) AS hours,

        -- 7-day moving average
        ROUND(
            AVG(hours_listened) OVER (
                ORDER BY date
                ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            ),
            2
        ) AS hours_7day_avg,

        -- 30-day moving average
        ROUND(
            AVG(hours_listened) OVER (
                ORDER BY date
                ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
            ),
            2
        ) AS hours_30day_avg,

        toDayOfWeek(date) AS day_of_week,
        toStartOfWeek(date) AS week_start,
        toStartOfMonth(date) AS month_start

    FROM daily_plays
)

SELECT
    toString(date) AS date,
    play_count,
    unique_tracks,
    unique_artists,
    hours,
    hours_7day_avg,
    hours_30day_avg,
    day_of_week,
    week_start,
    month_start,
    now() AS updated_at

FROM with_moving_avg
ORDER BY date DESC
