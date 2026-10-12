"""Normalize OTLP protobuf-JSON TracesData for approval lifecycle validation.

Supports one TracesData object or newline-delimited TracesData objects.
Only OTLP resourceSpans/scopeSpans/spans are accepted; unknown AnyValue types
and conflicting duplicate keys fail closed. Does not assert collector custody.
"""
import json
from pathlib import Path


def attributes(items):
    if not isinstance(items, list):
        raise ValueError("OTLP attributes must be a list")
    result = {}
    for attr in items:
        if not isinstance(attr, dict) or not isinstance(attr.get("key"), str) or not attr["key"]:
            raise ValueError("invalid attribute key")
        key = attr["key"]
        if key in result:
            raise ValueError("duplicate attribute key: " + key)
        val = attr.get("value")
        if not isinstance(val, dict) or len(val) != 1:
            raise ValueError("invalid AnyValue for " + key)
        kind, content = next(iter(val.items()))
        if kind not in ("stringValue", "boolValue", "intValue", "doubleValue", "bytesValue"):
            raise ValueError("unsupported AnyValue: " + kind)
        result[key] = content
    return result


def normalize(data):
    if not isinstance(data, dict) or not isinstance(data.get("resourceSpans"), list):
        raise ValueError("not an OTLP TracesData object")
    spans = []
    for resource in data["resourceSpans"]:
        resource_attrs = attributes((resource.get("resource") or {}).get("attributes", []))
        for scope in resource.get("scopeSpans", []):
            for span in scope.get("spans", []):
                attrs = attributes(span.get("attributes", []))
                events = []
                for event in span.get("events", []):
                    event_attrs = attributes(event.get("attributes", []))
                    # Event-local keys override enclosing span context; inherited
                    # execution identity is needed when events omit it.
                    inherited = dict(attrs)
                    inherited.update(event_attrs)
                    events.append({"name": event.get("name"),
                                   "attributes": inherited,
                                   "timeUnixNano": event.get("timeUnixNano")})
                spans.append({"name": span.get("name"), "traceId": span.get("traceId"),
                              "spanId": span.get("spanId"), "attributes": attrs,
                              "resourceAttributes": resource_attrs, "events": events})
    return {"spans": spans, "format": "OTLP_JSON", "provenance": "unverified"}


def read_otlp_json(path):
    content = Path(path).read_text(encoding="utf-8")
    try:
        objects = [json.loads(content)]
    except json.JSONDecodeError:
        objects = [json.loads(line) for line in content.splitlines() if line.strip()]
    if not objects:
        raise ValueError("empty OTLP export")
    combined = {"spans": [], "format": "OTLP_JSON", "provenance": "unverified"}
    for obj in objects:
        combined["spans"].extend(normalize(obj)["spans"])
    if not combined["spans"]:
        raise ValueError("no OTLP spans")
    return combined
