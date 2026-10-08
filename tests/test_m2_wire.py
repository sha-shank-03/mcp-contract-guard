import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mcp_contract_guard.common import ROOT
from mcp_contract_guard.runner import Runner, cases_from

WIRE = ROOT / "tests/wire_m2.py"
SERVER = ROOT / "examples/faulty_server.py"
CASES = ROOT / "examples/cases.json"


class M2Wire(unittest.TestCase):
    def test_raw_framing_content_envelopes_ids_and_error_shapes(self):
        modes = [("invalid-utf8", "WIRE_JSON"), ("truncated", "TRUNCATED_FRAME"),
                 ("missing-content", "RESULT_SCHEMA"), ("bad-content", "RESULT_SCHEMA"),
                 ("wrong-id", "RESPONSE_ID"), ("both", "WIRE_ENVELOPE"), ("neither", "WIRE_ENVELOPE"),
                 ("duplicate", "DUPLICATE_RESPONSE"), ("bad-error", "ERROR_SCHEMA"),
                 ("unknown-result-type", "RESULT_TYPE"), ("exit", "SERVER_EXIT")]
        for mode, expected in modes:
            with self.subTest(mode=mode):
                code, report, _ = Runner([sys.executable, str(WIRE), mode]).run(cases_from(CASES))
                self.assertEqual(code, 1, report)
                self.assertEqual(report["findings"][0]["ruleId"], expected)
                self.assertTrue(report["cleanup"]["directChildExited"])
                self.assertTrue(report["cleanup"]["readerThreadsStopped"])
                self.assertEqual(report["coverage"]["casesExecuted"], 1)
                if mode == "duplicate":
                    self.assertEqual(report["cases"][0]["status"], "fail")

    def test_valid_input_required_is_unsupported_coverage_not_malformed(self):
        code, report, _ = Runner([sys.executable, str(WIRE), "input-required"]).run(cases_from(CASES))
        self.assertEqual(code, 1)
        self.assertEqual(report["findings"][0]["ruleId"], "UNSUPPORTED_INTERACTION")
        self.assertNotIn("RESULT_SCHEMA", [f["ruleId"] for f in report["findings"]])

    def test_unsupported_advertised_and_peer_version_errors_do_not_fallback(self):
        for mode in ("unsupported-version", "unsupported-version-error"):
            with self.subTest(mode=mode):
                code, report, _ = Runner([sys.executable, str(SERVER), "--mode", mode]).run(cases_from(CASES))
                self.assertEqual(code, 1)
                self.assertEqual(report["findings"][0]["ruleId"], "UNSUPPORTED_PROTOCOL")
                self.assertEqual(report["coverage"]["requestsExecuted"], 1)
                self.assertEqual(report["coverage"]["casesSkipped"], 1)

    def test_silent_call_cancellation_and_no_retry_are_observed(self):
        with tempfile.TemporaryDirectory() as directory:
            audit = Path(directory) / "requests.jsonl"
            code, report, _ = Runner([sys.executable, str(WIRE), "silent", str(audit)], request_timeout=0.2).run(cases_from(CASES))
            self.assertEqual(code, 1)
            self.assertEqual(report["findings"][0]["ruleId"], "REQUEST_TIMEOUT")
            events = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
            methods = [event["method"] for event in events]
            self.assertEqual(methods, ["server/discover", "tools/list", "tools/call", "notifications/cancelled"])
            self.assertEqual(events[-1]["cancelledId"], events[-2]["id"])
            self.assertTrue(all(e["hasModernMeta"] for e in events[:-1]))
            self.assertTrue(report["cleanup"]["cancellationAttempted"])
            self.assertTrue(report["cleanup"]["directChildExited"])

    def test_tool_error_cannot_satisfy_success_or_rpc_error_expectations(self):
        base = cases_from(CASES)[0]
        expected_rpc = {**base, "id": "expected-rpc", "expect": {"kind": "rpc_error", "code": -32602}}
        expected_rpc.pop("expectedStructuredContent")
        code, report, _ = Runner([sys.executable, str(WIRE), "tool-error"]).run([base, expected_rpc])
        self.assertEqual(code, 1)
        self.assertEqual([f["ruleId"] for f in report["findings"]], ["TOOL_EXECUTION_ERROR", "OUTCOME_MISMATCH"])

    def test_boolean_error_code_in_case_config_rejected_before_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, marker = root / "cases.json", root / "launched.txt"
            path.write_text(json.dumps({"caseVersion": 1, "protocolVersion": "2026-07-28", "cases": [
                {"id": "bad-code", "tool": "sum", "arguments": {}, "expect": {"kind": "rpc_error", "code": True}}]}))
            probe = "from pathlib import Path; Path(" + repr(str(marker)) + ").write_text('launched')"
            result = subprocess.run([sys.executable, "-m", "mcp_contract_guard", "check", "--cases", str(path),
                                     "--", sys.executable, "-c", probe], cwd=ROOT, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
