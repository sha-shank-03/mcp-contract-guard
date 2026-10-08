import json
import subprocess
import sys

from .common import GuardError, MAX_FRAME, PROTOCOL_VERSION, bounded_tree

DIALECT = "https://json-schema.org/draft/2020-12/schema"


def schema_policy(schema):
    bounded_tree(schema)
    pending = [schema]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            dialect = item.get("$schema", DIALECT)
            if dialect not in (DIALECT, DIALECT + "#"):
                raise GuardError("UNSUPPORTED_DIALECT", "This schema declares an unsupported dialect.",
                                 "Use Draft 2020-12 or run a checker supporting the declared dialect.")
            for key in ("$ref", "$dynamicRef"):
                if key in item and (not isinstance(item[key], str) or not item[key].startswith("#")):
                    raise GuardError("EXTERNAL_REFERENCE", "Schema reference retrieval is disabled.",
                                     "Bundle definitions as fragment references; no network or file retrieval occurs.")
            # Walk schema locations, not arbitrary values in const/enum/default/examples.
            for key in ("additionalProperties", "unevaluatedProperties", "unevaluatedItems",
                        "contains", "not", "if", "then", "else", "items", "propertyNames"):
                if isinstance(item.get(key), (dict, bool)):
                    pending.append(item[key])
            for key in ("allOf", "anyOf", "oneOf", "prefixItems"):
                if isinstance(item.get(key), list):
                    pending.extend(item[key])
            for key in ("properties", "patternProperties", "$defs", "dependentSchemas"):
                if isinstance(item.get(key), dict):
                    pending.extend(item[key].values())


class Validator:
    """Run schema work in a killable process, not a timeout-less reader thread."""

    def __init__(self, timeout=2.0):
        self.timeout = timeout

    def _run(self, operation, *, definition=None, schema=None, instance=None):
        if schema is not None:
            schema_policy(schema)
        payload = json.dumps({"operation": operation, "definition": definition,
                              "schema": schema, "instance": instance}, allow_nan=False).encode("utf-8")
        if len(payload) > MAX_FRAME * 2:
            raise GuardError("RESOURCE_LIMIT", "Validation payload exceeds the harness limit.",
                             "Reduce schema or instance size.")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "mcp_contract_guard._validation_worker"],
                input=payload, capture_output=True, timeout=self.timeout, check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise GuardError("VALIDATION_TIMEOUT", "Schema validation exceeded its local deadline.",
                             "Simplify the schema or review the validation budget; coverage is incomplete.") from error
        if result.returncode != 0 or len(result.stdout) > 65536:
            raise GuardError("VALIDATOR_FAILURE", "The local validation worker failed.",
                             "Check the scoped dependency setup and schema complexity.")
        try:
            response = json.loads(result.stdout)
        except (ValueError, UnicodeError) as error:
            raise GuardError("VALIDATOR_FAILURE", "The local worker returned an invalid result.",
                             "Check the harness installation.") from error
        if response.get("workerError"):
            raise GuardError("VALIDATOR_FAILURE", "The local validator could not resolve or check this schema.",
                             "Review local references and schema complexity; coverage is incomplete.")
        return response["issues"]

    def definition(self, name, instance):
        return self._run("definition", definition=name, instance=instance)

    def schema(self, schema):
        return self._run("schema", schema=schema)

    def instance(self, schema, instance):
        return self._run("instance", schema=schema, instance=instance)


def request(method, request_id, params):
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": {
        **params, "_meta": {
            "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
            "io.modelcontextprotocol/clientCapabilities": {},
            "io.modelcontextprotocol/clientInfo": {"name": "mcp-contract-guard", "version": "0.1.0"},
        },
    }}
