# M2 local execution evidence

Recorded 2026-10-07 on Windows with the existing Python 3.11.9 venv. Corrected M1 was independently accepted by main before this assignment. This slice implements M2 only: bounded pagination, reviewed baseline checking, offline diff, supplied-case witnesses, explicit error outcomes, wire faults, and extended file preservation. CI and M3 remain pending assignment.

## Tests actually executed

Commands below ran from this repository with `.venv/Scripts/python.exe`. These were separate targeted module runs, **37 tests in total**, rather than one aggregate suite invocation. Times are unittest's observed output, not a performance benchmark.

| Command after the interpreter | Tests | Exit | Reported seconds |
| --- | ---: | ---: | ---: |
| `-m unittest discover -s tests -p 'test_m1*.py' -v` | 18 | 0 | 25.650 |
| `-m unittest discover -s tests -p test_m2_contracts.py -v` | 11 | 0 | 57.569 |
| `-m unittest discover -s tests -p test_m2_wire.py -v` | 6 | 0 | 35.095 |
| `-m unittest discover -s tests -p test_m2_preservation.py -v` | 2 | 0 | 3.392 |

The contract module was rerun after adding the offline pin check. Its empty-catalog test replaces the schema reader with corrupt bytes and an I/O exception, expecting configuration failures rather than a false pass. Earlier contract runs had ten tests; the table records the final eleven-test run. Full test stdout was displayed in the worker chat; [verification-summary.json](evidence/m2/verification-summary.json) records the commands and observed results, not a retained raw stdout transcript.

Assertions cover:

- Baseline-valid arguments rejected by the candidate input schema produce an `INPUT_REGRESSION` witness without an invalid tool call. Candidate-valid output rejected by the old schema produces `OUTPUT_REGRESSION`. Exact drift stays a separate review finding. An optional property change passes its case but returns `review_required`, with no witness or universal compatibility claim. Baseline-invalid success cases exit 2 before launch.
- Two-page discovery and scalar/array/object structured output; duplicate names, repeated cursors, page/tool/aggregate-byte limits; removed tools; unchanged and changed offline snapshots with zero requests; baseline bytes preserved during check/diff.
- Explicit success, tool-error, and exact integer RPC-error-code outcomes. Wrong mechanisms and codes fail. Boolean codes are invalid configuration. Individual assertion failures collect without retry; protocol failures abort remaining coverage.
- Independently authored raw frames cover invalid UTF-8, a missing newline, missing/malformed content, wrong and duplicate IDs (including the final response), both/neither result/error envelopes, malformed errors, unknown result type, and early process exit. Both unsupported-revision mechanisms fail without fallback. A valid `input_required` result passes its wire schema and becomes unsupported coverage.
- The silent fixture writes an independent request audit. It observes one tool call, modern per-request metadata, and cancellation with that call's ID; no retry occurs. This proves receipt by this cooperative fixture, not cancellation of arbitrary server side effects.
- Fifteen real M2 CLI alias subcases cover baseline/check and both diff inputs against report destinations using identical, relative/absolute, normalized, hard-link, and Windows case aliases. They preserve existing bytes, exit 2, and leave an independent launch marker absent. M1 preservation/bounded-read tests also pass. The supported 1000-tool CLI cap is rejected before launch when exceeded.
- M1's remote-reference refusal, local-reference support, validation-worker deadline/kill, strict JSON, frame bound, stderr drain, protocol pin, resultType fallback, and malformed-field checks remain passing.

## CLI demonstrations actually executed

`work/verify_m2.py` executed **15 CLI scenarios** and asserted their exits, required findings, direct-child cleanup, and baseline preservation. [commands.json](evidence/m2/commands.json) retains each exact argv, cwd, stdout, stderr, expected/observed exit, asserted rule, and coverage. Every listed assertion passed.

| Saved report | Exit | Observed assertion |
| --- | ---: | --- |
| `snapshot.json` | 0 | Explicitly captured the reviewed one-tool mock catalog |
| `healthy.json` | 0 | Baseline check and supplied success case passed |
| `bad-output.json` | 1 | `OUTPUT_SCHEMA` |
| `fallback.json` | 0 | Omitted resultType accepted with observations |
| `input-witness.json` | 1 | `SCHEMA_DRIFT` plus `INPUT_REGRESSION` |
| `output-witness.json` | 1 | `SCHEMA_DRIFT` plus `OUTPUT_REGRESSION` |
| `review-only.json` | 1 | Case passed; drift remained `review_required` |
| `expected-errors.json` | 0 | Success, tool error, and RPC error matched |
| `paged-shapes.json` | 0 | Two pages; three scalar/array/object cases; six requests |
| `cursor-loop.json` | 1 | `CURSOR_LOOP` |
| `duplicate-id.json` | 1 | `DUPLICATE_RESPONSE` |
| `unsupported-version.json` | 1 | `UNSUPPORTED_PROTOCOL` |
| `input-required.json` | 1 | `UNSUPPORTED_INTERACTION` |
| `diff-identical.json` | 0 | Zero requests; unchanged offline snapshots |
| `diff-changed.json` | 1 | Zero requests; review-required exact schema drift |

All reports are in [the M2 evidence directory](evidence/m2/commands.json). The reviewed baseline's before/after SHA-256 in the receipt is identical. A deliberately changed copy was created explicitly for the diff demonstration. Check/diff never recaptured either input.

`work/verify_m1.py` also reran the **four documented M1 examples** after M2: snapshot, healthy check, bad output, and omitted-resultType fallback. Exits were **0/0/1/0**, bad output retained `OUTPUT_SCHEMA`, and fallback retained three non-failing observations. Their [exact argv and results](evidence/m1/commands.json) and reports are refreshed; historical M1 documents retain their original test-run context.

Each of the 17 stdio example reports records direct-child exit and stopped reader threads. A separate Windows `Get-Process -Id` lookup found none of those saved PIDs present at the one-time probe; [process-check.json](evidence/m2/process-check.json) retains the result. This is direct-child evidence, not descendant containment or a persistent monitor. The two diffs launch no child.

`-m compileall -q mcp_contract_guard examples tests` exited 0. `-m pip check` exited 0 with no broken requirements. `git status --short` showed the local files still untracked; therefore the empty `git diff --check` result is not substantive source validation.

## What this evidence establishes

These are fresh deterministic **local mock stdio executions** and **offline snapshot comparisons**, not recorded replay or model execution. Reports expose executed/skipped coverage, separate review findings from concrete supplied-case witnesses, and never claim universal compatibility. Exit 0 is supported executed checks passing; exit 1 includes an observed fault/witness, unsupported coverage, or unreviewed drift; exit 2 is configuration/local setup failure. No new dependency or protocol/transport profile was added.

Not executed: Linux runtime or CI, upstream Inspector/conformance, live production servers, model/provider calls, security audit, broad compatibility proof, performance benchmarking, packaging, publication, deployment, or M3 release work. Main's independent M2 review is still required. Resource and file preflight bounds do not provide process isolation, an atomic filesystem guarantee, or server security certification.
