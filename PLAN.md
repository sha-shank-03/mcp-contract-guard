# MCP Contract Guard: proposed implementation plan

Planning only. Prepared and primary sources retrieved on **2026-10-07**. Implementation requires the main chat's accepted milestone assignment. Repository: `C:/Users/shash/Documents/CodexPortfolios/agentic-ai-2026-10-07/mcp-contract-guard`.

## Problem and user journey

A team upgrades its MCP tool server. A tool gains a required input, changes its output shape, starts returning malformed content, or hangs. Existing agent workflows then fail, while a manual successful call misses the regression. The developer needs a small local CI gate that explains the failed contract, request/case, JSON pointer, expected behavior, and practical next action.

MCP Contract Guard will launch a **user-specified local stdio server**, discover its tool definitions, validate a bounded set of messages and tool schemas against a pinned MCP revision, execute only explicitly supplied cases, and compare the result with a reviewed baseline. There are no model calls. The example is a deterministic **mock MCP server** exchanging real local JSON-RPC messages; it is not an LLM evaluation or a production integration.

Proposed journey:

1. Run `snapshot` against a known-good server. It calls `server/discover` and paginated `tools/list`, validates them, and saves a versioned baseline. It does not invoke tools.
2. Author a small JSON case file with tool name, arguments, expected outcome, and optional expected structured value. Review and commit the baseline and cases together.
3. Run `check` against the candidate server with that baseline and case file. Inspect console diagnostics and a machine-readable JSON report; use the exit code as a CI gate.
4. For deliberate API changes, review the schema differences and explicitly recapture the baseline. The tool never silently updates a baseline.
5. Run `diff` between two saved snapshots without launching a server. This is offline schema comparison, not recorded protocol replay.

Illustrative diagnostic, **proposed rather than observed**: `INPUT_REGRESSION case=sum-normal tool=sum /inputSchema/required: baseline-valid arguments no longer satisfy the candidate schema; restore the accepted input or update consumers and review the baseline.`

## Existing tools and contribution

