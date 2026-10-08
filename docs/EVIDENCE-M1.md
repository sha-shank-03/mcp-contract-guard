# M1 execution evidence

Recorded **2026-10-07** on this Windows HP using Python **3.11.9**. This is the accepted first slice, ready for independent main review. All server execution below used deterministic local fixtures. No model, paid API, live account, publication, or deployment was used.

The main's independent review subsequently found output alias overwrite and an unbounded case-file read. Those M1 defects are corrected; [correction evidence](EVIDENCE-M1-CORRECTIONS.md) records the receipt-based reproduction, byte-preservation/prelaunch tests, actual read bound, **18-test** rerun, and four rerun mock scenarios. Original observations below are retained as history; current CLI reports were refreshed after correction.

## Actual commands and observations

Commands ran from `C:/Users/shash/Documents/CodexPortfolios/agentic-ai-2026-10-07/mcp-contract-guard`.

| Executed command/check | Observed result |
| --- | --- |
| `py -3.11 --version` | Python 3.11.9, exit 0 |
| `py -3.11 work/bootstrap_m1.py` | Exact schema digest verified, 181474 bytes, six pinned runtime dependencies; full upstream notice and source provenance saved |
| `py -3.11 -m venv .venv` | Scoped environment created, exit 0 |
| `.\.venv\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: -r requirements.lock` | Installed the six exact pins using wheels, exit 0; no source builds |
| `.\.venv\Scripts\python.exe -m pip check` | `No broken requirements found.`, exit 0 |
| `.\.venv\Scripts\python.exe -m mcp_contract_guard --help` | Displays `snapshot` and `check`, exit 0 |
| `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`, initial run | 12 tests; one oversized-frame diagnostic failed (`SERVER_EXIT` instead of `FRAME_LIMIT`); the remaining tests passed |
| Same unittest command after correcting the reader/EOF race and adding enum-data coverage | **13 tests passed**, exit 0; runner reported 18.163 seconds on that execution |
| `.\.venv\Scripts\python.exe work/verify_m1.py` | Ran the four CLI scenarios below, asserted actual exit codes/diagnostics/cleanup, saved raw command argv/stdout/stderr and reports; exit 0 |
| `.\.venv\Scripts\python.exe -m compileall -q mcp_contract_guard examples tests` | Exit 0 |
| Installed distribution notice inventory using `importlib.metadata` | All six pins matched; each distribution included the notice listed in DEPENDENCIES.md |
| PowerShell `Get-Process -Id` checks against the four saved server PIDs | None still present at check time; saved in `docs/evidence/m1/process-check.json` |

The first run's failing assertion was retained in this account rather than omitted. The transport now waits for the reader to inspect buffered bytes and checks its specific fault before reporting EOF. The test expectation was unchanged. Tests were rerun because code changed. A subsequent acceptance run used the final code.

`git diff --check` returned 0 while the new deliverables were untracked; this did not validate untracked source and is not counted as a substantive source check. No lint, type checker, or coverage percentage is claimed.

## Reproducible CLI evidence

[commands.json](evidence/m1/commands.json) contains the exact subprocess argv, working directory, timestamp, environment, expected/observed exit codes, stdout, and stderr. Use the equivalent checkout-relative commands in README to reproduce them.

| Local mock scenario | Actual exit | Evidence |
| --- | --- | --- |
| Healthy catalog snapshot | 0 | [snapshot report](evidence/m1/snapshot.json), [catalog snapshot](../examples/baseline.json) |
| Healthy scalar `sum-normal` call | 0 | [healthy report](evidence/m1/healthy.json): one case, three executed/self-validated requests, no findings |
| Intentional bad scalar output | 1 | [bad-output report](evidence/m1/bad-output.json): `OUTPUT_SCHEMA`, case `sum-normal`, root instance pointer, `/type` schema pointer, action provided |
| Missing resultType fallback | 0 | [fallback report](evidence/m1/missing-result-type.json): three `RESULT_TYPE_DEFAULT` observations with raw-schema issues; no failing finding |

Every saved CLI report observed `directChildExited: true` and `readerThreadsStopped: true`, without forced termination for these cooperative fixtures. Separate timeout tests exercise forced cleanup. Timing fields are individual observed local runs, not a performance benchmark. The saved baseline is synthetic fixture data; M1 does not compare future candidates against it.

The tests additionally verified malformed JSON, response ID type correlation, result/error exclusivity, oversized frames, unexpected exit, finite request timeout with skipped case coverage, stderr draining, exact schema provenance, all three outgoing request definitions and missing required request metadata, local references, blocked external references, killable pathological regex validation, strict non-finite/duplicate-key rejection, and the distinction between subschemas and `$ref` text inside enum data. Missing resultType acceptance does not hide an unrelated invalid cache field.

## Unexecuted and incomplete checks

Linux runtime/CI, remote GitHub workflows, an installed console package, upstream Inspector/conformance runs, production server interoperability, credentials/auth, HTTP, legacy profiles, pagination, expected-error assertions, baseline drift/compatibility analysis, and broader M2/M3 acceptance have **not** run or are not implemented. No security audit, general compatibility proof, model evaluation, or benchmark result is claimed. Arbitrary descendant containment is not supplied.

The remaining work requires the next bounded assignment. M1 has no packaging backend and no paid call path. Research artifact metadata and exact pins remain in `docs/dependency-provenance.json` and the worker's coordination record. Intermediate bootstrap/evidence scripts live in ignored `work/`; retained evidence and README commands are sufficient to inspect and reproduce this slice.
