# Foreman decision-event evidence probe (experimental)

This is a small, **independent evidence branch**, not an addition to upstream PR #535.
It tests only the correlation and execution-count invariants visible in
Foreman's **simulated** traces.

Source: https://github.com/karank2512/Foreman/blob/main/docs/OTEL.md

## Reproduce

Download the published files
[`approve-path.json`](https://github.com/karank2512/Foreman/blob/main/docs/otel-evidence/approve-path.json)
and [`deny-path.json`](https://github.com/karank2512/Foreman/blob/main/docs/otel-evidence/deny-path.json)
to a local directory, then run:

```sh
python scripts/check_decision_trace.py /path/to/approve-path.json /path/to/deny-path.json
```

The checker requires `mode: Simulated`; it correlates decisions and
`execute_tool` spans by `gen_ai.tool.call.id`, ensures names agree and
`require_approval` precedes `allow` / `deny`, and requires one / zero
matching execution spans respectively. **Other tool spans are deliberately ignored.**

It does not verify actual side effects, model-issued identifiers, restart
durability, timing, OTLP collector delivery, or interoperability across
separate producers. `gen_ai.tool.call.id` is described by the current model
YAML as "The tool call identifier"; requiring its origin to be model-issued
would need a separate explicit semantic decision.

The upstream proposal is **not yet adopted or stable**.
