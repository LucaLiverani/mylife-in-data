-- Phase 0 — top-level databases.
-- Run by warehouse/ddl/apply.sh on stack boot; safe to re-apply.

CREATE DATABASE IF NOT EXISTS bronze;
CREATE DATABASE IF NOT EXISTS silver;
CREATE DATABASE IF NOT EXISTS gold;
CREATE DATABASE IF NOT EXISTS auth;

-- Dev sandbox: `dbt build --target dev` lands views here (generate_schema_name
-- prefixes non-prod targets) while reading the same bronze. Views only, so
-- these cost nothing at rest. Scoped user: warehouse/ddl/bootstrap_dev_user.sh.
CREATE DATABASE IF NOT EXISTS dev_silver;
CREATE DATABASE IF NOT EXISTS dev_gold;
