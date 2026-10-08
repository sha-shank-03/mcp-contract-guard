# CLI, configuration, and report reference

Run `python -m mcp_contract_guard` from the checkout with the installed pinned dependencies. Use an absolute server executable after `--`, especially on Windows. Arguments are literal argv with `shell=False`; there is no command-string shell expansion. Paths in options are resolved relative to the current directory.

## Operations and exits

| Operation | Required inputs | Effect |
| --- | --- | --- |
| `snapshot --out FILE -- EXE ARGS...` | Explicit stdio server argv | Discover/list/validate; save a catalog only on success; never invoke a tool |
| `check --cases FILE [--baseline FILE] -- EXE ARGS...` | Cases and explicit server argv; optional reviewed snapshot | Discover/list/validate; evaluate supplied cases; never replace baseline/cases |
| `diff BASELINE CANDIDATE` | Two pinned snapshots | Offline exact input/output schema and tool-name comparison; no server or replay |

| Exit | Meaning |
| ---: | --- |
| 0 | Executed supported checks passed; not universal compatibility/conformance/security proof |
| 1 | Server/case fault, concrete witness, resource/unsupported coverage, or unreviewed exact drift |
| 2 | Invalid invocation/configuration, schema-pin/local I/O/setup failure, or generated-request defect |

Review findings alone yield JSON `status: review_required`, exit 1, even when every supplied case passes. Error findings yield `fail`; no findings yield `pass`. Argument-parser errors return 2 on stderr before report creation. An invalid output/report alias is printed but never saved into that collided path. A failed snapshot preserves an existing catalog; that file may describe an earlier run.

## Options

| Option | Operations | Default | Accepted values |
| --- | --- | --- | --- |
| `--report FILE` | All | Console only | Distinct output destination; reports include failures when configuration permits a safe write |
| `--validation-timeout SECONDS` | All | 2 | Finite, greater than 0, at most 60; per supervised validation worker |
| `--run-timeout SECONDS` | All | 30 | Finite, greater than 0, at most 60; checked at runtime boundaries including baseline validation |
| `--request-timeout SECONDS` | snapshot/check | 2 | Finite, greater than 0, at most 60; one request's exchange deadline |
| `--max-pages N` | snapshot/check | 10 | Integer 1–1048576; run budget/frame bounds still apply |
| `--max-tools N` | snapshot/check | 1000 | Integer 1–1000; format has a fixed 1000-tool cap |
| `--max-catalog-bytes N` | snapshot/check | 1048576 | Integer 1–1048576; total canonical tool-definition bytes |
| `--execution-mode LABEL` | snapshot/check | `local_stdio` | `local_stdio` or `local_mock_stdio`; caller label, not identity verification |

Diff fixes its label to `offline_snapshot_diff`. Cleanup can add a bounded interval beyond the run budget. Byte limits and validation deadlines are harness policies, not protocol mandates. See [architecture](ARCHITECTURE.md) for fixed framing, queue, notification, structure, worker, and case limits.

All JSON inputs are strict UTF-8, at most 1 MiB, with unique object keys and finite numbers. Reads stop after the bound plus one sentinel byte. Every output must differ from all inputs and other outputs. Normalized paths, existing hard links, symlinks resolved by path normalization, and Windows case aliases are checked before launch and before writes. This preflight is not an atomic guarantee under concurrent filesystem replacement.

## Case document version 1

Root keys are exactly `caseVersion`, `protocolVersion`, and `cases`. Use integer 1, exact `2026-07-28`, and 1–100 cases. Each case requires a unique nonempty string `id` of at most 128 characters, a nonempty string `tool`, and object `arguments`. Unknown keys are rejected.

```json
{
  "caseVersion": 1,
  "protocolVersion": "2026-07-28",
  "cases": [
    {"id": "normal", "tool": "sum", "arguments": {"a": 2, "b": 3},
     "expect": {"kind": "success"}, "expectedStructuredContent": 5},
    {"id": "negative", "tool": "sum", "arguments": {"a": "invalid", "b": 3},
     "allowInvalidArguments": true, "expect": {"kind": "tool_error"}},
    {"id": "missing", "tool": "absent", "arguments": {},
     "expect": {"kind": "rpc_error", "code": -32602}}
  ]
}
```

Omitting `expect` means success. Success/tool_error accepts only `kind`; rpc_error also requires exactly one integer `code` (booleans are rejected). `expectedStructuredContent` is optional for success only and may be any JSON value. Comparison sorts object keys but preserves array order and serialized numeric representation. `allowInvalidArguments` is boolean, defaults false, and may be true only with an error expectation. It allows a deliberate negative argument test; MCP request validation still applies. An unlisted tool may be called only for an explicit rpc_error case.

