import json
import math
import os
from pathlib import Path

PROTOCOL_VERSION = "2026-07-28"
SCHEMA_SHA256 = "ef70b61f99b6d2e5e3b46863822eab08dff6a45bedc7a08914e0e5b133f40203"
ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "vendor" / "mcp" / PROTOCOL_VERSION / "schema.json"
MAX_FRAME = 1024 * 1024


class GuardError(Exception):
    def __init__(self, code, summary, remedy, *, pointer="", details=None, exit_code=1):
        super().__init__(summary)
        self.code, self.summary, self.remedy = code, summary, remedy
        self.pointer, self.details, self.exit_code = pointer, details or {}, exit_code


def pointer(parts):
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def constant(_value):
        raise ValueError("non-finite JSON number")

    def decimal(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("non-finite JSON number")
        return result

    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="strict")
    result = json.loads(data, object_pairs_hook=pairs, parse_constant=constant, parse_float=decimal)
    bounded_tree(result, depth=64, nodes=100000)
    return result


def bounded_tree(value, *, depth=32, nodes=10000):
    pending = [(value, 0)]
    count = 0
    while pending:
        item, level = pending.pop()
        count += 1
        if level > depth or count > nodes:
            raise GuardError("RESOURCE_LIMIT", "JSON structure exceeds the configured limit.",
                             "Reduce schema/data depth or size; this is a harness policy limit.")
        if isinstance(item, dict):
            pending.extend((v, level + 1) for v in item.values())
        elif isinstance(item, list):
            pending.extend((v, level + 1) for v in item)


def read_document(path):
    try:
        with Path(path).open("rb") as source:
            data = source.read(MAX_FRAME + 1)
        if len(data) > MAX_FRAME:
            raise ValueError("document too large")
        return strict_json(data)
    except (OSError, ValueError, UnicodeError, RecursionError, GuardError) as error:
        raise GuardError("CONFIGURATION", "Cannot read the bounded strict-JSON document.",
                         "Use a UTF-8 JSON file at most 1 MiB with unique keys and finite numbers.",
                         exit_code=2) from error


def paths_alias(first, second):
    """Resolve names and detect existing same-file aliases, including hard links."""
    try:
        left, right = Path(first).resolve(), Path(second).resolve()
        if os.path.normcase(str(left)) == os.path.normcase(str(right)):
            return True
        try:
            return left.samefile(right)
        except FileNotFoundError:
            return False
    except (OSError, ValueError, RuntimeError) as error:
        raise GuardError("CONFIGURATION", "Cannot safely compare the input/output paths.",
                         "Use accessible paths without unresolved link loops.", exit_code=2) from error


def write_document(path, document):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2, ensure_ascii=True, allow_nan=False) + "\n",
                      encoding="utf-8")
