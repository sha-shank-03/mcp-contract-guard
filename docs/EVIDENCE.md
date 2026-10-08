# Final local execution evidence

Prepared and executed on **2026-10-08**, Windows x64, CPython **3.11.9**, using the existing repository-local `.venv`. This is the agreed M3 developer review package. Main reported independent acceptance of corrected M1 and M2 before this assignment; whole-repository final acceptance remains pending main's review.

The runtime, original fixtures/tests, exact dependency lock, root license, pinned schema/license/provenance, and historical raw evidence were preserved. M3 adds the asserting portable demo, two demo-gate tests, Windows/POSIX checkout docs, CLI/config/report reference, copied existing distribution notices, and a prepared commit-pinned CI workflow. It adds no runtime dependency, transport/profile, package build, model/provider call, or deployment.

## Actually executed checks

[checks.json](evidence/m3/checks.json) retains exact interpreter/argv/cwd, stdout, stderr, exit codes, environment, and unittest counts/times for the final checks. Commands use the absolute existing `.venv/Scripts/python.exe`; no install or wheel download was repeated during M3.

| Interpreter arguments | Tests | Exit |
| --- | ---: | ---: |
| `-m unittest discover -s tests -p 'test_m1*.py' -v` | 18 | 0 |
| `-m unittest discover -s tests -p test_m2_contracts.py -v` | 11 | 0 |
| `-m unittest discover -s tests -p test_m2_wire.py -v` | 6 | 0 |
| `-m unittest discover -s tests -p test_m2_preservation.py -v` | 2 | 0 |
| `-m unittest discover -s tests -p test_demo.py -v` | 2 | 0 |

**39 tests passed across five separate bounded module runs**, not one aggregate suite invocation or a performance benchmark. These include all accepted M1/M2 tests: strict JSON/framing, request self-validation, omitted resultType compatibility, malformed fields/content/envelopes, ID faults, supported output shapes, explicit error mechanisms/codes, unsupported revision/input_required, pagination limits, remote-reference refusal/local references, worker deadline/kill, timeout/cancellation/no retry, and input/output alias/bounded-read preservation.

The two new gate tests deliberately corrupt known report evidence to ensure unexpected exits/labels, a missing expected fault, and nonzero offline request coverage are rejected. An optimized Python invocation preserves an existing output directory and cannot disable a false demo assertion. This checks the demo's gate, not an added server feature.

Additional actual commands: `--version`; `-m pip check`; `-m compileall -q mcp_contract_guard examples tests scripts`; root/snapshot/check/diff `--help`; and `scripts/demo.py --help`. All exited 0. Pip reported no broken requirements. Current installs remain the six exact runtime pins; no packaging backend or new dependency was installed.

## Fresh asserting demo

Actual outer command from the checkout: `.venv/Scripts/python.exe scripts/demo.py --out-dir docs/evidence/m3/demo`. It returned **0**, printed `DEMO PASS: 15 scenarios asserted; intentional fault exits verified; no model calls.`, and retained [exact CLI receipts](evidence/m3/demo/commands.json) with argv, stdout/stderr, expected/observed exits, coverage, interpreter, platform, and input hashes.

| Scenario | Observed exit | Asserted behavior |
| --- | ---: | --- |
| Snapshot / healthy / fallback | 0 / 0 / 0 | Explicit catalog capture, passing baseline case, three non-failing resultType defaults |
| Bad output | 1 | `OUTPUT_SCHEMA` |
| Input / output witness | 1 / 1 | One concrete witness each; baseline-valid rejected input was not called |
| Review-only drift | 1 | Supplied case passed; review_required; no witness; compatibility not_proven |
| Expected errors / paged shapes | 0 / 0 | Success/tool-error/RPC-error matched; two pages and three shapes |
| Cursor loop / duplicate ID | 1 / 1 | `CURSOR_LOOP` / `DUPLICATE_RESPONSE` |
| Unsupported version / input_required | 1 / 1 | Unsupported protocol / valid unsupported interaction |
| Identical / changed offline diff | 0 / 1 | Zero requests in both; changed schema requires review |

The deliberately failing scenario exits are **expected asserted detections**, not ignored failures. The demo exits 1 for an unexpected gate result and 2 for an existing/unwritable output directory. All comparisons preserved the explicitly captured mock baseline and the deliberately changed candidate copy. Baseline SHA-256 before/after is `f8beb6491403cc905381cb0a98ff0bcb6d785ceb37709a0646872d739fe000e0`. The demo never silently recaptures while checking/diffing.

The 13 stdio scenario reports record direct-child exit and stopped readers; the two diffs launch no child. A separate native Windows `Get-Process -Id` lookup and the PowerShell manual checks are retained in [process-and-literal-checks.json](evidence/m3/process-and-literal-checks.json). These observations establish direct-child cleanup for these mocks, not arbitrary descendant containment or side-effect cancellation.

All protocol exchanges here are **fresh deterministic local_mock_stdio executions**, and diffs are **offline_snapshot_diff**. They are not recorded replay, live production integration, model evaluation, or universal compatibility/conformance/security proof. Reports and the separate CLI receipts keep those labels explicit; raw wire transcripts and tool-output values are not saved in runtime reports.

## Source, notices, and prepared CI

[source-preservation.json](evidence/m3/source-preservation.json) records before/after hashes for existing implementation/fixtures/tests, exact lock/license/schema, and retained historical evidence. [source-manifest.json](evidence/m3/source-manifest.json) identifies the final review package's source/docs/workflow hashes. Files remain local and untracked; an empty git diff check does not validate them.

All six copied runtime notices were byte-compared with the existing installed distributions and their manifest hashes. [Notice manifest](../vendor/licenses/manifest.json), [dependency provenance](dependency-provenance.json), and the [complete schema notice/provenance](../vendor/mcp/2026-07-28/provenance.json) preserve attribution and exact pins. This is a distributed-notice inventory, not an exhaustive embedded-native-dependency license or security audit.

[Prepared CI checks](evidence/m3/prepared-ci-check.json) compare action pins with actual official metadata and inspect the intended permission, interpreter, bounds, wheel-only install, and demo commands. Official action definitions/commits/licenses were actually read; [CI provenance](ci-provenance.json) retains URLs/digests. The five module commands and demo were executed locally. These are static workflow checks, **not GitHub YAML/actionlint validation or hosted CI execution**.

Not executed: Linux/POSIX runtime, hosted GitHub CI, a new bootstrap/install, upstream Inspector/conformance, live production servers/models/providers, packaging, publication/push, deployment, security audit, general schema containment, or performance benchmarks. The prepared Windows/Linux CI is bounded, read-only at the repository permission level, and uses no configured account secrets or paid APIs. No remote workflow was dispatched. Main still owns final independent acceptance.

Historical records: [M1](EVIDENCE-M1.md), [M1 corrections](EVIDENCE-M1-CORRECTIONS.md), and [M2](EVIDENCE-M2.md) retain their original execution/review context and were not rewritten to invent later results.
