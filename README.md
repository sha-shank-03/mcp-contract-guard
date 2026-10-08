# MCP Contract Guard

[![CI](https://github.com/sha-shank-03/mcp-contract-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/sha-shank-03/mcp-contract-guard/actions/workflows/ci.yml)

Open-source Apache-2.0 project. [Project context](docs/PROJECT_CONTEXT.md) · [Independent local verification](docs/INDEPENDENT_VERIFICATION.md) · [Contributing](CONTRIBUTING.md)

A small developer CLI for checking a local MCP tool server before an agent consumes its outputs. It supports MCP **2026-07-28**, bounded stdio discovery, reviewed baselines, exact schema drift, supplied-case regression witnesses, explicit error outcomes, and offline snapshot diff. It uses no model or paid API.

The bundled server is a **deterministic mock**. It exchanges real local JSON-RPC messages, adds two integers, and can deliberately return the wrong output type. This demonstration is not a live model evaluation or a production integration.

## Quickstart on Windows

Run from this repository in PowerShell with Python 3.11 available through `py`:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: -r requirements.lock
.\.venv\Scripts\python.exe -m mcp_contract_guard --help
$guardPython = (Resolve-Path -LiteralPath '.\.venv\Scripts\python.exe').Path
$guardServer = (Resolve-Path -LiteralPath '.\examples\faulty_server.py').Path
& $guardPython scripts\demo.py --out-dir work\demo
```

Dependency setup needs package access or a prepared wheelhouse. Everything below runs offline after setup. No activation script or machine-wide install is needed. Local evidence uses Python **3.11.9, Windows x64**; the prepared CI pins that exact interpreter on Windows/Linux x64. Confirm your installed version with `& $guardPython --version`.

Expected demo result: **exit 0** and `DEMO PASS: 15 scenarios asserted`. It verifies intended fault exits, concrete witnesses, review-only drift, error mechanisms, pagination, zero-request offline diff, baseline preservation, and direct-child cleanup. Reports and exact CLI receipts are saved in the chosen directory. That directory must be new; subsequent runs can use `--out-dir work\demo-2`. An existing directory is preserved and returns demo exit 2. Python optimization does not disable these checks.

## POSIX checkout quickstart

Use an installed CPython 3.11 interpreter on Linux x86_64, then run from the checkout root:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install --require-hashes --only-binary=:all: -r requirements.lock
guard_python="$(pwd -P)/.venv/bin/python"
guard_server="$(pwd -P)/examples/faulty_server.py"
"$guard_python" -m mcp_contract_guard --help
"$guard_python" scripts/demo.py --out-dir work/demo
```

Linux is **prepared but not locally executed**. The native dependency lock covers Windows amd64 and Linux x86_64 CPython 3.11, not macOS/ARM/other Python versions. After bootstrap the demo uses only local fixtures and saved snapshots. For manual commands below, use `"$guard_python"` in place of `& $guardPython` and `"$guard_server"` in place of `$guardServer` on POSIX.

## Manual checks in PowerShell

Keep the absolute interpreter/server variables from setup. An absolute interpreter path avoids Windows subprocess lookup ambiguity.

Capture a validated catalog snapshot without calling any tools:

```powershell
& $guardPython -m mcp_contract_guard snapshot --out work\baseline.json --report work\snapshot-report.json --execution-mode local_mock_stdio -- $guardPython $guardServer --mode healthy
```

Expected: `PASS ... exit=0`; `work\baseline.json` contains the `sum` tool and scalar integer output schema. Run the supplied success case:

```powershell
& $guardPython -m mcp_contract_guard check --cases examples\cases.json --report work\healthy.json --execution-mode local_mock_stdio -- $guardPython $guardServer --mode healthy
```

Expected: exit **0**, one passing case, three self-validated requests, and `cleanup.directChildExited: true`. Then exercise the intentional fault:

```powershell
& $guardPython -m mcp_contract_guard check --cases examples\cases.json --report work\broken.json --execution-mode local_mock_stdio -- $guardPython $guardServer --mode bad-output
$LASTEXITCODE
```

Expected: exit **1**, `OUTPUT_SCHEMA case=sum-normal /`, and an action to return structured content matching the declared schema. `/` is the console display for the root JSON pointer `""`; the JSON report keeps the actual pointer and schema keyword `type`. The intentional failure is a successful demonstration of detection.

The normative compatibility default for an omitted `resultType` has a dedicated mock mode:

```powershell
& $guardPython -m mcp_contract_guard check --cases examples\cases.json --report work\fallback.json --execution-mode local_mock_stdio -- $guardPython $guardServer --mode missing-result-type
```

Expected: exit **0**, with three non-failing `RESULT_TYPE_DEFAULT` observations containing the raw schema issues. The parsing view uses `complete`; other malformed fields still fail.

Run the targeted test modules:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_m1*.py' -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_m2_contracts.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_m2_wire.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_m2_preservation.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_demo.py -v
.\.venv\Scripts\python.exe -m pip check
```

Use the same module commands with the POSIX venv interpreter. No packaging backend or console-script installation is required.

## Use your own server and cases

Place the executable and literal arguments after `--`. The harness uses `shell=False`. Only explicitly named case tools are invoked; snapshot calls discovery/list only. The server runs with your user's permissions. This is not process isolation.

The case format is deliberately small:

```json
{
  "caseVersion": 1,
  "protocolVersion": "2026-07-28",
  "cases": [
    {"id": "sum-normal", "tool": "sum", "arguments": {"a": 2, "b": 3}, "expectedStructuredContent": 5}
  ]
}
```

`expectedStructuredContent` is optional. When supplied, the checker compares canonical JSON including its serialized numeric representation. The default outcome is success for compatibility with M1 cases. Arguments must satisfy the candidate input schema before a normal call is sent. Successful results must have valid content and, when `outputSchema` exists, matching `structuredContent`. Reports contain diagnostic paths and categories without raw case values, tool output values, or stderr text. Snapshots necessarily contain public tool definitions; review them before storing them.

`snapshot` and `check` accept `--report`, `--request-timeout`, `--validation-timeout`, `--run-timeout`, `--execution-mode`, `--max-pages`, `--max-tools`, and `--max-catalog-bytes`. Defaults are 10 pages, 1000 tools, and 1 MiB of aggregate canonical tool-definition bytes. Saved formatted snapshots must fit the same 1 MiB input bound. Durations are finite positive seconds, up to 60; defaults are 2, 2, and 30 seconds. `local_mock_stdio` is a caller-supplied fixture label, not verified identity.

Exit **0** means the executed supported checks passed. Exit **1** means a detected server/case failure, resource limit, or unsupported interaction prevented a pass. Exit **2** means invocation, configuration, or local harness setup failed. Inspect JSON `coverage`, `findings`, `observations`, and `cleanup`. A failing snapshot never replaces its output file with an invalid catalog; an existing file may still represent an earlier successful run.

Every output/report must be distinct from every case, baseline, and diff input and from other destinations. Normalized relative/absolute names, Windows case aliases, and existing same-file aliases are checked before launch and again before writing. A collision exits **2**, preserves existing bytes, and prints its configuration error without writing over a protected file. Input reads stop after at most **1 MiB plus one byte**; exactly 1 MiB is allowed and a larger file is rejected before server launch.

## Baseline checks, error cases, and offline diff

Capture and review `work\baseline.json` with the snapshot command above. Then consume it explicitly:

```powershell
& $guardPython -m mcp_contract_guard check --baseline work\baseline.json --cases examples\cases.json --report work\input-witness.json --execution-mode local_mock_stdio -- $guardPython $guardServer --mode input-regression
& $guardPython -m mcp_contract_guard check --baseline work\baseline.json --cases examples\cases.json --report work\output-witness.json --execution-mode local_mock_stdio -- $guardPython $guardServer --mode output-regression
& $guardPython -m mcp_contract_guard check --baseline work\baseline.json --cases examples\cases.json --report work\review-only.json --execution-mode local_mock_stdio -- $guardPython $guardServer --mode schema-drift-only
```

All three intentionally exit **1**. The first proves that supplied baseline-valid arguments are rejected by the candidate schema (`INPUT_REGRESSION`), without sending that invalid call. The second observes a candidate-valid string output rejected by the old integer schema (`OUTPUT_REGRESSION`). Each also records separate `SCHEMA_DRIFT` review findings. The third passes the supplied case but returns `review_required`: an optional property changed, and no incompatibility witness was established. Arbitrary schema drift is not a proof of incompatibility. Passing supplied cases is not a general compatibility proof.

Cases may declare `"expect": {"kind": "success"}`, `"expect": {"kind": "tool_error"}`, or `"expect": {"kind": "rpc_error", "code": -32602}`. Error mechanisms and integer codes must match. An intentional negative input needs `"allowInvalidArguments": true` and an error expectation; this never bypasses validation of the MCP request itself. Success cases used with a baseline must first satisfy its input schema; otherwise configuration exits **2** before launch. Output-schema checks apply to successful results; execution errors are checked as valid error results instead.

```powershell
& $guardPython -m mcp_contract_guard check --cases examples\error-cases.json --report work\errors.json --execution-mode local_mock_stdio -- $guardPython $guardServer --mode healthy
& $guardPython -m mcp_contract_guard check --cases examples\shape-cases.json --report work\pages.json --execution-mode local_mock_stdio -- $guardPython $guardServer --mode paged
& $guardPython -m mcp_contract_guard diff work\baseline.json work\baseline.json --report work\diff.json
```

Expected exits are **0/0/0**: explicit success/tool-error/protocol-error cases, two pages with scalar/array/object results, and identical offline snapshots. Compare with another explicitly captured candidate snapshot to see drift. `diff` accepts `--report`, `--validation-timeout`, and `--run-timeout`, never launches a server, and labels execution `offline_snapshot_diff`. A changed snapshot exits **1** with review findings, not a compatibility verdict. Neither check nor diff writes a baseline.

Additional mock modes cover cursor loops, duplicate tools/IDs, malformed JSON/content, peer/tool errors, unsupported revisions, silent timeout, exit, and valid unsupported `input_required`. Protocol/framing faults abort and mark remaining cases skipped; individual input/output/outcome assertions collect failures and continue to the next case without retries. No automatic baseline acceptance or recapture occurs.

## Scope and contribution

The official [MCP Inspector](https://github.com/modelcontextprotocol/inspector) and [conformance suite](https://github.com/modelcontextprotocol/conformance) already provide inspection and protocol tests. This project focuses on project-owned contract baselines/cases, review-only drift, concrete witnesses, bounded failure diagnostics, and inspectable evidence. It is not a full conformance replacement.

There is no HTTP/OAuth, legacy handshake fallback, MRTR continuation, subscription/task support, general JSON Schema compatibility proof, replay, retry, or security certification. A passing run proves only the executed cases in the supported profile. Resource limits protect this harness's selected paths; they do not establish server security.

The [prepared workflow](.github/workflows/ci.yml) uses read-only checkout, verified action commit pins, Python 3.11.9, two Windows/Linux jobs with ten-minute limits, hash-locked wheels, and the asserting demo. It needs no configured secrets, paid APIs, deployment, or publication step. Setup uses the network; contract tests run locally. **Hosted CI and Linux execution remain unexecuted**; no passing CI badge is claimed. [CI provenance and limits](docs/CI.md) explain the preparation.

See [CLI/config/report reference](docs/REFERENCE.md), [architecture](docs/ARCHITECTURE.md), [execution evidence](docs/EVIDENCE.md), [historical M2 evidence](docs/EVIDENCE-M2.md), [dependency attribution](docs/DEPENDENCIES.md), and [accepted plan](PLAN.md). Original code is Apache-2.0; the vendored schema retains its [full upstream notice](vendor/mcp/2026-07-28/LICENSE).

## Get the source

```sh
git clone https://github.com/sha-shank-03/mcp-contract-guard.git
cd mcp-contract-guard
```

Follow the quickstart above for runtime/dependency setup. Demos use fictional/mock data; initial dependency setup, where required, is separate from offline execution.
