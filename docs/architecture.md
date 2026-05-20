┌─────────────────────────────────────────────────────────┐
│ INGESTION LAYER (Airflow)                               │
│ Spotify API → JSONL → MinIO                             │
│ Kafka → Streaming events                                │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ LOADING LAYER (DuckDB/Spark + PyIceberg)                │
│ JSONL → Iceberg Tables (Bronze/Silver)                  │
│ - Type casting, basic cleaning                          │
│ - Deduplication                                         │
│ - Schema enforcement                                    │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ TRANSFORMATION LAYER (dbt)                              │
│ Bronze/Silver → Gold tables                             │
│ - Business logic                                        │
│ - Joins across sources                                  │
│ - Aggregations & metrics                                │
│ - Data quality tests                                    │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ SERVING LAYER (Dashboard)                               │
│ Query Gold tables for pre-computed metrics              │
│ Query Silver tables for real-time data                  │
└─────────────────────────────────────────────────────────┘