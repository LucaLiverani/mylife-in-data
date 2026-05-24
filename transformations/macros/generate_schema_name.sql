{# Override dbt's default schema-name macro so that models with `schema: 'gold'`
   land in the `gold` ClickHouse database (not `<target.schema>_gold`).
   We treat the model-level schema as the ClickHouse database name verbatim. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
