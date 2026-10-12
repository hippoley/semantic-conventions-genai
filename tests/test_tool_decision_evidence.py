"""Regression tests for approval evidence verifier (stdlib only)."""
import json
import tempfile
import unittest
from pathlib import Path
from tools.verify_tool_decision_evidence import assess


def fixture(terminal="allow", executions=1, same_id=True, mode="Simulated"):
    call_id = "call-1"
    agent_id = "run-1"
    def event(outcome, chosen_id=call_id):
        return {"name": "gen_ai.tool.call.decision", "attributes": {
            "gen_ai.tool.call.id": chosen_id,
            "gen_ai.tool.name": "send_notification",
            "gen_ai.agent.execution.id": agent_id,
            "gen_ai.tool.call.decision.outcome": outcome}}
    spans = [{"name": "invoke_agent", "attributes": {"gen_ai.agent.execution.id": agent_id},
              "events": [event("require_approval")]}]
    spans += [{"name": "tool_call_decision", "attributes": {}, "events":
               [event(terminal, call_id if same_id else "another-call")]}]
    for _ in range(executions):
        spans.append({"name": "execute_tool send_notification", "attributes": {
            "gen_ai.operation.name": "execute_tool", "gen_ai.tool.call.id": call_id,
            "gen_ai.agent.execution.id": agent_id}, "events": []})
    return {"mode": mode, "spans": spans}


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "trace.json"

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, payload, *, cross=False):
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        return assess(self.path, require_cross_process=cross)

    def test_allow_exactly_once(self):
        self.assertEqual(self.check(fixture())["status"], "PASS_SIMULATED")

    def test_deny_never_executes(self):
        self.assertEqual(self.check(fixture("deny", 0))["status"], "PASS_SIMULATED")

    def test_allow_without_execution_fails(self):
        self.assertEqual(self.check(fixture("allow", 0))["status"], "FAIL")

    def test_duplicate_execute_fails(self):
        self.assertEqual(self.check(fixture("allow", 2))["status"], "FAIL")

    def test_deny_with_execute_fails(self):
        self.assertEqual(self.check(fixture("deny", 1))["status"], "FAIL")

    def test_mismatched_call_id_fails(self):
        self.assertEqual(self.check(fixture("allow", 1, same_id=False))["status"], "FAIL")

    def test_cross_process_not_proven_by_simulated_traces(self):
        out = self.check(fixture(), cross=True)
        self.assertEqual(out["status"], "FAIL")
        self.assertIn("CROSS_PROCESS_UNPROVEN", out["reason"])

    def test_invalid_json_fails_closed(self):
        self.path.write_text("{not json", encoding="utf-8")
        self.assertEqual(assess(self.path)["status"], "FAIL")

    def test_empty_evidence_fails_closed(self):
        self.assertEqual(self.check({"spans": []})["status"], "FAIL")

    def test_execution_id_mismatch_fails(self):
        data = fixture()
        data["spans"][-1]["attributes"]["gen_ai.agent.execution.id"] = "wrong-run"
        self.assertEqual(self.check(data)["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
