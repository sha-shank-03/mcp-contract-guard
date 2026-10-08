import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp_contract_guard.common import GuardError, MAX_FRAME, ROOT, read_document

CASES = ROOT / "examples" / "cases.json"


class CliPreservation(unittest.TestCase):
    def call(self, arguments, marker):
        # If launch happens, this independent child writes a marker before exiting.
        launch_probe = "from pathlib import Path; Path(" + repr(str(marker)) + ").write_text('launched')"
        return subprocess.run([sys.executable, "-m", "mcp_contract_guard", *map(str, arguments),
                               "--", sys.executable, "-c", launch_probe],
                              cwd=ROOT, capture_output=True, text=True, timeout=10)

    def test_existing_collisions_preserve_all_bytes_and_never_launch(self):
        variants = ["identical", "relative-absolute", "normalized", "hardlink"]
        if os.name == "nt":
            variants.append("case-insensitive")
        for operation in ("snapshot", "check"):
            for variant in variants:
                with self.subTest(operation=operation, alias=variant):
                    (ROOT / "work").mkdir(exist_ok=True)
                    with tempfile.TemporaryDirectory(dir=ROOT / "work") as directory:
                        base = Path(directory)
                        protected = base / "protected.json"
                        before = CASES.read_bytes() if operation == "check" else b'Existing output: \x00\xff\n'
                        protected.write_bytes(before)
                        target = protected
                        if variant == "relative-absolute":
                            target = protected.relative_to(ROOT)
                        elif variant == "normalized":
                            child = base / "child"
                            child.mkdir()
                            target = child / ".." / protected.name
                        elif variant == "hardlink":
                            target = base / "report-hardlink.json"
                            os.link(protected, target)
                        elif variant == "case-insensitive":
                            target = protected.with_name(protected.name.upper())
                        marker = base / "launched.txt"
                        flag = "--out" if operation == "snapshot" else "--cases"
                        result = self.call([operation, flag, protected, "--report", target], marker)
                        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                        self.assertIn("CONFIGURATION", result.stdout)
                        self.assertIn("same file", result.stdout)
                        self.assertFalse(marker.exists(), "Aliased output launched a server")
                        self.assertEqual(protected.read_bytes(), before)
                        self.assertEqual((ROOT / target if not target.is_absolute() else target).read_bytes(), before)

    def test_nonexistent_normalized_alias_creates_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            target = base / "new.json"
            alias = base / "not-created" / ".." / target.name
            marker = base / "launched.txt"
            result = self.call(["snapshot", "--out", target, "--report", alias], marker)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertFalse(target.exists())
            self.assertFalse((base / "not-created").exists())
            self.assertFalse(marker.exists())

    def test_oversized_case_input_is_preserved_and_rejected_before_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source, report, marker = base / "large.json", base / "report.json", base / "launched.txt"
            before = CASES.read_bytes() + b" " * (MAX_FRAME + 100)
            source.write_bytes(before)
            result = self.call(["check", "--cases", source, "--report", report], marker)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("CONFIGURATION", result.stdout)
            self.assertEqual(source.read_bytes(), before)
            self.assertFalse(marker.exists())
            saved = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(saved["coverage"]["requestsExecuted"], 0)


class BoundedInput(unittest.TestCase):
    def test_oversized_read_consumes_only_limit_plus_one_bytes(self):
        consumed = []

        class ReadProbe(io.BytesIO):
            def read(self, size=-1):
                result = super().read(size)
                consumed.append(len(result))
                return result

        # This instrumentation fails the old unbounded Path.read_bytes implementation.
        stream = ReadProbe(b" " * (MAX_FRAME * 2))
        with patch.object(Path, "open", return_value=stream):
            with self.assertRaises(GuardError) as caught:
                read_document("oversized-test.json")
        self.assertEqual(caught.exception.exit_code, 2)
        self.assertEqual(sum(consumed), MAX_FRAME + 1)

    def test_document_at_exact_limit_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "boundary.json"
            source.write_bytes(b"{}" + b" " * (MAX_FRAME - 2))
            self.assertEqual(read_document(source), {})


if __name__ == "__main__":
    unittest.main()
