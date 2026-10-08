# Bounded M1 correction evidence

Recorded 2026-10-07 in the existing scoped Python 3.11.9 Windows environment. Scope is limited to the two defects assigned by main; M2 remains unimplemented.

The main receipt at `C:/Users/shash/Documents/CodexPortfolios/agentic-ai-2026-10-07/coordination/acceptance/mcp-contract-guard/m1-output-collision.json` supplied the reproducing argv. I read that receipt and substituted an owned disposable path, without writing in main's acceptance directory. Before fixing the code, snapshot and report using the same path returned exit 0 and replaced the existing bytes with a report. [collision-before.json](evidence/m1-corrections/collision-before.json) retains the actual command/result. This was a data-preservation defect in the original CLI.

Corrections:

- Snapshot/report and case-input/report aliases are rejected before case reading, server launch, and output writes. Path comparison resolves and normalizes names and checks existing file identity, including hard links. Configuration failure returns exit 2. The collided report path is never used to save the error report.
- Case reading now opens a binary stream and consumes at most 1 MiB plus one sentinel byte. Oversized input is rejected before parsing or server launch. Exactly 1 MiB remains accepted.

Actually executed after correction: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` ran **18 tests**, exit **0**, with the runner reporting **20.840 seconds**. This includes all original 13 tests and five regression tests. Existing-output checks used ten real CLI subcases across snapshot/check and identical, relative/absolute, normalized, hard-link, and Windows case aliases. Every subcase returned exit 2, preserved bytes at both existing paths, and left an independently written launch marker absent. A nonexistent normalized collision created neither file nor parent directory.

An oversized valid case document was rejected with exit 2; its original bytes were unchanged, the launch marker was absent, and its distinct error report recorded zero requests. A stream probe independently counted the consumed bytes at exactly 1048577; this test fails the former `Path.read_bytes()` implementation because it consumes the entire two-MiB probe. A separate exact-limit document passed the reader.

The documented healthy snapshot, healthy call, bad-output call, and resultType fallback were rerun through `.\.venv\Scripts\python.exe work/verify_m1.py`. Their actual exits remain **0/0/1/0**, with `OUTPUT_SCHEMA` on bad output and three non-failing fallback observations. [Current exact argv and results](evidence/m1/commands.json) and the four reports are refreshed. The receipt-based collision was also rerun after correction; [collision-after.json](evidence/m1-corrections/collision-after.json) records exit 2 and unchanged bytes. Saved scenario child PIDs were checked again through `Get-Process`.

These checks do not establish an atomic filesystem guarantee under concurrent path replacement. Linux, CI, publication, live servers/models, and M2/M3 remain unexecuted. No new dependency, model call, packaging backend, transport, or protocol profile was added.
