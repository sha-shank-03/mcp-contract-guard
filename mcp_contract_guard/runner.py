import copy
import hashlib
import json
import time
from dataclasses import dataclass

from .common import GuardError, MAX_FRAME, PROTOCOL_VERSION, SCHEMA_PATH, SCHEMA_SHA256, read_document
from .contracts import canonical, drift_findings, validate_snapshot
from .stdio import Stdio
from .validation import Validator, request

DEFINITIONS = {"server/discover": ("DiscoverRequest", "DiscoverResult"),
               "tools/list": ("ListToolsRequest", "ListToolsResult"),
               "tools/call": ("CallToolRequest", "CallToolResult")}
BASE_SOURCE = "https://modelcontextprotocol.io/specification/2026-07-28/basic"
CASE_FAILURES = {"INPUT_SCHEMA", "INPUT_REGRESSION", "OUTPUT_SCHEMA", "OUTPUT_REGRESSION",
                 "CASE_EXPECTATION", "CASE_TOOL_MISSING", "TOOL_REMOVED", "TOOL_EXECUTION_ERROR",
                 "PEER_RPC_ERROR", "OUTCOME_MISMATCH", "RPC_ERROR_CODE"}


@dataclass(frozen=True)
class PeerError:
    code: int


def cases_from(path):
    document = read_document(path)
    invalid = GuardError("CONFIGURATION", "The case file is not a pinned version-1 case document.",
                         "Use 1-100 unique cases with success, tool_error, or rpc_error plus integer code.", exit_code=2)
    if not isinstance(document, dict) or set(document) != {"caseVersion", "protocolVersion", "cases"}:
        raise invalid
    if type(document["caseVersion"]) is not int or document["caseVersion"] != 1:
        raise invalid
    if document["protocolVersion"] != PROTOCOL_VERSION:
        raise invalid
    cases = document["cases"]
    if not isinstance(cases, list) or not 1 <= len(cases) <= 100:
        raise invalid
    ids = set()
    for case in cases:
        if not isinstance(case, dict) or not {"id", "tool", "arguments"} <= case.keys():
            raise invalid
        if set(case) - {"id", "tool", "arguments", "expectedStructuredContent", "expect", "allowInvalidArguments"}:
            raise invalid
        if (not isinstance(case["id"], str) or not 1 <= len(case["id"]) <= 128
                or case["id"] in ids or not isinstance(case["tool"], str) or not case["tool"]
                or not isinstance(case["arguments"], dict)):
            raise invalid
        expect = case.get("expect", {"kind": "success"})
        if not isinstance(expect, dict) or expect.get("kind") not in {"success", "tool_error", "rpc_error"}:
            raise invalid
        allowed = {"kind", "code"} if expect["kind"] == "rpc_error" else {"kind"}
        if set(expect) != allowed or (expect["kind"] == "rpc_error" and type(expect.get("code")) is not int):
            raise invalid
        if type(case.get("allowInvalidArguments", False)) is not bool:
            raise invalid
        if expect["kind"] == "success" and case.get("allowInvalidArguments", False):
            raise invalid
        if expect["kind"] != "success" and "expectedStructuredContent" in case:
            raise invalid
        ids.add(case["id"])
    return cases


