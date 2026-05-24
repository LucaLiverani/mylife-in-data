-- Phase 0 — top-level databases.
-- Run by warehouse/ddl/apply.sh on stack boot; safe to re-apply.

CREATE DATABASE IF NOT EXISTS bronze;
CREATE DATABASE IF NOT EXISTS silver;
CREATE DATABASE IF NOT EXISTS gold;
CREATE DATABASE IF NOT EXISTS auth;
