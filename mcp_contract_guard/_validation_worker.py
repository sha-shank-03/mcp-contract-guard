"""Internal worker. Output contains paths/keywords, never instance values."""
import hashlib
import json
import sys
from itertools import islice

from jsonschema import Draft202012Validator
from referencing import Registry
from referencing.exceptions import NoSuchResource

from .common import MAX_FRAME, SCHEMA_PATH, SCHEMA_SHA256, pointer, strict_json


def deny_retrieval(uri):
    raise NoSuchResource(ref=uri)


def main():
    try:
        payload = sys.stdin.buffer.read(MAX_FRAME * 2 + 1)
        if len(payload) > MAX_FRAME * 2:
            raise ValueError("input limit")
        job = strict_json(payload)
        registry = Registry(retrieve=deny_retrieval)
        if job["operation"] == "definition":
            raw = SCHEMA_PATH.read_bytes()
            if hashlib.sha256(raw).hexdigest() != SCHEMA_SHA256:
                raise ValueError("schema digest")
            pinned = json.loads(raw)
            if job["definition"] not in pinned["$defs"]:
                raise ValueError("definition")
            schema = {**pinned, "$ref": "#/$defs/" + job["definition"]}
            errors = Draft202012Validator(schema, registry=registry).iter_errors(job["instance"])
        elif job["operation"] == "schema":
            try:
                Draft202012Validator.check_schema(job["schema"])
                errors = iter(())
            except Exception as error:
                from jsonschema.exceptions import SchemaError
                if not isinstance(error, SchemaError):
                    raise
                errors = iter((error,))
        elif job["operation"] == "instance":
            errors = Draft202012Validator(job["schema"], registry=registry).iter_errors(job["instance"])
        else:
            raise ValueError("operation")
        issues = [{"instancePointer": pointer(error.absolute_path),
                   "schemaPointer": pointer(error.absolute_schema_path),
                   "keyword": str(error.validator)} for error in islice(errors, 20)]
        response = {"issues": issues}
    except Exception:
        response = {"workerError": True, "issues": []}
    sys.stdout.write(json.dumps(response, ensure_ascii=True))


if __name__ == "__main__":
    main()
