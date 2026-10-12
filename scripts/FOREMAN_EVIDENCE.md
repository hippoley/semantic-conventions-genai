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

## Evidence boundary and adoption gate

This is a **Foreman fixture-specific** verifier: it deliberately requires a
non-empty `gen_ai.tool.name` and correlation ID in the captured decision records.
Those are stronger fixture assertions than the proposed semantic convention's
`Recommended If available` attributes and **must not** be interpreted as
universal semantic-convention conformance requirements.

A passing trace shows record consistency, not that the exporter is deployed,
that an OpenTelemetry Collector received the data, that a provider created
model-owned IDs, or that physical side effects are idempotent. Use separate,
independently captured Collector evidence before making those claims.

Source is pinned to Foreman commit
[`6d57dca896a01c2f7aefa905a11369d3de09b6c0`](https://github.com/karank2512/Foreman/commit/6d57dca896a01c2f7aefa905a11369d3de09b6c0)
in CI so passing results remain attributable to specific upstream bytes.
