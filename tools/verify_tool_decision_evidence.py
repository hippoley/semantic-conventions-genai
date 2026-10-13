#!/usr/bin/env python3
"""Validate tool approval evidence per call id; no OpenTelemetry SDK required.

Usage:
  python3 tools/verify_tool_decision_evidence.py approve.json deny.json
  python3 tools/verify_tool_decision_evidence.py --require-cross-process approve.json deny.json

The second mode is intentionally fail-closed unless explicit producer/process
identities from at least two processes exist across decision and execution.
This verifier validates evidence, not production adoption or semantic acceptance.
"""
import argparse
import json
import sys
from pathlib import Path
from tools.otlp_decision_adapter import read_otlp_json

EVENT = "gen_ai.tool.call.decision"
ID = "gen_ai.tool.call.id"
OUTCOME = "gen_ai.tool.call.decision.outcome"
EXECUTION = "gen_ai.agent.execution.id"


def assess(path, require_cross_process=False):
    try:
        try:
            raw = Path(path).read_text(encoding="utf-8")
            parsed = json.loads(raw)
            data = read_otlp_json(path) if "resourceSpans" in parsed else parsed
        except json.JSONDecodeError:
            data = read_otlp_json(path)
        spans = data["spans"]
        if not isinstance(spans, list):
            raise ValueError("spans must be an array")
        decisions = []
        tool_spans = []
        for span in spans:
            attrs = span.get("attributes") or {}
            if attrs.get("gen_ai.operation.name") == "execute_tool":
                tool_spans.append(span)
            for event in span.get("events") or []:
                if event.get("name") == EVENT:
                    decisions.append((event.get("attributes") or {}, span, event.get("timeUnixNano")))
        grouped = {}
        for attrs, span, timestamp in decisions:
            call_id = attrs.get(ID)
            if not isinstance(call_id, str) or not call_id:
                raise ValueError("decision event lacks nonempty tool-call id")
            run_id = attrs.get(EXECUTION)
            if not isinstance(run_id, str) or not run_id:
                raise ValueError(f"{call_id}: decision lacks execution id")
            grouped.setdefault((run_id, call_id), []).append((attrs, span, timestamp))
        checked = []
        for (run_id, call_id), entries in grouped.items():
            outcomes = [attrs.get(OUTCOME) for attrs, _, _ in entries]
            if "require_approval" not in outcomes:
                continue
            if outcomes.count("require_approval") != 1:
                raise ValueError(f"{call_id}: duplicate approval-gate decisions")
            if any(o not in ("require_approval", "allow", "deny") for o in outcomes):
                raise ValueError(f"{call_id}: unrecognized/extended outcome requires separate review")
            terminals = [x for x in outcomes if x in ("allow", "deny")]
            if len(terminals) != 1:
                raise ValueError(f"{call_id}: expected exactly one allow/deny decision")
            if data.get("format") == "OTLP_JSON":
                timestamps = []
                for _, _, raw_time in entries:
                    if not isinstance(raw_time, (str, int)) or not str(raw_time).isdigit() or int(raw_time) <= 0:
                        raise ValueError(f"{call_id}: OTLP decision lacks valid event timeUnixNano")
                    timestamps.append(int(raw_time))
                gate_time = timestamps[outcomes.index("require_approval")]
                terminal_time = timestamps[outcomes.index(terminals[0])]
                if terminal_time <= gate_time:
                    raise ValueError(f"{call_id}: terminal decision must follow gate in event time")
            elif outcomes.index("require_approval") > outcomes.index(terminals[0]):
                raise ValueError(f"{call_id}: outcome ordering is invalid")
            execs = [s for s in tool_spans if (s.get("attributes") or {}).get(ID) == call_id and (s.get("attributes") or {}).get(EXECUTION) == run_id]
            expected = 1 if terminals[0] == "allow" else 0
            if len(execs) != expected:
                raise ValueError(f"{call_id}: {terminals[0]} has {len(execs)} executions, expected {expected}")
            # OTLP span timestamps are not tied to JSON/export order.  An
            # allowed tool must not begin before its recorded permission.
            if data.get("format") == "OTLP_JSON" and terminals[0] == "allow":
                start = execs[0].get("startTimeUnixNano")
                if not isinstance(start, (str, int)) or isinstance(start, bool) or not str(start).isdigit() or int(start) <= 0:
                    raise ValueError(f"{call_id}: executed tool lacks valid OTLP startTimeUnixNano")
                if int(start) < terminal_time:
                    raise ValueError(f"{call_id}: execution began before approval")

            execution_ids = {a.get(EXECUTION) for a, _, _ in entries}
            execution_ids.update((s.get("attributes") or {}).get(EXECUTION) for s in execs)
            if len(execution_ids) != 1 or None in execution_ids:
                raise ValueError(f"{call_id}: missing/inconsistent agent execution id")
            checked.append({"call_id": call_id, "outcome": terminals[0], "execution_count": len(execs)})
        if not checked:
            raise ValueError("no gated tool call with an allow/deny terminal decision")
        # Span trace IDs are insufficient proof of distinct instrumented OS processes.
        if require_cross_process:
            raise ValueError("CROSS_PROCESS_UNPROVEN: artifact lacks independently attested web/worker process provenance and collector receipt")
        return {"artifact": str(path), "status": "PASS_SIMULATED" if data.get("mode") == "Simulated" else "INCONCLUSIVE_PROVENANCE", "calls": checked}
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return {"artifact": str(path), "status": "FAIL", "reason": str(exc)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-cross-process", action="store_true")
    parser.add_argument("artifacts", nargs="+")
    args = parser.parse_args()
    results = [assess(p, args.require_cross_process) for p in args.artifacts]
    print(json.dumps({"results": results}, indent=2))
    return 0 if all(r["status"].startswith("PASS") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
