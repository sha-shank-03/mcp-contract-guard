# Prepared CI and provenance

The [workflow](../.github/workflows/ci.yml) is prepared locally and has **not run on GitHub or Linux**. It uses standard Windows 2022 and Ubuntu 24.04 x64 runners with Python 3.11.9, max two parallel jobs, ten-minute job deadlines, read-only `contents` permission, and checkout credential persistence disabled. It triggers on push, pull_request, or explicit dispatch, with superseded runs canceled. It does not use privileged pull_request_target, configured secrets, model/provider calls, deployment, publication, or a paid external service.

The workflow is intended for a public open-source repository using standard hosted runners. No runner billing setting or account quota was queried, and no remote workflow was triggered. Setup obtains Python/actions and the existing hash-locked binary wheels from official/package services; subsequent tests exchange only local mock stdio and offline files. Hosted artifact retention is seven days; only synthetic demo outputs are uploaded. This is CI preparation, not a passing CI claim or a guarantee of runner availability.

Each job checks dependency closure, executes the five targeted test modules sequentially, then runs `scripts/demo.py --out-dir work/ci-demo`. The demo asserts both successful and deliberately failing CLI exits, exact finding rules, concrete witnesses versus review-only drift, explicit error mechanisms, two-page/three-shape coverage, direct-child cleanup, zero-request offline diff, and unchanged input hashes. Demo failure exits nonzero. No step suppresses an unexpected failure; the final artifact step uses `always()` to retain available diagnostic receipts.

Full action commits were resolved through official GitHub release/tag/commit endpoints and their action definitions/license files actually read on 2026-10-08. [ci-provenance.json](ci-provenance.json) retains URLs, observed tags, immutable commits, and source/license SHA-256 hashes:

| Official action | Observed release | Commit |
| --- | --- | --- |
| [checkout](https://github.com/actions/checkout/commit/3d3c42e5aac5ba805825da76410c181273ba90b1) | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| [setup-python](https://github.com/actions/setup-python/commit/5fda3b95a4ea91299a34e894583c3862153e4b97) | v7.0.0 | `5fda3b95a4ea91299a34e894583c3862153e4b97` |
| [upload-artifact](https://github.com/actions/upload-artifact/commit/cf430e030ddbb5b0abf93d22962f4752f3646cd9) | v7.0.2 | `cf430e030ddbb5b0abf93d22962f4752f3646cd9` |

All three declare MIT and run on Node 24 in the inspected action definitions. They are referenced by immutable commits rather than copied into this repository. Exact action inputs used in the workflow were read at those commits. This follows GitHub's [commit-pin guidance](https://docs.github.com/en/actions/reference/security/secure-use#using-third-party-actions); source inspection is not a comprehensive action security audit.

The lock covers CPython 3.11 Windows amd64/Linux x86_64 wheels. macOS, ARM, source builds, other interpreters, live servers, broader protocol profiles, and upstream conformance are outside this job. CI runner images remain managed version labels; they are not immutable machine-image pins. Passing these jobs, when eventually executed, establishes only their supported cases.
