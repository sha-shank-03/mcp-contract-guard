import hashlib
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from mcp_contract_guard.common import GuardError, ROOT, SCHEMA_PATH, SCHEMA_SHA256, strict_json
from mcp_contract_guard.runner import Runner, cases_from
from mcp_contract_guard.stdio import Stdio
from mcp_contract_guard.validation import Validator, request

CASES = ROOT / "examples" / "cases.json"
SERVER = ROOT / "examples" / "faulty_server.py"
WIRE = ROOT / "tests" / "wire_server.py"


class M1Integration(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "mcp_contract_guard", *map(str, args)],
                              capture_output=True, text=True, cwd=ROOT, timeout=25)

    def test_snapshot_and_healthy_scalar_case_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline = Path(directory) / "baseline.json"
            report_path = Path(directory) / "report.json"
            snapshot = self.cli("snapshot", "--out", baseline, "--execution-mode", "local_mock_stdio",
                                "--", sys.executable, SERVER, "--mode", "healthy")
            self.assertEqual(snapshot.returncode, 0, snapshot.stdout + snapshot.stderr)
            saved = json.loads(baseline.read_text())
            self.assertEqual(saved["schemaSha256"], SCHEMA_SHA256)
            self.assertEqual(saved["tools"][0]["outputSchema"], {"type": "integer"})
            checked = self.cli("check", "--cases", CASES, "--report", report_path,
                               "--execution-mode", "local_mock_stdio", "--",
                               sys.executable, SERVER, "--mode", "healthy")
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            report = json.loads(report_path.read_text())
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["executionMode"], "local_mock_stdio")
            self.assertEqual(report["coverage"]["requestsSelfValidated"], 3)
            self.assertEqual(report["coverage"]["casesExecuted"], 1)
            self.assertTrue(report["cleanup"]["directChildExited"])
            self.assertTrue(report["cleanup"]["readerThreadsStopped"])

    def test_bad_output_cli_returns_actionable_failure_without_value(self):
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.json"
            result = self.cli("check", "--cases", CASES, "--report", report_path,
                              "--", sys.executable, SERVER, "--mode", "bad-output")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            report_text = report_path.read_text()
            report = json.loads(report_text)
            self.assertEqual(report["findings"][0]["ruleId"], "OUTPUT_SCHEMA")
            self.assertEqual(report["findings"][0]["caseId"], "sum-normal")
            self.assertEqual(report["findings"][0]["details"]["schemaIssues"][0]["keyword"], "type")
            self.assertNotIn("intentional mock fault", report_text + result.stdout)
            self.assertTrue(report["cleanup"]["directChildExited"])

    def test_missing_result_type_required_default_passes(self):
        runner = Runner([sys.executable, str(SERVER), "--mode", "missing-result-type"])
        code, report, _ = runner.run(cases_from(CASES))
        self.assertEqual(code, 0, report)
        self.assertEqual(len(report["observations"]), 3)
        self.assertTrue(all(o["rawSchemaIssues"] and not o["affectsExitCode"] for o in report["observations"]))
        self.assertEqual(report["findings"], [])

    def test_missing_result_type_does_not_hide_other_bad_fields(self):
        code, report, _ = Runner([sys.executable, str(WIRE), "other-invalid-with-default"]).run()
        self.assertEqual(code, 1)
        self.assertEqual(report["findings"][0]["ruleId"], "RESULT_SCHEMA")
        self.assertEqual(report["observations"][0]["ruleId"], "RESULT_TYPE_DEFAULT")

    def test_malformed_and_strict_envelope_failures(self):
        for mode, expected in [("malformed", "WIRE_JSON"), ("wrong-id", "RESPONSE_ID"),
                               ("both", "WIRE_ENVELOPE"), ("oversize", "FRAME_LIMIT"),
                               ("exit", "SERVER_EXIT")]:
            with self.subTest(mode=mode):
                code, report, saved = Runner([sys.executable, str(WIRE), mode]).run()
                self.assertEqual(code, 1, report)
                self.assertEqual(report["findings"][0]["ruleId"], expected)
                self.assertIsNone(saved)
                self.assertTrue(report["cleanup"]["directChildExited"])

    def test_local_deadline_and_skipped_case_cleanup(self):
        started = time.monotonic()
        code, report, _ = Runner([sys.executable, str(WIRE), "timeout"], request_timeout=0.15).run(cases_from(CASES))
        self.assertEqual(code, 1)
        self.assertEqual(report["findings"][0]["ruleId"], "REQUEST_TIMEOUT")
        self.assertLess(time.monotonic() - started, 8)
        self.assertEqual(report["coverage"]["casesSkipped"], 1)
        self.assertTrue(report["cleanup"]["directChildExited"])

    def test_stderr_is_drained_without_retaining_values(self):
        transport = Stdio([sys.executable, str(WIRE), "stderr"], timeout=2).open()
        try:
            reply = transport.exchange(request("server/discover", 1, {}))
            self.assertEqual(reply["id"], 1)
        finally:
            transport.close()
        self.assertGreater(transport.stderr_bytes, 65536)
        self.assertTrue(transport.cleanup["directChildExited"])

    def test_invalid_case_document_exits_two_before_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"caseVersion": 1, "caseVersion": 2}')
            result = self.cli("check", "--cases", path, "--", "this-server-does-not-exist")
            self.assertEqual(result.returncode, 2)
            self.assertIn("CONFIGURATION", result.stdout)


