"""OTLP shape, AnyValue, and JSONL regression tests; standard library only."""
import json
import tempfile
import unittest
from pathlib import Path
from tools.otlp_decision_adapter import attributes, normalize, read_otlp_json


def data():
    return {"resourceSpans": [{"resource": {"attributes": [
        {"key": "service.name", "value": {"stringValue": "foreman-web"}}]},
        "scopeSpans": [{"scope": {"name": "test"}, "spans": [{
            "name": "tool_call_decision", "traceId": "0123456789abcdef0123456789abcdef",
            "spanId": "0123456789abcdef",
            "attributes": [{"key": "gen_ai.agent.execution.id", "value": {"stringValue": "run-1"}}],
            "events": [{"name": "gen_ai.tool.call.decision", "attributes": [
                {"key": "gen_ai.tool.call.id", "value": {"stringValue": "call-1"}},
                {"key": "gen_ai.tool.call.decision.outcome", "value": {"stringValue": "allow"}}]}]}]}]}]}


class OTLPTests(unittest.TestCase):
    def test_normalizes_nested_otlp(self):
        span = normalize(data())["spans"][0]
        self.assertEqual(span["resourceAttributes"]["service.name"], "foreman-web")
        self.assertEqual(span["events"][0]["attributes"]["gen_ai.tool.call.id"], "call-1")

    def test_rejects_duplicate_keys(self):
        attrs = [{"key": "k", "value": {"stringValue": "a"}}] * 2
        with self.assertRaisesRegex(ValueError, "duplicate"):
            attributes(attrs)

    def test_rejects_unsupported_value(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            attributes([{"key": "x", "value": {"arrayValue": {}}}])

    def test_rejects_non_otlp_document(self):
        with self.assertRaises(ValueError):
            normalize({"spans": []})

    def test_json_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "export.jsonl"
            p.write_text(json.dumps(data()) + "\n" + json.dumps(data()) + "\n")
            self.assertEqual(len(read_otlp_json(p)["spans"]), 2)

    def test_unverified_provenance(self):
        self.assertEqual(normalize(data())["provenance"], "unverified")


if __name__ == "__main__":
    unittest.main()