class Runner:
    def __init__(self, argv, *, mode="local_stdio", request_timeout=2.0,
                 validation_timeout=2.0, run_timeout=30.0, max_pages=10,
                 max_tools=1000, max_catalog_bytes=MAX_FRAME):
        self.started = time.monotonic()
        self.run_timeout, self.validation_timeout = run_timeout, validation_timeout
        self.validator = Validator(validation_timeout)
        self.transport = Stdio(argv, timeout=request_timeout)
        self.max_pages, self.max_tools, self.max_catalog_bytes = max_pages, max_tools, max_catalog_bytes
        self.sequence = 0
        self.context = {"method": None, "requestId": None, "caseId": None, "tool": None}
        self.report = {
            "reportVersion": 1, "protocolVersion": PROTOCOL_VERSION, "schemaSha256": SCHEMA_SHA256,
            "executionMode": mode, "scope": "M2: modern stdio, bounded catalog, explicit cases and reviewed baseline",
            "status": "running", "findings": [], "observations": [], "cases": [],
            "compatibility": {"baselineProvided": False, "assessment": "supplied_cases_and_exact_drift_only",
                              "inputWitnesses": 0, "outputWitnesses": 0, "universalCompatibilityProven": False},
            "coverage": {"requestsExecuted": 0, "requestsSelfValidated": 0, "casesEvaluated": 0,
                         "casesExecuted": 0, "casesSkipped": 0, "toolListPages": 0,
                         "catalogBytes": 0, "baselineTools": 0, "baselineValidInputs": 0,
                         "notImplemented": ["general schema containment", "MRTR continuation", "HTTP", "legacy profiles"]},
        }

    def remaining(self):
        left = self.run_timeout - (time.monotonic() - self.started)
        if left <= 0:
            raise GuardError("RUN_TIMEOUT", "The total local run budget expired.",
                             "Reduce cases or review the run budget; no tool call is retried.")
        self.validator.timeout = min(self.validation_timeout, left)
        return left

    def add_finding(self, error):
        if self.report["findings"] and all(self.report["findings"][-1].get(key) == value for key, value in {
                "ruleId": error.code, "caseId": self.context["caseId"], "requestId": self.context["requestId"]}.items()):
            return
        self.report["findings"].append({"ruleId": error.code, "severity": "error", **self.context,
            "pointer": error.pointer, "summary": error.summary, "remedy": error.remedy, "details": error.details})

    def ensure_valid(self, issues, code, summary, remedy, **details):
        if issues:
            raise GuardError(code, summary, remedy, pointer=issues[0]["instancePointer"],
                             details={"schemaIssues": issues, **details})

    def validate_notification(self, message):
        self.remaining()
        self.ensure_valid(self.validator.definition("ServerNotification", message), "NOTIFICATION_SCHEMA",
                          "A notification violates the pinned schema.", "Use a defined MCP notification.")

    def invoke(self, method, params, *, accept_rpc_error=False):
        self.sequence += 1
        self.context.update(method=method, requestId=self.sequence)
        request_definition, result_definition = DEFINITIONS[method]
        self.remaining()
        outgoing = request(method, self.sequence, params)
        issues = self.validator.definition(request_definition, outgoing)
        if issues:
            raise GuardError("HARNESS_REQUEST_SCHEMA", "The harness generated an invalid MCP request.",
                             "Fix the harness; this is not a server defect.", details={"schemaIssues": issues}, exit_code=2)
        self.report["coverage"]["requestsSelfValidated"] += 1
        timeout = min(self.transport.timeout, self.remaining())
        self.report["coverage"]["requestsExecuted"] += 1
        response = self.transport.exchange(outgoing, timeout=timeout, notification_validator=self.validate_notification)
        self.remaining()
        if "error" in response:
            self.ensure_valid(self.validator.definition("JSONRPCErrorResponse", response), "ERROR_SCHEMA",
                              "The peer JSON-RPC error is malformed.", "Return an integer code and string message.")
            code = response["error"]["code"]
            if code == -32022:
                self.remaining()
                self.ensure_valid(self.validator.definition("UnsupportedProtocolVersionError", response), "ERROR_SCHEMA",
                                  "The version error is malformed.", "Include requested and supported versions.")
                raise GuardError("UNSUPPORTED_PROTOCOL", "The server rejected the pinned protocol version.",
                                 "Use a 2026-07-28 server; no negotiation down occurs.")
            if accept_rpc_error:
                return PeerError(code)
            raise GuardError("PEER_RPC_ERROR", "The server returned a JSON-RPC error for this request.",
                             "Inspect the server protocol error path.", details={"peerCode": code})
        result = response["result"]
        if not isinstance(result, dict):
            raise GuardError("RESULT_SCHEMA", "The result must be an object.", "Return the pinned method result.", pointer="/result")
        normalized = copy.deepcopy(result)
        if "resultType" not in result:
            raw_issues = self.validator.definition(result_definition, result)
            normalized["resultType"] = "complete"
            self.report["observations"].append({"ruleId": "RESULT_TYPE_DEFAULT", **self.context,
                "pointer": "/result/resultType", "source": BASE_SOURCE,
                "summary": "Absent resultType accepted as complete by the required compatibility default.",
                "rawSchemaIssues": raw_issues, "affectsExitCode": False})
        kind = normalized["resultType"]
        if kind == "input_required" and method == "tools/call":
            result_definition = "InputRequiredResult"
        elif kind != "complete":
            raise GuardError("RESULT_TYPE", "The server returned an unrecognized resultType.",
                             "Use complete or a supported core interaction; no extensions are advertised.", pointer="/result/resultType")
        self.remaining()
        self.ensure_valid(self.validator.definition(result_definition, normalized), "RESULT_SCHEMA",
                          "The result violates the pinned method schema.", "Correct the fields identified by schema pointers.")
        if kind == "input_required":
            if "inputRequests" not in normalized and "requestState" not in normalized:
                raise GuardError("RESULT_SCHEMA", "Input-required results need inputRequests or requestState.", "Supply a valid multi-round result.")
            raise GuardError("UNSUPPORTED_INTERACTION", "This valid result requires another input round trip.",
                             "Use a multi-round client; coverage is incomplete.")
        return normalized

    def catalog(self):
        discover = self.invoke("server/discover", {})
        if PROTOCOL_VERSION not in discover["supportedVersions"]:
            raise GuardError("UNSUPPORTED_PROTOCOL", "The server does not advertise the pinned protocol.", "Use a 2026-07-28 server.")
        if "tools" not in discover["capabilities"]:
            raise GuardError("TOOLS_CAPABILITY", "The server does not advertise tools support.", "Select a tool server.")
        tools, cursors, params = {}, set(), {}
        while True:
            if self.report["coverage"]["toolListPages"] >= self.max_pages:
                raise GuardError("PAGE_LIMIT", "The catalog exceeded the page limit.", "Reduce pages or review the bounded limit.")
            listing = self.invoke("tools/list", params)
            self.report["coverage"]["toolListPages"] += 1
            self.report["coverage"]["catalogBytes"] += len(canonical(listing["tools"]).encode("utf-8"))
            if self.report["coverage"]["catalogBytes"] > self.max_catalog_bytes:
                raise GuardError("CATALOG_LIMIT", "Aggregate tool-definition bytes exceeded the limit.", "Reduce the catalog or review its byte budget.")
            for tool in listing["tools"]:
                if tool["name"] in tools:
                    raise GuardError("DUPLICATE_TOOL", "A tool name repeats within or across pages.", "Return one definition per name.")
                tools[tool["name"]] = tool
                if len(tools) > self.max_tools:
                    raise GuardError("TOOL_LIMIT", "The catalog exceeded the tool count.", "Reduce tools or review the bounded limit.")
            if "nextCursor" not in listing:
                break
            cursor = listing["nextCursor"]
            if cursor in cursors:
                raise GuardError("CURSOR_LOOP", "The tool-list cursor repeated.", "Return an advancing cursor or end pagination.")
            cursors.add(cursor)
            params = {"cursor": cursor}
        for tool in tools.values():
            self.context["tool"] = tool["name"]
            for field in ("inputSchema", "outputSchema"):
                if field in tool:
                    self.remaining()
                    self.ensure_valid(self.validator.schema(tool[field]), "TOOL_SCHEMA", "The tool schema is invalid.", "Correct the Draft 2020-12 document.")
        self.context["tool"] = None
        return discover, tools

    def baseline_inputs(self, cases, baseline):
        for case in cases or []:
            if case.get("expect", {"kind": "success"})["kind"] != "success":
                continue
            self.context.update(caseId=case["id"], tool=case["tool"], method=None, requestId=None)
            if case["tool"] not in baseline:
                raise GuardError("CONFIGURATION", "A success case names a tool absent from the baseline.", "Review the baseline and case together.", exit_code=2)
            self.remaining()
            issues = self.validator.instance(baseline[case["tool"]]["inputSchema"], case["arguments"])
            if issues:
                raise GuardError("CONFIGURATION", "A success case was never baseline-valid.", "Provide baseline-valid inputs to establish a regression witness.", details={"schemaIssues": issues}, exit_code=2)
            self.report["coverage"]["baselineValidInputs"] += 1
        self.context.update(caseId=None, tool=None, method=None, requestId=None)

    def evaluate_case(self, case, tools, baseline):
        expect = case.get("expect", {"kind": "success"})
        kind = expect["kind"]
        self.context.update(caseId=case["id"], tool=case["tool"], method="tools/call", requestId=None)
        self.report["coverage"]["casesEvaluated"] += 1
        tool = tools.get(case["tool"])
        if tool is None and kind != "rpc_error":
            raise GuardError("TOOL_REMOVED" if baseline and case["tool"] in baseline else "CASE_TOOL_MISSING",
                             "The supplied case names an unavailable tool.", "Restore the tool or review the case.", details={"witness": "supplied_case"})
        self.remaining()
        if tool and not case.get("allowInvalidArguments", False):
            issues = self.validator.instance(tool["inputSchema"], case["arguments"])
            code = "INPUT_REGRESSION" if baseline and kind == "success" else "INPUT_SCHEMA"
            if issues and code == "INPUT_REGRESSION":
                self.report["compatibility"]["inputWitnesses"] += 1
            self.ensure_valid(issues, code, "Supplied arguments fail the candidate input schema.",
                              "Restore accepted inputs or review consumers; no invalid call was sent.",
                              witness="supplied_case" if code == "INPUT_REGRESSION" else None)
        self.report["coverage"]["casesExecuted"] += 1
        result = self.invoke("tools/call", {"name": case["tool"], "arguments": case["arguments"]}, accept_rpc_error=True)
        observed = "rpc_error" if isinstance(result, PeerError) else "tool_error" if result.get("isError", False) else "success"
        if observed != kind:
            code = "PEER_RPC_ERROR" if kind == "success" and observed == "rpc_error" else "TOOL_EXECUTION_ERROR" if kind == "success" and observed == "tool_error" else "OUTCOME_MISMATCH"
            raise GuardError(code, "The case returned a different error/success mechanism.", "Match the explicit outcome; protocol and tool errors differ.", details={"expected": kind, "observed": observed})
        if kind == "rpc_error":
            if result.code != expect["code"]:
                raise GuardError("RPC_ERROR_CODE", "The peer error code differs from the expected code.", "Review the explicit error assertion.", details={"expectedCode": expect["code"], "observedCode": result.code})
            return observed
        if kind == "tool_error":
            return observed
        if "outputSchema" in tool:
            if "structuredContent" not in result:
                raise GuardError("OUTPUT_SCHEMA", "The tool declares outputSchema but omitted structuredContent.", "Return matching structuredContent.", pointer="/structuredContent")
            self.remaining()
            self.ensure_valid(self.validator.instance(tool["outputSchema"], result["structuredContent"]), "OUTPUT_SCHEMA",
                              "Structured output fails the tool's declared schema.", "Return structuredContent conforming to outputSchema.")
        old = baseline.get(case["tool"]) if baseline else None
        if old and "outputSchema" in old:
            if "structuredContent" not in result:
                self.report["compatibility"]["outputWitnesses"] += 1
                raise GuardError("OUTPUT_REGRESSION", "The candidate omitted baseline structured output.", "Restore output accepted by baseline consumers.", details={"witness": "supplied_case"})
            self.remaining()
            issues = self.validator.instance(old["outputSchema"], result["structuredContent"])
            if issues:
                self.report["compatibility"]["outputWitnesses"] += 1
            self.ensure_valid(issues, "OUTPUT_REGRESSION", "Candidate output is rejected by the baseline schema.",
                              "Restore the previous output or review consumers.", witness="supplied_case")
        if "expectedStructuredContent" in case:
            if "structuredContent" not in result or canonical(result["structuredContent"]) != canonical(case["expectedStructuredContent"]):
                raise GuardError("CASE_EXPECTATION", "Structured output differs from the case expectation.", "Review behavior or the fixture expectation.", pointer="/structuredContent")
        return observed

    def run(self, cases=None, baseline=None):
        exit_code, snapshot, old = 0, None, {}
        try:
            if hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest() != SCHEMA_SHA256:
                raise GuardError("SCHEMA_PROVENANCE", "The vendored schema does not match its pin.", "Restore its exact bytes.", exit_code=2)
            if baseline is not None:
                self.report["compatibility"]["baselineProvided"] = True
                old = validate_snapshot(baseline, self.validator, self.remaining)
                self.report["coverage"]["baselineTools"] = len(old)
                self.baseline_inputs(cases, old)
            self.transport.open()
            discover, tools = self.catalog()
            snapshot = {"snapshotVersion": 1, "protocolVersion": PROTOCOL_VERSION, "schemaSha256": SCHEMA_SHA256,
                        "executionMode": self.report["executionMode"],
                        "serverInfo": discover.get("_meta", {}).get("io.modelcontextprotocol/serverInfo"),
                        "tools": [tools[name] for name in sorted(tools)]}
            if len(json.dumps(snapshot, indent=2, ensure_ascii=True).encode("utf-8")) + 1 > MAX_FRAME:
                raise GuardError("SNAPSHOT_LIMIT", "The formatted catalog exceeds the readable snapshot limit.", "Reduce the catalog; snapshot inputs are bounded to 1 MiB.")
            if baseline is not None:
                self.report["findings"].extend(drift_findings(old, tools))
            for case in cases or []:
                try:
                    observed = self.evaluate_case(case, tools, old)
                    self.report["cases"].append({"caseId": case["id"], "tool": case["tool"], "status": "pass", "observedOutcome": observed})
                except GuardError as error:
                    if error.code not in CASE_FAILURES:
                        raise
                    self.add_finding(error)
                    self.report["cases"].append({"caseId": case["id"], "tool": case["tool"], "status": "fail"})
        except GuardError as error:
            exit_code = error.exit_code
            self.add_finding(error)
        except OSError:
            exit_code = 2
            self.add_finding(GuardError("LOCAL_IO", "A local file or process operation failed.", "Check the scoped checkout and runtime.", exit_code=2))
        finally:
            self.transport.close()
            if self.transport.process:
                try:
                    self.transport.drain_after_close(self.validate_notification)
                except GuardError as error:
                    self.add_finding(error)
                    for completed in self.report["cases"]:
                        if completed["caseId"] == self.context["caseId"]:
                            completed["status"] = "fail"
                if not self.transport.cleanup["directChildExited"]:
                    self.add_finding(GuardError("CLEANUP_FAILURE", "The direct server child did not exit.", "Inspect it before running again."))
            evaluated = {case["caseId"] for case in self.report["cases"]}
            for case in cases or []:
                if case["id"] not in evaluated:
                    status = "fail" if case["id"] == self.context["caseId"] else "skipped"
                    self.report["cases"].append({"caseId": case["id"], "tool": case["tool"], "status": status})
            self.report["coverage"]["casesSkipped"] = sum(c["status"] == "skipped" for c in self.report["cases"])
            if not exit_code and self.report["findings"]:
                exit_code = 1
            has_error = any(f["severity"] == "error" for f in self.report["findings"])
            self.report.update(status="fail" if has_error else "review_required" if exit_code else "pass",
                               exitCode=exit_code, elapsedMs=round((time.monotonic() - self.started) * 1000, 3),
                               cleanup=self.transport.cleanup)
        return exit_code, self.report, snapshot if exit_code == 0 else None
