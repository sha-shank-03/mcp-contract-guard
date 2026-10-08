"""Deterministic mock MCP stdio server. No model, network, or external effects.

This fixture deliberately does not import the harness or its schema helpers.
"""
import argparse
import copy
import json
import sys

VERSION = "2026-07-28"
TOOL = {"name": "sum", "description": "Add two fictional fixture integers.",
        "inputSchema": {"type": "object", "properties": {
            "a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"], "additionalProperties": False},
        "outputSchema": {"type": "integer"}}
ECHO = {"name": "echo", "description": "Echo synthetic JSON values.", "inputSchema": {
    "type": "object", "properties": {"value": {}}, "required": ["value"], "additionalProperties": False},
    "outputSchema": {}}


def respond(request_id, result, omit_type=False):
    if not omit_type:
        result = {"resultType": "complete", **result}
    print(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}), flush=True)


def error(request_id, code, data=None):
    print(json.dumps({"jsonrpc": "2.0", "id": request_id,
                      "error": {"code": code, "message": "Mock request rejected", **({"data": data} if data is not None else {})}}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("healthy", "bad-output", "missing-result-type", "input-regression",
        "output-regression", "schema-drift-only", "paged", "cursor-loop", "duplicate-tool", "shapes",
        "malformed-json", "malformed-content", "rpc-error", "tool-error", "timeout", "exit",
        "unsupported-version", "unsupported-version-error", "input-required", "duplicate-id", "removed-tool"), default="healthy")
    args = parser.parse_args()
    tool = copy.deepcopy(TOOL)
    if args.mode in ("input-regression", "schema-drift-only"):
        tool["inputSchema"]["properties"]["precision"] = {"type": "integer"}
        if args.mode == "input-regression":
            tool["inputSchema"]["required"].append("precision")
    if args.mode == "output-regression":
        tool["outputSchema"] = {"type": "string"}
    for line in sys.stdin:
        try:
            message = json.loads(line)
            if "id" not in message:
                if message.get("method") == "notifications/cancelled":
                    return 0
                continue
            params = message.get("params", {})
            meta = params.get("_meta", {})
            # Independently enforce the fields the harness must put on every request.
            if (message.get("jsonrpc") != "2.0"
                    or meta.get("io.modelcontextprotocol/protocolVersion") != VERSION
                    or meta.get("io.modelcontextprotocol/clientCapabilities") != {}
                    or meta.get("io.modelcontextprotocol/clientInfo") != {
                        "name": "mcp-contract-guard", "version": "0.1.0"}):
                error(message["id"], -32602)
                continue
            method = message.get("method")
            if method == "server/discover":
                if args.mode == "unsupported-version-error":
                    error(message["id"], -32022, {"requested": VERSION, "supported": ["2025-11-25"]})
                    continue
                result = {"supportedVersions": [VERSION], "capabilities": {"tools": {}},
                          "ttlMs": 0, "cacheScope": "private", "_meta": {
                              "io.modelcontextprotocol/serverInfo": {"name": "mock-sum", "version": "1.0.0"}}}
                if args.mode == "unsupported-version":
                    result["supportedVersions"] = ["2025-11-25"]
            elif method == "tools/list":
                result = {"tools": [tool], "ttlMs": 0, "cacheScope": "private"}
                if args.mode in ("paged", "duplicate-tool"):
                    if "cursor" not in params:
                        result["nextCursor"] = "page-two"
                    else:
                        result["tools"] = [tool if args.mode == "duplicate-tool" else ECHO]
                elif args.mode == "cursor-loop":
                    result.update(tools=[], nextCursor="same-cursor")
                elif args.mode == "shapes":
                    result["tools"] = [tool, ECHO]
                elif args.mode == "removed-tool":
                    result["tools"] = []
            elif method == "tools/call":
                if args.mode == "malformed-json":
                    print('{"broken":', flush=True)
                    continue
                if args.mode == "rpc-error":
                    error(message["id"], -32602)
                    continue
                if args.mode == "tool-error":
                    respond(message["id"], {"content": [{"type": "text", "text": "Mock execution error"}], "isError": True})
                    continue
                if args.mode == "timeout":
                    continue
                if args.mode == "exit":
                    return 7
                if args.mode == "input-required":
                    respond(message["id"], {"resultType": "input_required", "requestState": "mock-pending"})
                    continue
                if params.get("name") == "echo" and args.mode in ("paged", "shapes"):
                    value = params["arguments"]["value"]
                    respond(message["id"], {"content": [{"type": "text", "text": "Mock echo"}], "structuredContent": value})
                    continue
                if params.get("name") != "sum":
                    error(message["id"], -32602)
                    continue
                values = params.get("arguments", {})
                if not {"a", "b"} <= values.keys() or any(type(v) is not int for v in values.values()):
                    result = {"content": [{"type": "text", "text": "Mock integer input error"}], "isError": True}
                else:
                    value = values["a"] + values["b"]
                    result = {"content": [{"type": "text", "text": str(value)}],
                              "structuredContent": "intentional mock fault" if args.mode == "bad-output" else value,
                              "isError": False}
                    if args.mode == "output-regression":
                        result["structuredContent"] = str(value)
                    if args.mode == "malformed-content":
                        result["content"] = [{"type": "text", "text": 42}]
            else:
                error(message["id"], -32602)
                continue
            respond(message["id"], result, omit_type=args.mode == "missing-result-type")
            if args.mode == "duplicate-id" and method == "tools/call":
                respond(message["id"], result)
        except (ValueError, TypeError, KeyError):
            # The harness only sends valid requests in this mock path.
            print("Malformed mock input", file=sys.stderr, flush=True)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
