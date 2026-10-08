"""Asserting deterministic stdio demo; no network, replay, model, or retry."""
import argparse
import copy
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = str(Path(sys.executable).resolve())
SERVER = str(ROOT / "examples/faulty_server.py")


class DemoFailure(Exception):
    pass


def require(condition, message):
    # Deliberate checks instead of assert: python -O must not disable the gate.
    if not condition:
        raise DemoFailure(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def validate_report(label, actual_exit, expected_exit, report, rule=None, *, offline=False):
    require(actual_exit == expected_exit == report.get("exitCode"), label + ": unexpected CLI/report exit")
    require(report.get("executionMode") == ("offline_snapshot_diff" if offline else "local_mock_stdio"),
            label + ": wrong execution label")
    require(report.get("compatibility", {}).get("universalCompatibilityProven") is False,
            label + ": missing limited-coverage classification")
    if rule:
        require(rule in [finding.get("ruleId") for finding in report.get("findings", [])],
                label + ": missing expected finding " + rule)
    if offline:
        require(report["coverage"]["requestsExecuted"] == 0 and "cleanup" not in report,
                label + ": offline diff executed requests")
    else:
        require(report["coverage"]["requestsExecuted"] == report["coverage"]["requestsSelfValidated"],
                label + ": a transmitted request was not self-validated")
        require(report["cleanup"]["directChildExited"] and report["cleanup"]["readerThreadsStopped"],
                label + ": mock child/readers did not stop")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "work/demo",
                        help="New directory for receipts/reports; existing directories are refused.")
    args = parser.parse_args(argv)
    destination = args.out_dir.resolve()
    try:
        destination.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        print("DEMO CONFIGURATION: choose a new writable output directory; existing paths are preserved.", file=sys.stderr)
        return 2
    started = time.monotonic()
    baseline = destination / "baseline.json"
    records, baseline_hash = [], None
    summary = {"recordedAtUtc": datetime.now(timezone.utc).isoformat(), "interpreter": PYTHON,
               "pythonVersion": platform.python_version(), "platform": platform.platform(), "cwd": str(ROOT),
               "execution": "fresh deterministic local_mock_stdio plus offline_snapshot_diff; no replay/model/network",
               "commands": records, "allAssertionsPassed": False}

    def run(label, arguments, expected, rule=None, mode=None):
        remaining = 180 - (time.monotonic() - started)
        require(remaining > 0, "Demo exceeded its 180-second budget")
        report_path = destination / (label + ".json")
        command = [PYTHON, "-m", "mcp_contract_guard", *arguments, "--report", str(report_path)]
        if mode:
            command.extend(["--execution-mode", "local_mock_stdio", "--", PYTHON, SERVER, "--mode", mode])
        record = {"label": label, "argv": command, "expectedExit": expected, "assertedRule": rule}
        records.append(record)
        try:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=min(40, remaining))
        except subprocess.TimeoutExpired as error:
            raise DemoFailure(label + ": CLI exceeded its command budget") from error
        record.update(observedExit=result.returncode, stdout=result.stdout, stderr=result.stderr)
        require(report_path.is_file(), label + ": report was not saved")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        record["coverage"] = report["coverage"]
        validate_report(label, result.returncode, expected, report, rule, offline=mode is None)
        if baseline_hash:
            require(digest(baseline) == baseline_hash, label + ": baseline bytes changed")
        print(label + ": expected exit " + str(expected) + " verified", flush=True)
        save(destination / "commands.json", summary)
        return report

    try:
        snapshot = run("snapshot", ["snapshot", "--out", str(baseline)], 0, mode="healthy")
        require(snapshot["coverage"]["casesExecuted"] == 0, "Snapshot invoked a tool")
        baseline_hash = digest(baseline)
        summary["baselineSha256BeforeChecks"] = baseline_hash
        cases = str(ROOT / "examples/cases.json")
        for label, mode, expected, rule in [
            ("healthy", "healthy", 0, None), ("bad-output", "bad-output", 1, "OUTPUT_SCHEMA"),
            ("fallback", "missing-result-type", 0, None),
            ("input-witness", "input-regression", 1, "INPUT_REGRESSION"),
            ("output-witness", "output-regression", 1, "OUTPUT_REGRESSION"),
            ("review-only", "schema-drift-only", 1, "SCHEMA_DRIFT")]:
            report = run(label, ["check", "--baseline", str(baseline), "--cases", cases], expected, rule, mode)
            if label == "fallback":
                require(len(report["observations"]) == 3 and not report["findings"], "Fallback became a failure")
            elif label == "input-witness":
                require(report["compatibility"]["inputWitnesses"] == 1 and report["coverage"]["casesExecuted"] == 0,
                        "Input witness sent invalid arguments or lost its concrete classification")
            elif label == "output-witness":
                require(report["compatibility"]["outputWitnesses"] == 1, "Output witness was not observed")
            elif label == "review-only":
                require(report["status"] == "review_required" and report["cases"][0]["status"] == "pass"
                        and report["compatibility"]["inputWitnesses"] == report["compatibility"]["outputWitnesses"] == 0
                        and all(f["severity"] == "review" and f["compatibility"] == "not_proven" for f in report["findings"]),
                        "Unwitnessed drift was presented as a compatibility verdict")
        for label, mode, file, expected, rule in [
            ("expected-errors", "healthy", "error-cases.json", 0, None),
            ("paged-shapes", "paged", "shape-cases.json", 0, None),
            ("cursor-loop", "cursor-loop", "cases.json", 1, "CURSOR_LOOP"),
            ("duplicate-id", "duplicate-id", "cases.json", 1, "DUPLICATE_RESPONSE"),
            ("unsupported-version", "unsupported-version-error", "cases.json", 1, "UNSUPPORTED_PROTOCOL"),
            ("input-required", "input-required", "cases.json", 1, "UNSUPPORTED_INTERACTION")]:
            report = run(label, ["check", "--cases", str(ROOT / "examples" / file)], expected, rule, mode)
            if label == "expected-errors":
                require([case["observedOutcome"] for case in report["cases"]] == ["success", "tool_error", "rpc_error"],
                        "Error mechanisms were not distinguished")
            elif label == "paged-shapes":
                require(report["coverage"]["toolListPages"] == 2 and report["coverage"]["casesExecuted"] == 3,
                        "Pagination/structured-shape coverage missing")
        changed = destination / "changed-baseline.json"
        candidate = copy.deepcopy(json.loads(baseline.read_text(encoding="utf-8")))
        candidate["tools"][0]["inputSchema"]["properties"]["optional"] = {"type": "string"}
        save(changed, candidate)
        changed_hash = digest(changed)
        run("diff-identical", ["diff", str(baseline), str(baseline)], 0)
        drift = run("diff-changed", ["diff", str(baseline), str(changed)], 1, "SCHEMA_DRIFT")
        require(drift["status"] == "review_required" and all(f["compatibility"] == "not_proven" for f in drift["findings"]),
                "Offline drift claimed incompatibility")
        require(digest(changed) == changed_hash, "Diff changed its candidate input")
        summary.update(allAssertionsPassed=True, scenarios=len(records), baselineBytesPreserved=True,
                       baselineSha256AfterChecks=digest(baseline), candidateBytesPreserved=True,
                       changedSnapshotSha256=changed_hash)
        print("DEMO PASS: 15 scenarios asserted; intentional fault exits verified; no model calls.")
        return 0
    except (DemoFailure, OSError, ValueError, KeyError, TypeError) as error:
        summary["failure"] = str(error)
        print("DEMO FAIL: " + str(error), file=sys.stderr)
        return 1
    finally:
        summary["elapsedMs"] = round((time.monotonic() - started) * 1000, 3)
        save(destination / "commands.json", summary)


if __name__ == "__main__":
    raise SystemExit(main())
