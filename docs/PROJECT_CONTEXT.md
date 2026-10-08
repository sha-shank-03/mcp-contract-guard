# Project context

## Developer problem

Detect a server contract regression before an agent relies on its advertised schema or returned data.

## Engineering contribution

Reviewed schema baselines, supplied concrete input/output witnesses, explicit error outcome kinds and zero-request offline snapshot differences. The existing tools, overlap and primary sources considered during planning are retained in [PLAN.md](../PLAN.md). The contribution is scoped engineering and inspectable evidence; no adoption, novelty, superiority or production guarantee is implied.

## Why this portfolio exists

This independently usable repository belongs to a ten-project Java/Python portfolio focused on agent harnesses, orchestration, tool contracts, reliability, evaluation and debugging. The author brings Java backend experience and uses Python where a small local tool is sufficient. Implementation used separate AI coding workers and coordinating-agent reviews. Human maintainers remain responsible for reviewing changes.

The accepted MVP is recorded in the README and architecture documents. Future work should preserve its clear entry point, meaningful failure tests, small dependency surface and explicit trust boundaries. A supported integration or live model evaluation requires its own design and evidence.

## Demonstration and support status

39 meaningful tests; 15 fresh documented mock stdio/offline scenarios; direct mock process cleanup checks. See [independent verification](INDEPENDENT_VERIFICATION.md) for commands and qualifications. Local acceptance on 2026-10-08 used Windows, CPython 3.11.9 and/or JDK 17 as recorded. Mocks, recorded replay, actual local tools and the optional official SDK are labelled separately. These are authored-fixture results, not a live-model benchmark or third-party certification. GitHub Actions reports hosted execution separately.

Project licensing is [Apache-2.0](../LICENSE); dependencies retain their own licenses and attribution in the repository.

## Related repositories

Each project has its own Git repository, entry point, license, tests and limits. No other portfolio checkout is required to run this project.

- [spring-migration-agent](https://github.com/sha-shank-03/spring-migration-agent) — Java migration harness combining OpenRewrite, bounded mock repair and protected verification for a pinned Spring Boot fixture.
- [durable-agent-jobs](https://github.com/sha-shank-03/durable-agent-jobs) — Java and SQLite runtime for durable mock agent jobs, checkpoints, bounded retries and explicit side-effect recovery contracts.
- [agent-failure-lab](https://github.com/sha-shank-03/agent-failure-lab) — Offline Python CLI for agent trace analysis, recorded replay, failure injection and evidence-linked regression comparisons.
- [agent-tool-authority](https://github.com/sha-shank-03/agent-tool-authority) — Python policy gateway for scoped agent tools, explicit operator approval, expiration and transactional SQLite audit.
- [incident-evidence-agent](https://github.com/sha-shank-03/incident-evidence-agent) — Read-only Python incident investigation harness producing evidence-linked observations, hypotheses and explicit uncertainty.
- [agent-budget-scheduler](https://github.com/sha-shank-03/agent-budget-scheduler) — Python scheduler for cooperative agent work with tenant fairness, concurrency limits, deadlines and observed usage ledgers.
- [a2a-recovery-lab](https://github.com/sha-shank-03/a2a-recovery-lab) — Two-peer A2A JSON-RPC recovery lab with deterministic agents, loopback HTTP faults and an optional official SDK oracle.
- [agent-memory-lifecycle-bench](https://github.com/sha-shank-03/agent-memory-lifecycle-bench) — Offline SQLite-backed evaluation suite for agent memory retention, expiration, deletion, tenant separation and conflicting facts.
- [openclaw-skill-ci](https://github.com/sha-shank-03/openclaw-skill-ci) — Offline CI tooling for pinned OpenClaw skill metadata, prerequisites, team policy and safe synthetic behavior contracts.
