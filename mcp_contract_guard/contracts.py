"""Reviewed snapshots and exact drift; no general schema containment proof."""
import json
import hashlib
import time

from .common import GuardError, PROTOCOL_VERSION, SCHEMA_PATH, SCHEMA_SHA256, pointer, read_document
from .validation import Validator


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def snapshot_from(path):
    document = read_document(path)
    invalid = GuardError("CONFIGURATION", "The baseline is not a pinned version-1 catalog snapshot.",
                         "Review a valid snapshot with the exact protocol version and schema digest.", exit_code=2)
    if not isinstance(document, dict) or set(document) - {
            "snapshotVersion", "protocolVersion", "schemaSha256", "executionMode", "serverInfo", "tools"}:
        raise invalid
    if (type(document.get("snapshotVersion")) is not int or document["snapshotVersion"] != 1
            or document.get("protocolVersion") != PROTOCOL_VERSION
            or document.get("schemaSha256") != SCHEMA_SHA256
            or not isinstance(document.get("tools"), list) or len(document["tools"]) > 1000):
        raise invalid
    names = set()
    for tool in document["tools"]:
        if not isinstance(tool, dict) or not isinstance(tool.get("name"), str) or tool["name"] in names:
            raise invalid
        names.add(tool["name"])
    return document


def validate_snapshot(document, validator, budget):
    tools = {}
    for tool in document["tools"]:
        budget()
        issues = validator.definition("Tool", tool)
        if issues:
            raise GuardError("CONFIGURATION", "A baseline tool definition violates the pin.",
                             "Repair or recapture the reviewed baseline explicitly.",
                             details={"schemaIssues": issues}, exit_code=2)
        for field in ("inputSchema", "outputSchema"):
            if field in tool:
                budget()
                issues = validator.schema(tool[field])
                if issues:
                    raise GuardError("CONFIGURATION", "A baseline schema is invalid.",
                                     "Correct the reviewed baseline; check/diff never recapture it.",
                                     details={"schemaIssues": issues}, exit_code=2)
        tools[tool["name"]] = tool
    return tools


def changed_pointers(left, right):
    changed, pending = [], [(left, right, [])]
    while pending and len(changed) < 100:
        old, new, path = pending.pop()
        if canonical(old) == canonical(new):
            continue
        if isinstance(old, dict) and isinstance(new, dict):
            for key in sorted(set(old) | set(new), reverse=True):
                if key not in old or key not in new:
                    changed.append(pointer([*path, key]))
                else:
                    pending.append((old[key], new[key], [*path, key]))
        else:
            changed.append(pointer(path))
    return changed[:100]


def drift_findings(baseline, candidate):
    findings = []
    for name in sorted(set(baseline) | set(candidate)):
        if name not in baseline or name not in candidate:
            findings.append({"ruleId": "CATALOG_DRIFT", "severity": "review", "tool": name,
                "pointer": pointer(["tools", name]), "change": "added" if name in candidate else "removed",
                "summary": "The available tool set differs from the reviewed baseline.",
                "remedy": "Review the catalog change; explicitly recapture only after consumer review.",
                "compatibility": "not_proven", "witness": None})
            continue
        for field in ("inputSchema", "outputSchema"):
            old, new = baseline[name], candidate[name]
            if (field in old) != (field in new) or canonical(old.get(field)) != canonical(new.get(field)):
                findings.append({"ruleId": "SCHEMA_DRIFT", "severity": "review", "tool": name,
                    "pointer": pointer(["tools", name, field]),
                    "changedPointers": changed_pointers(old.get(field), new.get(field)),
                    "summary": "The exact tool schema differs from the reviewed baseline.",
                    "remedy": "Review this drift; supplied cases do not prove general compatibility.",
                    "compatibility": "not_proven", "witness": None})
    return findings


def offline_diff(baseline, candidate, *, validation_timeout=2.0, run_timeout=30.0):
    started = time.monotonic()
    validator = Validator(validation_timeout)
    report = {"reportVersion": 1, "protocolVersion": PROTOCOL_VERSION, "schemaSha256": SCHEMA_SHA256,
              "executionMode": "offline_snapshot_diff", "status": "running", "findings": [],
              "observations": [], "compatibility": {"assessment": "limited_to_exact_snapshot_drift",
                  "inputWitnesses": 0, "outputWitnesses": 0, "universalCompatibilityProven": False},
              "coverage": {"requestsExecuted": 0, "casesExecuted": 0, "toolListPages": 0,
                           "baselineTools": 0, "candidateTools": 0, "notImplemented": ["general schema containment"]}}

    def budget():
        remaining = run_timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise GuardError("RUN_TIMEOUT", "Offline comparison exceeded its validation budget.",
                             "Reduce the snapshots or review the run budget; coverage is incomplete.")
        validator.timeout = min(validation_timeout, remaining)

    code = 0
    try:
        if hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest() != SCHEMA_SHA256:
            raise GuardError("SCHEMA_PROVENANCE", "The vendored schema does not match its pin.",
                             "Restore its exact bytes before comparing snapshots.", exit_code=2)
        old = validate_snapshot(baseline, validator, budget)
        report["coverage"]["baselineTools"] = len(old)
        new = validate_snapshot(candidate, validator, budget)
        report["coverage"]["candidateTools"] = len(new)
        report["findings"] = drift_findings(old, new)
        code = 1 if report["findings"] else 0
    except GuardError as error:
        code = error.exit_code
        report["findings"].append({"ruleId": error.code, "severity": "error", "summary": error.summary,
                                   "remedy": error.remedy, "details": error.details})
    except OSError:
        code = 2
        report["findings"].append({"ruleId": "LOCAL_IO", "severity": "error", "summary": "The pinned schema cannot be read.",
                                   "remedy": "Restore the vendored schema file."})
    report.update(exitCode=code, status="fail" if any(f["severity"] == "error" for f in report["findings"])
                  else "review_required" if code else "pass", elapsedMs=round((time.monotonic() - started) * 1000, 3))
    return code, report
