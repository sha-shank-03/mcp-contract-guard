"""The release demo must reject incorrect evidence, including under -O."""
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("contract_demo", ROOT / "scripts/demo.py")
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


class DemoGate(unittest.TestCase):
    def test_gate_rejects_incorrect_exit_label_coverage_and_missing_fault(self):
        report = json.loads((ROOT / "docs/evidence/m2/bad-output.json").read_text(encoding="utf-8"))
        demo.validate_report("fault", 1, 1, report, "OUTPUT_SCHEMA")
        for field, value in [("exitCode", 0), ("executionMode", "recorded_replay")]:
            changed = copy.deepcopy(report)
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(demo.DemoFailure):
                demo.validate_report("fault", 1, 1, changed, "OUTPUT_SCHEMA")
        changed = copy.deepcopy(report)
        changed["findings"] = []
        with self.assertRaises(demo.DemoFailure):
            demo.validate_report("fault", 1, 1, changed, "OUTPUT_SCHEMA")
        offline = json.loads((ROOT / "docs/evidence/m2/diff-identical.json").read_text(encoding="utf-8"))
        offline["coverage"]["requestsExecuted"] = 1
        with self.assertRaises(demo.DemoFailure):
            demo.validate_report("offline", 0, 0, offline, offline=True)

    def test_existing_demo_directory_is_preserved_even_with_optimization(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            marker = destination / "preserved.txt"
            marker.write_bytes(b"existing bytes")
            result = subprocess.run([sys.executable, "-O", str(ROOT / "scripts/demo.py"), "--out-dir", str(destination)],
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(marker.read_bytes(), b"existing bytes")
            self.assertFalse((destination / "commands.json").exists())
            # A false gate assertion still raises when Python optimization is enabled.
            code = "import runpy; d=runpy.run_path(" + repr(str(ROOT / "scripts/demo.py")) + "); d['require'](False, 'intentional gate failure')"
            result = subprocess.run([sys.executable, "-O", "-c", code], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 1)
            self.assertIn("intentional gate failure", result.stderr)


if __name__ == "__main__":
    unittest.main()