With a baseline, every success case must first satisfy its baseline tool's input schema. Invalid baseline cases are configuration errors before launch, not fabricated input witnesses. Error cases do not establish success compatibility witnesses. Output-schema checks apply to successful results; tool/RPC errors must still be valid wire results and match their explicit mechanism/code. Local case assertion failures are collected; fatal wire/protocol/schema-prerequisite faults abort the session. No call is retried.

## Snapshot document version 1

The snapshot records `snapshotVersion: 1`, exact `protocolVersion`, exact `schemaSha256`, an execution label, optional server information, and a unique-name `tools` array. The baseline reader validates the pin, permitted root keys, bounded tool count, each tool definition, and its schemas. Snapshot `serverInfo` is descriptive metadata, not identity verification. Capture/review is explicit; check/diff never recapture or auto-accept drift.

Diff compares tool-name membership and exact `inputSchema`/`outputSchema`. Object key order is ignored; array order is retained. Descriptions and annotations are outside that comparison. No general schema containment algorithm is implemented. New/removed tools generate `CATALOG_DRIFT`; changed schemas generate `SCHEMA_DRIFT`, severity `review`, compatibility `not_proven`, witness null. Findings may include up to 100 changed pointers; raw schema values are not embedded.

## JSON reports

Reports use `reportVersion: 1`. Consumers should tolerate fields absent on early configuration/local failures and inspect `exitCode` rather than assuming coverage/cleanup were populated. Console root-pointer display `/` corresponds to JSON's actual empty pointer `""`.

| Field | Interpretation |
| --- | --- |
| `protocolVersion`, `schemaSha256` | Exact supported schema pin |
| `executionMode` | Live stdio caller label or fixed offline snapshot diff |
| `status`, `exitCode`, `elapsedMs` | Gate result and local elapsed time where available |
| `findings` | Rule ID, severity where available, summary/remedy, method/request/case/tool context, pointer and bounded diagnostic details |
| `observations` | Non-failing information, including `RESULT_TYPE_DEFAULT` and raw strict-schema issues for an omitted resultType |
| `cases` | Evaluated case ID/tool/status; successful matched cases include observed mechanism; skipped coverage is explicit |
| `compatibility` | Limited assessment, optional baseline flag, input/output witness counts, `universalCompatibilityProven: false` |
| `coverage` | Actual attempted execution/evaluation counts and incomplete/nonimplemented scope |
| `cleanup` | Direct-child PID/exit, forced termination, stopped readers, stderr byte count, cancellation attempt/write completion; absent for offline diff |

Live coverage includes `requestsExecuted` (exchange attempts, not proof of delivered bytes or completed side effects), `requestsSelfValidated`, `casesEvaluated`, `casesExecuted` (call attempts), `casesSkipped`, `toolListPages`, `catalogBytes`, `baselineTools`, and `baselineValidInputs`. Offline coverage has zero requests/calls/pages and baseline/candidate tool counts. A counter is not proof that a semantic operation completed; consult case findings and cleanup.

`INPUT_REGRESSION` uses baseline-valid supplied arguments rejected by the candidate input schema; no invalid call is sent. `OUTPUT_REGRESSION` uses successful candidate data rejected by the baseline schema (or missing required baseline structured output). Both include supplied-case witness classification. Candidate-invalid output stays `OUTPUT_SCHEMA`. Witness counts cover these observed cases only.

Selected failure rules: `WIRE_JSON`/`TRUNCATED_FRAME`/`WIRE_ENVELOPE`, `RESPONSE_ID`/`DUPLICATE_RESPONSE`, `ERROR_SCHEMA`/`RESULT_SCHEMA`, `INPUT_SCHEMA`/`OUTPUT_SCHEMA`/`CASE_EXPECTATION`, `OUTCOME_MISMATCH`/`RPC_ERROR_CODE`, `PEER_RPC_ERROR`/`TOOL_EXECUTION_ERROR`, `CURSOR_LOOP`/`DUPLICATE_TOOL`/`PAGE_LIMIT`/`TOOL_LIMIT`/`CATALOG_LIMIT`/`SNAPSHOT_LIMIT`, `REQUEST_TIMEOUT`/`RUN_TIMEOUT`/`VALIDATION_TIMEOUT`, `SERVER_EXIT`, and `UNSUPPORTED_PROTOCOL`/`UNSUPPORTED_INTERACTION`. Remedies and pointers give the concrete next action. Unsupported input_required is valid wire behavior requiring a client outside this single-round profile.

Runtime reports omit raw arguments, structured output values, stderr text, and wire transcripts. Snapshots contain public tool definitions. The synthetic demo's separate `commands.json` records local CLI argv and console stdout/stderr for inspection; its labels explicitly distinguish fresh mock execution from offline diff and from replay/model execution.
