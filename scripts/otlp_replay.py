#!/usr/bin/env python3
"""Convert Foreman in-memory simulated spans into OTLP/HTTP JSON and back.

This exercises the Collector transport, NOT Foreman's own live OTLP exporter.
"""
import json
import sys
from pathlib import Path

CALL_ID = "gen_ai.tool.call.id"

def any_value(v):
    if isinstance(v, bool):
        return {"boolValue": v}
    if isinstance(v, int):
        return {"intValue": str(v)}
    if isinstance(v, float):
        return {"doubleValue": v}
    return {"stringValue": str(v)}

def attrs(values):
    return [{"key": k, "value": any_value(v)} for k, v in (values or {}).items()]

def from_attrs(values):
    result = {}
    for item in values or []:
        v = item.get("value", {})
        for k in ("stringValue", "intValue", "doubleValue", "boolValue"):
            if k in v:
                result[item["key"]] = v[k]
                break
    return result

def convert(document):
    spans = []
    for idx, s in enumerate(document["spans"]):
        # Preserve trace and span ids when valid; otherwise assign deterministic test ids.
        trace = s.get("traceId") or "0123456789abcdef0123456789abcdef"
        sid = s.get("spanId") or f"{idx + 1:016x}"
        if len(trace) != 32 or len(sid) != 16:
            raise ValueError("invalid span/trace id")
        spans.append({
            "traceId": trace, "spanId": sid, "name": s.get("name", "span"),
            "startTimeUnixNano": "1000000000", "endTimeUnixNano": "1000000001",
            "attributes": attrs(s.get("attributes")),
            "events": [
                {"name": e["name"], "timeUnixNano": "1000000000",
                 "attributes": attrs(e.get("attributes"))}
                for e in s.get("events", [])
            ],
        })
    return {"resourceSpans": [{"resource": {"attributes": attrs({"service.name": "foreman-evidence-replay"})},
        "scopeSpans": [{"scope": {"name": "foreman.evidence.replay"}, "spans": spans}]}]}

def normalize(payload):
    spans = []
    for rs in payload.get("resourceSpans", []):
        for ss in rs.get("scopeSpans", []):
            for s in ss.get("spans", []):
                spans.append({"name": s.get("name"), "attributes": from_attrs(s.get("attributes")),
                    "events": [{"name": e.get("name"), "attributes": from_attrs(e.get("attributes"))}
                              for e in s.get("events", [])]})
    return {"mode": "Simulated", "spans": spans}

def main():
    if len(sys.argv) != 4 or sys.argv[1] not in ("encode", "decode"):
        print("usage: otlp_replay.py encode|decode input.json output.json", file=sys.stderr)
        return 2
    data = json.loads(Path(sys.argv[2]).read_text())
    result = convert(data) if sys.argv[1] == "encode" else normalize(data)
    Path(sys.argv[3]).write_text(json.dumps(result, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
