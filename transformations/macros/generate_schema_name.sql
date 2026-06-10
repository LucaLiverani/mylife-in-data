{# Override dbt's default schema-name macro so that models with `schema: 'gold'`
   land in the `gold` ClickHouse database (not `<target.schema>_gold`).
   We treat the model-level schema as the ClickHouse database name verbatim.

   Target-aware: any target other than `prod` gets a `dev_` prefix
   (silver -> dev_silver, gold -> dev_gold), so a dev build can never clobber
   the production layer databases while source() keeps resolving to the same
   bronze. The `prod` target name is pinned in DbtCliResource
   (orchestration/dagster/definitions.py) and is the profiles.yml default. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set base = (custom_schema_name | trim) if custom_schema_name is not none else target.schema -%}
    {%- if target.name == 'prod' or base.startswith('dev_') -%}
        {{ base }}
    {%- else -%}
        dev_{{ base }}
    {%- endif -%}
{%- endmacro %}
