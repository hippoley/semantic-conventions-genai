"""Regression and adversarial checks for decision trace evidence."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).with_name("check_decision_trace.py")
spec = importlib.util.spec_from_file_location("check_decision_trace", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture(outcome="allow", execution_count=1):
    call_id = "call-1"
    decision_events = [
        {"name": module.EVENT, "attributes": {
            module.CALL_ID: call_id,
            module.OUTCOME: status,
            "gen_ai.tool.name": "send_notification",
        }}
        for status in ("require_approval", outcome)
    ]
    spans = [{"name": "invoke_agent", "events": decision_events}]
    for i in range(execution_count):
        spans.append({"name": "execute_tool send_notification", "attributes": {
            "gen_ai.operation.name": "execute_tool",
            module.CALL_ID: call_id,
            "gen_ai.tool.name": "send_notification",
        }})
    return {"mode": "Simulated", "spans": spans}


class TraceVerifierTests(unittest.TestCase):
    def assert_valid(self, doc, expected):
        errors, matched = module.validate(doc, expected)
        self.assertEqual(errors, [])
        self.assertEqual(matched, ["call-1"])

    def assert_invalid(self, doc, expected):
        errors, _ = module.validate(doc, expected)
        self.assertTrue(errors, "expected trace to fail verification")

    def test_allow_one_execution(self):
        self.assert_valid(fixture(), "allow")

    def test_deny_no_execution(self):
        self.assert_valid(fixture("deny", 0), "deny")

    def test_unrelated_execution_does_not_count(self):
        doc = fixture("deny", 0)
        doc["spans"].append({"attributes": {
            "gen_ai.operation.name": "execute_tool", module.CALL_ID: "unrelated-id"
        }})
        self.assert_valid(doc, "deny")

    def test_duplicate_execution_rejected(self):
        self.assert_invalid(fixture("allow", 2), "allow")

    def test_denied_execution_rejected(self):
        self.assert_invalid(fixture("deny", 1), "deny")

    def test_missing_execution_rejected(self):
        self.assert_invalid(fixture("allow", 0), "allow")

    def test_missing_terminal_decision_rejected(self):
        doc = fixture()
        doc["spans"][0]["events"].pop()
        self.assert_invalid(doc, "allow")

    def test_duplicate_terminal_decision_rejected(self):
        doc = fixture()
        doc["spans"][0]["events"].append(doc["spans"][0]["events"][-1].copy())
        self.assert_invalid(doc, "allow")

    def test_conflicting_terminal_decisions_rejected(self):
        doc = fixture()
        event = {"name": module.EVENT, "attributes": {
            module.CALL_ID: "call-1", module.OUTCOME: "deny",
            "gen_ai.tool.name": "send_notification"
        }}
        doc["spans"][0]["events"].append(event)
        self.assert_invalid(doc, "allow")

    def test_reversed_decision_order_rejected(self):
        doc = fixture()
        doc["spans"][0]["events"].reverse()
        self.assert_invalid(doc, "allow")

    def test_missing_id_rejected(self):
        doc = fixture()
        del doc["spans"][0]["events"][0]["attributes"][module.CALL_ID]
        self.assert_invalid(doc, "allow")

    def test_mismatched_tool_name_rejected(self):
        doc = fixture()
        doc["spans"][0]["events"][1]["attributes"]["gen_ai.tool.name"] = "other_tool"
        self.assert_invalid(doc, "allow")

    def test_mixed_valid_and_invalid_calls_rejected(self):
        doc = fixture("allow", 1)
        doc["spans"].append({"events": [
            {"name": module.EVENT, "attributes": {
                module.CALL_ID: "call-2",
                module.OUTCOME: "require_approval",
                "gen_ai.tool.name": "other_tool",
            }},
            {"name": module.EVENT, "attributes": {
                module.CALL_ID: "call-2",
                module.OUTCOME: "deny",
                "gen_ai.tool.name": "other_tool",
            }},
        ]})
        self.assert_invalid(doc, "allow")

    def test_unpaired_decision_rejected(self):
        doc = fixture("allow", 1)
        doc["spans"].append({"events": [
            {"name": module.EVENT, "attributes": {
                module.CALL_ID: "call-2",
                module.OUTCOME: "allow",
                "gen_ai.tool.name": "other_tool",
            }},
        ]})
        self.assert_invalid(doc, "allow")

    def test_non_simulated_input_rejected(self):
        doc = fixture()
        doc["mode"] = "Production"
        self.assert_invalid(doc, "allow")


if __name__ == "__main__":
    unittest.main()
