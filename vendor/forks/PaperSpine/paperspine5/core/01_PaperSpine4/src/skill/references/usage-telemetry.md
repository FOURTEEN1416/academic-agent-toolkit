# Usage Telemetry

Append one JSON object per model call or delegated phase to
`paper_rewriting_output/usage_ledger.jsonl`. Record:

- timestamp, stage, role, model, reasoning effort;
- `usage_source`: `api`, `host`, or `telemetry_unavailable`;
- input, cached-input, reasoning, and output tokens when the host exposes them;
- hashes of Skill/input artifacts, output artifact paths, gate result, retry;
- a concrete `telemetry_note` when usage is unavailable.

Never estimate billed tokens from file bytes inside this ledger. If the host
does not return usage, log `telemetry_unavailable` explicitly and omit token
counts. This preserves the execution receipt without pretending it is a bill.

Example unavailable event:

```json
{"timestamp":"2026-08-22T12:00:00Z","stage":"research","role":"sota-mapper","model":"host-managed","reasoning_effort":"unknown","usage_source":"telemetry_unavailable","telemetry_note":"host returned no usage object","input_hashes":[],"output_artifacts":["sota_gap_map.md"],"gate_result":"pass","retry":0}
```

Validate and aggregate by stage:

```bash
python scripts/usage_ledger.py paper_rewriting_output --markdown --write
```

An all-unavailable but well-formed ledger reports `UNAVAILABLE` and passes the
honesty check; missing or malformed telemetry fails.