The official [MCP Inspector](https://github.com/modelcontextprotocol/inspector) already provides web, CLI, and TUI inspection, and documents automated smoke testing. Its inspected source identifies version `2.9.0` at commit `ae865a19178ddf6f375780a02e9c77c4cf4da184`; that is a source observation, not proof that a particular registry tag was installed here.

The official [MCP conformance framework](https://github.com/modelcontextprotocol/conformance/blob/main/README.md) already tests client/server protocol behavior, validates wire schemas, reports checks, and supports revision requirements and expected failures. Its inspected source identifies `0.2.0-alpha.12` at commit `c37eec888e1c6ff140af79987a40008548b7cc5f`. Neither project was installed or executed during planning.

This repository's contribution is the combination of **project-owned tool baselines, developer-authored regression cases, explicit schema drift review, concrete input/output compatibility witnesses, and fault diagnostics** in a compact Python stdio workflow. It complements those existing tools. It will not claim the first MCP validator, complete MCP conformance, general JSON Schema compatibility proof, or verified server security. No code from Inspector or the conformance harness is planned to be copied.

## Supported MVP and non-goals

Supported profile: **MCP `2026-07-28`, stdio, `server/discover`, paginated `tools/list`, and single-round `tools/call`**. Cases support success, tool execution error (`isError: true`), and explicitly expected JSON-RPC error with a specified integer code. Local timeouts and process exits remain harness failures, never synthetic peer JSON-RPC errors.

Required MVP behaviors:

- Check raw UTF-8 newline framing, strict JSON, response ID correlation, one result/error outcome, method-specific result shape, and bounded notifications.
- Send version and client capabilities in `params._meta` on every request, with client identity for debugging. Verify advertised support for the exact pinned revision and the tools capability.
- Validate tool schema documents with JSON Schema Draft 2020-12, including local references and composition within configured limits. Do not automatically fetch external references or read arbitrary referenced files.
- Validate successful structured results against the candidate output schema and, where supplied, the baseline output schema and case expectation.
- Detect tool removals, exact input/output schema drift, baseline-valid inputs rejected by the candidate schema, malformed responses, incorrect error outcomes, deadlines, and unexpected subprocess exit.
- Emit console and JSON reports with stable rule IDs, source/profile, tool/case/request ID, JSON pointers, severity, expected/observed category, remedy, elapsed time, and executed/skipped check counts.
- Provide healthy and deliberately faulty mock modes plus a reproducible demonstration.

Non-goals: HTTP/SSE, OAuth, legacy `initialize` profiles through `2025-11-25`, multi-round sampling/elicitation, subscriptions, tasks/extensions, prompts/resources operations, model-driven case generation, load testing, fuzzing arbitrary executables, live credentials, dashboards, hosted services, or automatic repair. A valid `input_required` result is reported as an unsupported interaction, not malformed protocol. Media/link content can be checked for schema shape; the harness will not fetch, render, or claim to inspect its payload semantics.

## Protocol pin and source decisions

The [official versioning page](https://modelcontextprotocol.io/docs/2026-07-28/learn/versioning) identifies `2026-07-28` as current. Unlike older revisions, [versioning and compatibility](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning) uses per-request metadata rather than initialization. The MVP deliberately refuses to negotiate down to another version; a mismatch yields an actionable `UNSUPPORTED_PROTOCOL` report.

Pin the official generated schema to commit **`271ecc9accafdd9b83a3c869fa67c22953b2af80`**, not a moving branch:

- [Exact JSON schema](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/271ecc9accafdd9b83a3c869fa67c22953b2af80/schema/2026-07-28/schema.json)
- Retrieved size: `181474` bytes.
- SHA-256: `ef70b61f99b6d2e5e3b46863822eab08dff6a45bedc7a08914e0e5b133f40203`.
- [Exact upstream LICENSE](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/271ecc9accafdd9b83a3c869fa67c22953b2af80/LICENSE) describes the Apache-2.0 transition and retained MIT contributions. Preserve the complete notice when vendoring the schema; do not reduce it to an unqualified MIT label. License original project code under Apache-2.0 and distinguish third-party material in attribution.

The [base protocol](https://modelcontextprotocol.io/specification/2026-07-28/basic) defines required metadata, JSON Schema dialect defaults, and no automatic network reference retrieval. It requires result types but also instructs clients to interpret an absent `resultType` as `complete` for older-server compatibility. Preserve the raw strict-schema diagnostic and normalize only the parsing view; do not silently claim the original modern response was schema-valid. The pinned schema is inspected by named `$defs` rather than validated as an unconstrained top-level object.

The [discovery page](https://modelcontextprotocol.io/specification/2026-07-28/server/discover) defines `supportedVersions` and capabilities. The pinned `DiscoverResult` and `ListToolsResult` also require `cacheScope` and `ttlMs`; examples and tests must include them. The [stdio binding](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio) defines framing, cancellation, and shutdown. The [tools page](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) separates peer protocol errors from execution errors and allows structured content to be any JSON value. Include a scalar output in the healthy fixture so an outdated object-only validator cannot pass.

## Architecture and dependencies

Use **Python 3.11**. Its standard library provides CLI parsing, JSON, subprocesses, threads/queues, monotonic clocks, hashing, and unittest. This avoids a Maven wrapper or a Java JSON Schema integration for a narrow wire-testing tool. The user's Java experience is relevant to the architecture, but a second language implementation adds no MVP value.

Components:

1. `cli`: argument/config validation; subcommands `snapshot`, `check`, `diff`; exit codes `0` pass, `1` observed failure or unreviewed schema drift, `2` invalid invocation/local configuration. Unknown dialects or unsupported interactions produce a failing incomplete-coverage finding, never a green pass.
2. `stdio`: `subprocess.Popen(argv, shell=False)`; bounded stdout framing and stderr draining on reader threads; queue-based monotonic deadlines; one request at a time with unique integer IDs; timeout cancellation and deterministic child cleanup. Never retry tool calls automatically.
3. `protocol`: immutable revision/schema provenance; request self-validation; selected response `$defs`; supplemental envelope/result-type semantics; discovery and bounded pagination.
4. `schema`: explicit `Draft202012Validator` and in-memory `referencing.Registry`; default/explicit 2020-12 support only. `format` remains annotation-only, documented in the report. Other dialects are unsupported rather than invalid by definition.
5. `contracts`: versioned canonical tool snapshots and exact drift comparison; validate baseline-valid case inputs against candidate schemas, candidate outputs against baseline output schemas, and selected developer expectations. Report arbitrary schema changes as `SCHEMA_DRIFT/review`, not a mathematical compatibility verdict. For example, adding an optional field is still visible drift; a concrete rejected input is a regression witness. Absence of a witness proves only the supplied cases passed.
6. `report`: stable JSON report format and console rendering. No raw arguments, tool output values, or stderr text in reports by default; diagnostics use categories/pointers and byte counts. Fixture evidence is synthetic. No transcript recorder is needed for the MVP.
7. `examples/faulty_server.py`: deterministic mock `sum` and `echo` tools; healthy, schema-change, malformed JSON, wrong ID, malformed content, bad structured output, JSON-RPC error, tool execution error, timeout, and early-exit modes. Smaller wire fixtures cover pagination loops and bounds.

Only direct runtime libraries: `jsonschema` and its public registry API provider `referencing`. Lock the full dependency closure. No format extras, pytest, HTTP client, MCP SDK, or database. Using raw messages is intentional: SDK parsing may discard or convert precisely the malformed input the tool must diagnose. This is a bounded test harness, not another general MCP client SDK.

| Package | Proposed exact pin | Role | Declared license | Verified artifact for Python 3.11 Windows |
| --- | --- | --- | --- | --- |
| jsonschema | 4.25.1 | Draft 2020-12 validation | MIT | universal wheel |
| referencing | 0.36.2 | Explicit in-memory references | MIT | universal wheel |
| attrs | 25.3.0 | Transitive dependency | MIT | universal wheel |
| jsonschema-specifications | 2025.9.1 | Bundled dialect resources | MIT | universal wheel |
| rpds-py | 0.27.1 | Transitive persistent data structures | MIT | CPython 3.11 `win_amd64` wheel |
| typing-extensions | 4.15.0 | referencing dependency below Python 3.13 | PSF-2.0 | universal wheel |
| setuptools | 80.9.0 | Optional package build backend, not runtime | MIT | universal wheel |

The exact release JSON at `https://pypi.org/pypi/<package>/<version>/json` was actually read for every row on 2026-10-07. Non-yanked wheel availability, Python requirements, dependency markers, URLs, and SHA-256 values are recorded in the worker's `research-artifacts.json`. A small rpds Windows wheel was inspected in memory and contained `rpds_py-0.27.1.dist-info/licenses/LICENSE`. No install or build was performed. Do not imply that metadata inspection is a completed dependency audit. Preserve distributed license files and inventory bundled notices during packaging.

Use root-level `mcp_contract_guard/` so `python -m mcp_contract_guard` works from the checkout after dependency setup. A standard pyproject may add a console entry point in milestone 3. Lockfiles will include universal wheels and the supported Windows/Linux Python 3.11 native wheel hashes; require binary wheels to avoid introducing Rust builds. [jsonschema 4.25.1 validation documentation](https://python-jsonschema.readthedocs.io/en/v4.25.1/validate/) supports `check_schema` and instance validation; its [referencing documentation](https://python-jsonschema.readthedocs.io/en/v4.25.1/referencing/) documents explicitly supplied registries without automatic retrieval.

## Reliability and precise bounds

Proposed defaults: request timeout 2 seconds, total run budget 30 seconds, maximum frame 1 MiB, maximum 10 tool-list pages/1000 tools, bounded reader queue/notification count, schema depth 32 and node count 10000. Stderr is drained continuously and retained only as a bounded byte count. Resource-limit findings are harness policy, not claims that the peer violates MCP.

Schema validation needs a wall-clock limit as well as structural limits: local cyclic references or pathological regexes can consume time. Run untrusted tool schema checking/instance validation in a small supervised Python worker process with a finite deadline, maximum payload, and bounded result; report `VALIDATION_TIMEOUT`/unsupported coverage instead of hanging. This is deadline containment, **not a sandbox**. Failure on a local transport aborts that session and marks remaining cases skipped; no reconnect/retry side effects.

Close stdin, wait briefly, then terminate/kill the direct server child if necessary. Windows cleanup of arbitrary descendant processes is not guaranteed; the fixture server spawns none. Document that executing a server grants it the current user's privileges. The harness makes no authorization, injection-resistance, isolation, or whole-server security guarantee. Ignore annotations as authority. Never infer a tool is safe to invoke from `readOnlyHint`; only explicit case entries cause tool calls.

## Bounded milestones and acceptance

### Milestone 1: first end-to-end slice

Implement pinned schema/provenance, package entry point, strict stdio exchange, discovery, single-page listing, one valid call, snapshot/check JSON reports, healthy `sum` mock, one bad-output mode, and short unittest integration tests. Add the minimum quickstart, project license, and schema attribution at the same time. Ensure scalar structured output works and every request is valid for the pin. Stop for main review with executed command evidence before expanding.

Acceptance: known-good snapshot and one healthy case exit 0; same case against bad-output exits 1 with `OUTPUT_SCHEMA` and a pointer; no process left running. Self-generated request failures are classified as harness defects rather than server failures.

### Milestone 2: required failure and compatibility behavior

Add pagination limits, schema meta-validation with registry/deadline limits, baseline comparison and `diff`, case outcome handling, malformed framing/envelope/content, wrong/duplicate IDs, stderr draining, unsupported revision, timeouts/cancellation, and exit cleanup. Add the faulty example modes and targeted tests. No new transport or protocol profile.

Acceptance: case-valid input becomes invalid under an added required field and reports `INPUT_REGRESSION`; a changed successful output violating the old output contract reports `OUTPUT_REGRESSION`; schema changes without a witness stay review findings. Expected tool error and expected JSON-RPC error pass only their respective explicit cases. Wrong mechanism/code fails. Timeout returns promptly, reports a local timeout, cleans up, and does not retry.

### Milestone 3: reviewable developer release

Complete Windows PowerShell quickstart and portable demo runner, CLI/config/report references, architecture/limitations/contribution docs, dependency/license inventory, packaging only if it adds value, and CI for Python 3.11 on Windows/Linux without paid calls. Pin CI actions to verified commit SHAs when authoring them. Produce `docs/EVIDENCE.md` with commands actually run, observed output/exit codes, environment, and checks not executed. Keep this phase local; CI execution on a remote host and publication remain unexecuted unless separately authorized.

The main owns independent acceptance and resource leases. Routine bounded tests are lightweight. Any large install, heavy integration suite, or package build requires a named lease before execution. A dependency bootstrap should be a scoped `.venv`, never a machine-wide install.

### Concrete proposed acceptance commands

The following are **future commands, not executed evidence**. Run from the assigned repository. Bootstrap needs package access (or a pre-populated wheelhouse); after that, all examples/checks below run offline and without a model.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: -r requirements.lock
.\.venv\Scripts\python.exe -m mcp_contract_guard --help
.\.venv\Scripts\python.exe -m mcp_contract_guard snapshot --out work\baseline.json -- .\.venv\Scripts\python.exe examples\faulty_server.py --mode healthy
.\.venv\Scripts\python.exe -m mcp_contract_guard check --baseline work\baseline.json --cases examples\cases.json --report work\healthy.json -- .\.venv\Scripts\python.exe examples\faulty_server.py --mode healthy
.\.venv\Scripts\python.exe -m mcp_contract_guard check --baseline work\baseline.json --cases examples\cases.json --report work\broken.json -- .\.venv\Scripts\python.exe examples\faulty_server.py --mode bad-output
.\.venv\Scripts\python.exe -m mcp_contract_guard diff examples\baseline.json examples\changed-baseline.json --report work\diff.json
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\demo.py --out work\demo
```

Expected assertions: `--help`/snapshot/healthy return 0; bad-output and changed-snapshot diff return 1; invalid config returns 2. Reports carry `reportVersion: 1`, `protocolVersion: 2026-07-28`, the exact schema digest, `executionMode: local_mock_stdio` for bundled examples, rule IDs and coverage. The demo runner itself returns 0 only when both the expected passing and expected failing examples were verified; it preserves each child exit code and marks intentional faults. Unit tests assert behavior and rule categories, not just text snapshots or implementation structure.

Required test matrix: modern metadata on every emitted request; healthy scalar/array/object output; invalid input-schema document; unsupported dialect; local `$ref` and composition; blocked external reference with retrieval never called; validation deadline; unchanged and changed baseline; removed tool; input/output witnesses; strict non-finite JSON/duplicate keys/invalid UTF-8; missing/both result-error/wrong ID; malformed content; expected and unexpected peer/tool errors; bounded silent request and process exit; stderr flood; pagination cursor loop; oversized unterminated frame; duplicate response; valid unsupported `input_required` marked incomplete; partial report/skipped cases after a fatal prerequisite. Use independently authored raw wire fixtures and meaningful subprocess tests so runner and example cannot agree on a shared schema bug.

## Risks, choices, and questions for the main

- **Current protocol differs substantially from familiar tutorials.** Resolved: modern-only pin and explicit legacy incompatibility diagnostic. Do not add a second profile during implementation without changing the accepted scope.
- **Generated schema versus prose edge cases.** Resolved: retain raw wire diagnostics separately from parsing compatibility; cite the pin for every supplementary rule. Use fixtures for result type, cache fields, and arbitrary structured values. Tool errors without an output schema avoid conflating successful output obligations with execution-error payloads in the initial demo.
- **Compatibility cannot be inferred for arbitrary JSON Schema.** Resolved: exact drift plus concrete supplied-case witnesses; no universal compatibility guarantee or automatic baseline acceptance.
- **Windows pipes and process cleanup.** Resolve with bounded reader threads and direct-child lifecycle tests. Descendant termination remains a documented limitation.
- **Hostile schemas can consume resources.** Resolve with structural limits, no external retrieval, and a supervised validation deadline. Passing does not certify security.
- **Dependency metadata is not an installation result.** A real scoped install and full closure/license check remain implementation evidence. Python version stays 3.11; Rust source builds are excluded.
- **Offline terminology.** Mock execution and snapshot comparison require no network at runtime; initial dependency bootstrap may require network. There is no recorded replay or live LLM execution in this scope.

No essential human answer or credential is needed. The next required input is the main chat's plan review and explicit **milestone 1 implementation assignment**. Proposed review decision: accept the modern-only stdio scope and concrete-witness compatibility definition, or make a bounded revision before work starts.

## Planning evidence

Actually executed: read own AGENTS/status and main-owned authorization/resource policy; `git status --short` and `rg --files`; primary web page reads listed above; Python standard-library HTTP reads of exact GitHub schema/license/source metadata and PyPI release metadata; in-memory inspection of one small Windows rpds wheel. Initially the repository contained only untracked `AGENTS.md`. Written artifacts in this phase are this plan and own coordination research/summary/status records.

Not executed: dependency installation, implementation, CLI, example server, acceptance commands, unit/integration tests, package builds, upstream Inspector/conformance runs, GitHub CI, publication, or deployment. No performance/security benchmark exists.
