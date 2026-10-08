import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp_contract_guard.common import ROOT
from mcp_contract_guard.contracts import offline_diff, snapshot_from
from mcp_contract_guard.runner import Runner, cases_from

SERVER = ROOT / "examples/faulty_server.py"
CASES = ROOT / "examples/cases.json"
BASELINE = ROOT / "examples/baseline.json"


class M2Contracts(unittest.TestCase):
    def run_server(self, mode, cases=None, baseline=None, **limits):
        return Runner([sys.executable, str(SERVER), "--mode", mode], **limits).run(cases, baseline)

    def test_concrete_input_and_output_witnesses_and_review_are_separate(self):
        baseline = snapshot_from(BASELINE)
        for mode, witness in [("input-regression", "INPUT_REGRESSION"), ("output-regression", "OUTPUT_REGRESSION")]:
            with self.subTest(mode=mode):
                code, report, _ = self.run_server(mode, cases_from(CASES), baseline)
                self.assertEqual(code, 1, report)
                self.assertEqual(report["findings"][0]["ruleId"], "SCHEMA_DRIFT")
                concrete = next(f for f in report["findings"] if f["ruleId"] == witness)
                self.assertEqual(concrete["details"]["witness"], "supplied_case")
                counter = "inputWitnesses" if mode.startswith("input") else "outputWitnesses"
                self.assertEqual(report["compatibility"][counter], 1)
                if counter == "inputWitnesses":
                    self.assertEqual(report["coverage"]["casesExecuted"], 0)
                self.assertFalse(report["compatibility"]["universalCompatibilityProven"])

    def test_optional_schema_change_passes_case_but_requires_review(self):
        code, report, _ = self.run_server("schema-drift-only", cases_from(CASES), snapshot_from(BASELINE))
        self.assertEqual(code, 1, report)
        self.assertEqual(report["status"], "review_required")
        self.assertEqual(report["cases"][0]["status"], "pass")
        self.assertTrue(all(f["severity"] == "review" and f["compatibility"] == "not_proven" for f in report["findings"]))
        self.assertEqual(report["compatibility"]["inputWitnesses"] + report["compatibility"]["outputWitnesses"], 0)

    def test_baseline_validity_is_checked_before_launch(self):
        cases = cases_from(CASES)
        cases[0]["arguments"]["a"] = "never baseline-valid"
        runner = Runner([sys.executable, str(SERVER), "--mode", "healthy"])
        code, report, _ = runner.run(cases, snapshot_from(BASELINE))
        self.assertEqual(code, 2)
        self.assertEqual(report["findings"][0]["ruleId"], "CONFIGURATION")
        self.assertIsNone(runner.transport.process)
        self.assertEqual(report["coverage"]["requestsExecuted"], 0)

    def test_removed_tool_witness_and_catalog_drift(self):
        code, report, _ = self.run_server("removed-tool", cases_from(CASES), snapshot_from(BASELINE))
        self.assertEqual(code, 1)
        self.assertEqual([f["ruleId"] for f in report["findings"]], ["CATALOG_DRIFT", "TOOL_REMOVED"])

    def test_expected_success_and_both_error_mechanisms(self):
        code, report, _ = self.run_server("healthy", cases_from(ROOT / "examples/error-cases.json"))
        self.assertEqual(code, 0, report)
        self.assertEqual([c["observedOutcome"] for c in report["cases"]], ["success", "tool_error", "rpc_error"])
        self.assertEqual(report["coverage"]["casesExecuted"], 3)
        self.assertEqual(report["coverage"]["requestsExecuted"], report["coverage"]["requestsSelfValidated"])

    def test_error_expectation_must_match_mechanism_and_integer_code(self):
        base = cases_from(CASES)[0]
        base.pop("expectedStructuredContent")
        cases = [{**base, "expect": {"kind": "tool_error"}}, {**base, "id": "wrong-code", "expect": {"kind": "rpc_error", "code": -32603}}]
        code, report, _ = self.run_server("rpc-error", cases)
        self.assertEqual(code, 1)
        self.assertEqual([f["ruleId"] for f in report["findings"]], ["OUTCOME_MISMATCH", "RPC_ERROR_CODE"])
        self.assertEqual(report["coverage"]["casesExecuted"], 2)
        self.assertEqual(report["coverage"]["casesSkipped"], 0)

    def test_pagination_and_all_three_structured_shapes(self):
        code, report, saved = self.run_server("paged", cases_from(ROOT / "examples/shape-cases.json"))
        self.assertEqual(code, 0, report)
        self.assertEqual(report["coverage"]["toolListPages"], 2)
        self.assertEqual(len(saved["tools"]), 2)
        self.assertEqual(report["coverage"]["casesExecuted"], 3)
        self.assertEqual(report["coverage"]["requestsSelfValidated"], 6)

    def test_cursor_duplicate_page_tool_and_byte_bounds(self):
        for mode, options, expected in [("cursor-loop", {}, "CURSOR_LOOP"), ("duplicate-tool", {}, "DUPLICATE_TOOL"),
                ("paged", {"max_pages": 1}, "PAGE_LIMIT"), ("paged", {"max_tools": 1}, "TOOL_LIMIT"),
                ("healthy", {"max_catalog_bytes": 8}, "CATALOG_LIMIT")]:
            with self.subTest(mode=mode, options=options):
                code, report, saved = self.run_server(mode, **options)
                self.assertEqual(code, 1, report)
                self.assertEqual(report["findings"][0]["ruleId"], expected)
                self.assertIsNone(saved)
                self.assertTrue(report["cleanup"]["directChildExited"])

    def test_offline_diff_never_claims_schema_change_proves_incompatibility(self):
        old = snapshot_from(BASELINE)
        candidate = copy.deepcopy(old)
        candidate["tools"][0]["inputSchema"]["properties"]["optional"] = {"type": "string"}
        code, report = offline_diff(old, candidate)
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "review_required")
        self.assertEqual(report["findings"][0]["compatibility"], "not_proven")
        self.assertEqual(report["coverage"]["requestsExecuted"], 0)
        self.assertEqual(offline_diff(old, old)[0], 0)

    def test_empty_offline_catalog_still_requires_the_vendored_schema_pin(self):
        empty = {"tools": []}
        self.assertEqual(offline_diff(empty, empty)[0], 0)
        with patch("mcp_contract_guard.contracts.SCHEMA_PATH") as schema:
            schema.read_bytes.return_value = b"corrupted pin"
            code, report = offline_diff(empty, empty)
            self.assertEqual(code, 2)
            self.assertEqual(report["findings"][0]["ruleId"], "SCHEMA_PROVENANCE")
            schema.read_bytes.side_effect = OSError("unavailable")
            code, report = offline_diff(empty, empty)
            self.assertEqual(code, 2)
            self.assertEqual(report["findings"][0]["ruleId"], "LOCAL_IO")
            self.assertEqual(report["coverage"]["requestsExecuted"], 0)

    def test_cli_check_and_diff_preserve_reviewed_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline, candidate, report = root / "baseline.json", root / "candidate.json", root / "report.json"
            before = BASELINE.read_bytes()
            baseline.write_bytes(before); candidate.write_bytes(before)
            for args in [["check", "--baseline", str(baseline), "--cases", str(CASES), "--report", str(report), "--", sys.executable, str(SERVER)],
                         ["diff", str(baseline), str(candidate), "--report", str(report)]]:
                result = subprocess.run([sys.executable, "-m", "mcp_contract_guard", *args], cwd=ROOT, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(baseline.read_bytes(), before)
                self.assertEqual(candidate.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
