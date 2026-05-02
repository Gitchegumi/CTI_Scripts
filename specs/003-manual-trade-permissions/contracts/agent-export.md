# Contract: Agent Export

## Purpose

Provide a structured JSON package that AI agents and LLM workflows can use to evaluate strategy performance, inspect corrections and annotations, and propose strategy adjustments without scraping dashboard UI.

## Format

The first version uses JSON with schema name `Agent Export` and schema version `manual-trade-agent-export.v1`.

## Top-Level Shape

```json
{
  "schema_version": "manual-trade-agent-export.v1",
  "schema_name": "Agent Export",
  "generated_at": "2026-05-01T16:00:00-05:00",
  "bot_mode": "alert_only",
  "scope": {},
  "chunking": {
    "chunk_index": 1,
    "chunk_count": 1,
    "record_offset": 0,
    "record_limit": 1000
  },
  "summary": {},
  "field_metadata": {},
  "analysis_context": {},
  "records": []
}
```

## Required Metadata

- `schema_version`: Stable version string for agent parsers.
- `schema_name`: Canonical export name, `Agent Export`.
- `generated_at`: Export creation timestamp.
- `bot_mode`: The isolated mode represented by the export.
- `scope`: Filters and limits used to generate the export.
- `chunking`: Chunk metadata for agent workflows and bounded context windows.
- `summary`: Counts and basic outcome totals.
- `field_metadata`: Plain-language field descriptions.
- `analysis_context`: Purpose, caveats, mode-isolation notes, override semantics, and legacy defaulting behavior.

## Record Requirements

Each record includes:

- Canonical trade identity.
- Source and source trade id.
- Bot mode.
- Manual/non-manual origin.
- Displayed trade values after overrides.
- Source values when available.
- Overridden fields and corrected values when applicable.
- Notes and tags.
- Timing, price, size, status, fees, and P/L fields.
- Permission snapshot for auditability.
- Optional linked strategy or signal context already available in unified history, such as `strategy`, `signal_id`, `confidence`, `setup_label`, or `source_context`.

## Constraints

- The export represents exactly one bot mode.
- The export must be deterministic for the same filters and data, except for `generated_at`.
- No credentials, API keys, webhook URLs, or account secrets may appear in the export.
- The export must be valid JSON and parseable without dashboard code.
- Agent Export v1 does not require new strategy diagnostics collection; it includes linked strategy/signal context only when already available in the unified history data.
