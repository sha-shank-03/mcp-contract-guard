import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mcp_contract_guard.common import ROOT


class M2InputPreservation(unittest.TestCase):
    def test_cli_tool_limit_cannot_create_an_unreadable_snapshot_format(self):
        result = subprocess.run([sys.executable, "-m", "mcp_contract_guard", "snapshot", "--out", "work/unused.json",
                                 "--max-tools", "1001", "--", "this-server-does-not-exist"], cwd=ROOT,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn("at most 1000 tools", result.stderr)

    def test_baseline_and_both_diff_inputs_are_protected_from_report_aliases(self):
        variants = ["identical", "relative", "normalized", "hardlink"]
        if os.name == "nt":
            variants.append("case-insensitive")
        for operation in ("check-baseline", "diff-baseline", "diff-candidate"):
            for variant in variants:
                with self.subTest(operation=operation, alias=variant):
                    (ROOT / "work").mkdir(exist_ok=True)
                    with tempfile.TemporaryDirectory(dir=ROOT / "work") as directory:
                        root = Path(directory)
                        baseline, candidate = root / "baseline.json", root / "candidate.json"
                        baseline.write_bytes((ROOT / "examples/baseline.json").read_bytes())
                        candidate.write_bytes(baseline.read_bytes())
                        protected = candidate if operation == "diff-candidate" else baseline
                        before = {p: p.read_bytes() for p in (baseline, candidate)}
                        output = protected
                        if variant == "relative":
                            output = protected.relative_to(ROOT)
                        elif variant == "normalized":
                            child = root / "subdir"; child.mkdir()
                            output = child / ".." / protected.name
                        elif variant == "hardlink":
                            output = root / "same-file.json"; os.link(protected, output)
                        elif variant == "case-insensitive":
                            output = protected.with_name(protected.name.upper())
                        marker = root / "launched.txt"
                        if operation == "check-baseline":
                            probe = "from pathlib import Path; Path(" + repr(str(marker)) + ").write_text('launched')"
                            args = ["check", "--baseline", str(baseline), "--cases", "examples/cases.json", "--report", str(output), "--", sys.executable, "-c", probe]
                        else:
                            args = ["diff", str(baseline), str(candidate), "--report", str(output)]
                        result = subprocess.run([sys.executable, "-m", "mcp_contract_guard", *args], cwd=ROOT,
                                                capture_output=True, text=True, timeout=10)
                        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                        self.assertIn("same file", result.stdout)
                        self.assertFalse(marker.exists())
                        for path, data in before.items():
                            self.assertEqual(path.read_bytes(), data)


if __name__ == "__main__":
    unittest.main()
