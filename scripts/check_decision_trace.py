#!/usr/bin/env python3
"""Validate experimental tool-call decision traces; not a semconv certification.

Usage: python scripts/check_decision_trace.py approve.json deny.json
Stdlib-only. Evaluates each gated call by ID, not global execute_tool counts.
"""
import json
import sys
from collections import Counter
from pathlib import Path

EVENT = "gen_ai.tool.call.decision"
OUTCOME = EVENT + ".outcome"
CALL_ID = "gen_ai.tool.call.id"

def validate(document, expected):
    errors = []
    if document.get("mode") != "Simulated":
        errors.append("fixture must explicitly declare mode=Simulated")
    events, executions = {}, Counter()
    for span in document.get("spans", []):
        attributes = span.get("attributes", {})
        if attributes.get("gen_ai.operation.name") == "execute_tool":
            key = attributes.get(CALL_ID)
            if key:
                executions[key] += 1
        for event in span.get("events", []):
            if event.get("name") != EVENT:
                continue
            a = event.get("attributes", {})
            key = a.get(CALL_ID)
            if not key:
                errors.append("decision event missing tool call ID (cannot correlate)")
                continue
            events.setdefault(key, []).append((a.get(OUTCOME), a.get("gen_ai.tool.name")))
    matched = []
    for key, decisions in events.items():
        outcomes = [o for o, _ in decisions]
        if "require_approval" not in outcomes:
            continue
        if expected not in outcomes:
            errors.append(f"{key}: missing expected terminal outcome {expected}")
            continue
        matched.append(key)
        if outcomes.count("require_approval") != 1 or outcomes.count(expected) != 1:
            errors.append(f"{key}: duplicate approval or terminal decision")
        if len({n for _, n in decisions}) != 1:
            errors.append(f"{key}: tool names differ between decision events")
        if outcomes.index("require_approval") > outcomes.index(expected):
            errors.append(f"{key}: terminal decision preceded approval requirement")
        count = executions[key]
        want = 1 if expected == "allow" else 0
        if count != want:
            errors.append(f"{key}: expected {want} matching execute_tool spans, got {count}")
        if ("allow" in outcomes) and ("deny" in outcomes):
            errors.append(f"{key}: contradictory allow/deny decisions")
    if not matched:
        errors.append(f"no matching require_approval → {expected} decision sequence")
    return errors, matched

def main():
    if len(sys.argv) != 3:
        print("usage: check_decision_trace.py APPROVE.json DENY.json", file=sys.stderr)
        return 2
    failed = False
    for filename, expectation in zip(sys.argv[1:], ("allow", "deny")):
        doc = json.loads(Path(filename).read_text(encoding="utf-8"))
        errors, ids = validate(doc, expectation)
        print(f"{filename}: {'FAIL' if errors else 'PASS'} matched_calls={len(ids)} simulated={doc.get('mode') == 'Simulated'}")
        for error in errors:
            print(f"  ERROR: {error}")
        failed |= bool(errors)
    return int(failed)

if __name__ == "__main__":
    raise SystemExit(main())
