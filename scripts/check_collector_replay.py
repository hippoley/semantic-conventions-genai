#!/usr/bin/env python3
"""Check Collector-exported replay preserves gated call decisions and execution counts.

This does NOT demonstrate Foreman's exporter itself sent spans to a Collector.
"""
import json
import sys
from pathlib import Path

KEY = "gen_ai.tool.call.id"
EVENT = "gen_ai.tool.call.decision"
OUTCOME = "gen_ai.tool.call.decision.outcome"

def get_calls(document):
    calls = {}
    for span in document["spans"]:
        attributes = span.get("attributes") or {}
        if attributes.get("gen_ai.operation.name") == "execute_tool" and KEY in attributes:
            entry = calls.setdefault(attributes[KEY], {"decisions": [], "executions": 0})
            entry["executions"] += 1
        for event in span.get("events") or []:
            if event.get("name") != EVENT:
                continue
            a = event.get("attributes") or {}
            entry = calls.setdefault(a[KEY], {"decisions": [], "executions": 0})
            entry["decisions"].append(a[OUTCOME])
    return calls

def main():
    if len(sys.argv) != 4:
        print("usage: check_collector_replay.py approve.json deny.json normalized.json", file=sys.stderr)
        return 2
    approve, deny, collected = [json.loads(Path(f).read_text()) for f in sys.argv[1:]]
    observed = get_calls(collected)
    gated = {}
    for source in (approve, deny):
        for call_id, values in get_calls(source).items():
            if "require_approval" in values["decisions"]:
                gated[call_id] = values
    if len(gated) != 2:
        raise AssertionError(f"expected 2 source gated calls, got {len(gated)}")
    for key, expected in gated.items():
        actual = observed.get(key)
        if not actual:
            raise AssertionError(f"gated call {key} absent from Collector output")
        if sorted(expected["decisions"]) != sorted(actual["decisions"]):
            raise AssertionError(f"{key}: decisions mismatch: {actual['decisions']}")
        if expected["executions"] != actual["executions"]:
            raise AssertionError(f"{key}: execution count mismatch: {actual['executions']}")
    print(f"Collector correlation PASS: {len(gated)} gated calls, decisions and execution counts preserved")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