class M1Validation(unittest.TestCase):
    def test_vendored_pin_and_requests(self):
        self.assertEqual(hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest(), SCHEMA_SHA256)
        validator = Validator()
        for method, definition, params in [("server/discover", "DiscoverRequest", {}),
                                           ("tools/list", "ListToolsRequest", {}),
                                           ("tools/call", "CallToolRequest", {"name": "sum", "arguments": {"a": 2, "b": 3}})]:
            with self.subTest(method=method):
                message = request(method, 1, params)
                self.assertEqual(validator.definition(definition, message), [])
                del message["params"]["_meta"]["io.modelcontextprotocol/protocolVersion"]
                self.assertTrue(validator.definition(definition, message))

    def test_local_schema_reference_and_blocked_remote(self):
        validator = Validator()
        schema = {"type": "object", "$defs": {"count": {"type": "integer"}},
                  "properties": {"count": {"$ref": "#/$defs/count"}}}
        self.assertEqual(validator.instance(schema, {"count": 3}), [])
        self.assertTrue(validator.instance(schema, {"count": "wrong"}))
        with self.assertRaises(GuardError) as caught:
            validator.instance({"$ref": "https://example.invalid/never-fetch"}, {})
        self.assertEqual(caught.exception.code, "EXTERNAL_REFERENCE")

    def test_pathological_validation_is_killed_at_deadline(self):
        started = time.monotonic()
        with self.assertRaises(GuardError) as caught:
            Validator(timeout=0.6).instance({"type": "string", "pattern": "(a+)+$"}, "a" * 1000 + "!")
        self.assertEqual(caught.exception.code, "VALIDATION_TIMEOUT")
        self.assertLess(time.monotonic() - started, 5)

    def test_schema_policy_distinguishes_subschemas_from_enum_data(self):
        validator = Validator()
        data = {"$ref": "https://example.invalid/ordinary-data", "$schema": "ordinary-data"}
        self.assertEqual(validator.instance({"enum": [data]}, data), [])
        with self.assertRaises(GuardError) as caught:
            validator.schema({"allOf": [{"$ref": "https://example.invalid/no-fetch"}]})
        self.assertEqual(caught.exception.code, "EXTERNAL_REFERENCE")

    def test_strict_json_rejects_nonfinite_and_duplicate_keys(self):
        for value in ('{"x":NaN}', '{"x":1e999}', '{"x":1,"x":2}'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                strict_json(value)


if __name__ == "__main__":
    unittest.main()
