# Dependencies and attribution

Original MCP Contract Guard source, examples, tests, demo, and documentation are licensed under Apache-2.0; see the root LICENSE. No Inspector/conformance source is copied.

The official MCP generated JSON schema is vendored at `vendor/mcp/2026-07-28/schema.json`. Its exact commit, digest, and retrieval date are recorded beside it. The complete upstream LICENSE is preserved there: new code/specification contributions are Apache-2.0; original contributions without relicensing consent retain MIT; documentation excluding specifications follows CC-BY-4.0. This file is a generated specification artifact. Do not replace the combined notice with a single license label.

The runtime wheel closure was installed into `.venv` using `--require-hashes --only-binary=:all:`. There is no packaging backend in the MVP, no format extras, and no source compilation. Exact PyPI metadata sources and Windows/Linux wheel hashes are in [dependency-provenance.json](dependency-provenance.json) and `requirements.lock`.

| Dependency | Version | Declared license | Distributed notice inspected after install |
| --- | --- | --- | --- |
| jsonschema | 4.25.1 | MIT | `jsonschema-4.25.1.dist-info/licenses/COPYING` |
| referencing | 0.36.2 | MIT | `referencing-0.36.2.dist-info/licenses/COPYING` |
| attrs | 25.3.0 | MIT | `attrs-25.3.0.dist-info/licenses/LICENSE` |
| jsonschema-specifications | 2025.9.1 | MIT | `jsonschema_specifications-2025.9.1.dist-info/licenses/COPYING` |
| rpds-py | 0.27.1 | MIT | `rpds_py-0.27.1.dist-info/licenses/LICENSE` |
| typing-extensions | 4.15.0 | PSF-2.0 | `typing_extensions-4.15.0.dist-info/licenses/LICENSE` |

The exact six installed notices are also preserved in [vendor/licenses](../vendor/licenses/manifest.json). Its manifest records the installed distribution path, copied path, byte count, and SHA-256, verified against the existing installed copies during M3. The native wheel's inspected rpds notice is retained as distributed; this inventory does not claim an exhaustive audit of embedded native components.

| Package | Retained notice |
| --- | --- |
| jsonschema | [MIT COPYING](../vendor/licenses/jsonschema-4.25.1-COPYING) |
| referencing | [MIT COPYING](../vendor/licenses/referencing-0.36.2-COPYING) |
| attrs | [MIT LICENSE](../vendor/licenses/attrs-25.3.0-LICENSE) |
| jsonschema-specifications | [MIT COPYING](../vendor/licenses/jsonschema-specifications-2025.9.1-COPYING) |
| rpds-py | [MIT LICENSE](../vendor/licenses/rpds-py-0.27.1-LICENSE) |
| typing-extensions | [Distributed PSF/BeOpen notices](../vendor/licenses/typing-extensions-4.15.0-LICENSE) |

`jsonschema` provides Draft 2020-12 validation. `referencing` provides the public explicit registry API. The other four are their dependency closure for Python 3.11. Package metadata and distributed notices were inspected on 2026-10-07; the installed files are inventory evidence rather than a claim of a comprehensive audit of embedded native dependencies. Package licenses remain in the installed distributions. Python and pip are environment/bootstrap tools; they are not vendored or machine-wide installed by this repository.

Primary sources: each pinned release's `https://pypi.org/pypi/<name>/<version>/json` is recorded in provenance. Validator behavior is grounded in the [pinned validation docs](https://python-jsonschema.readthedocs.io/en/v4.25.1/validate/) and [referencing docs](https://python-jsonschema.readthedocs.io/en/v4.25.1/referencing/). All research dates and actual installed versions are retained in evidence.

Prepared CI references three official MIT-licensed GitHub actions by verified commits. They are development workflow tools, not Python runtime dependencies or vendored action code; their source/license URLs and digests appear in [CI provenance](ci-provenance.json). No packaging backend, SDK, provider dependency, or extra installation was introduced for M3.
