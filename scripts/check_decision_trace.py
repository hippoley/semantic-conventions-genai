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
    if not isinstance(document, dict):
        return ["trace document must be an object"], []
    errors = []
    if document.get("mode") != "Simulated":
        errors.append("fixture must explicitly declare mode=Simulated")
    spans = document.get("spans")
    if not isinstance(spans, list):
        return ["spans must be an array"], []
    events, executions = {}, Counter()
    execution_names = {}
    for span in spans:
        if not isinstance(span, dict):
            errors.append("span must be an object")
            continue
        attributes = span.get("attributes") or {}
        if not isinstance(attributes, dict):
            errors.append("span attributes must be an object")
            continue
        if attributes.get("gen_ai.operation.name") == "execute_tool":
            key = attributes.get(CALL_ID)
            if isinstance(key, str) and key:
                executions[key] += 1
                execution_names.setdefault(key, set()).add(attributes.get("gen_ai.tool.name"))
        span_events = span.get("events") or []
        if not isinstance(span_events, list):
            errors.append("span events must be an array")
            continue
        for event in span_events:
            if not isinstance(event, dict):
                errors.append("event must be an object")
                continue
            if event.get("name") != EVENT:
                continue
            a = event.get("attributes") or {}
            if not isinstance(a, dict):
                errors.append("decision attributes must be an object")
                continue
            key = a.get(CALL_ID)
            if not isinstance(key, str) or not key:
                errors.append("decision event missing valid string tool call ID (cannot correlate)")
                continue
            tool_name = a.get("gen_ai.tool.name")
            if not isinstance(tool_name, str) or not tool_name:
                errors.append(f"{key}: missing valid tool name for source-specific evidence")
            events.setdefault(key, []).append((a.get(OUTCOME), tool_name))
    matched = []
    for key, decisions in events.items():
        outcomes = [outcome for outcome, _ in decisions]
        if "require_approval" not in outcomes:
            errors.append(f"{key}: decision without require_approval")
            continue
        if outcomes.count("require_approval") != 1:
            errors.append(f"{key}: duplicate approval requirement")
        terminal = [outcome for outcome in outcomes if outcome != "require_approval"]
        if terminal != [expected]:
            errors.append(f"{key}: expected one {expected} terminal decision, got {terminal}")
            continue
        matched.append(key)
        if len({name for _, name in decisions}) != 1:
            errors.append(f"{key}: tool names differ between decision events")
        if outcomes.index("require_approval") > outcomes.index(expected):
            errors.append(f"{key}: terminal decision preceded approval requirement")
        if executions[key] and execution_names.get(key) != {decisions[0][1]}:
            errors.append(f"{key}: execution tool name differs from decision")
        count = executions[key]
        want = 1 if expected == "allow" else 0
        if count != want:
            errors.append(f"{key}: expected {want} matching execute_tool spans, got {count}")
    if not matched:
        errors.append(f"no matching require_approval → {expected} decision sequence")
    return errors, matched

def main():
    if len(sys.argv) != 3:
        print("usage: check_decision_trace.py APPROVE.json DENY.json", file=sys.stderr)
        return 2
    failed = False
    for filename, expectation in zip(sys.argv[1:], ("allow", "deny")):
        try:
            doc = json.loads(Path(filename).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            print(f"{filename}: FAIL input_error={type(exc).__name__}: {exc}", file=sys.stderr)
            failed = True
            continue
        errors, ids = validate(doc, expectation)
        simulated = isinstance(doc, dict) and doc.get("mode") == "Simulated"
        print(f"{filename}: {'FAIL' if errors else 'PASS'} matched_calls={len(ids)} simulated={simulated}")
        for error in errors:
            print(f"  ERROR: {error}")
        failed |= bool(errors)
    return int(failed)

if __name__ == "__main__":
    raise SystemExit(main())
