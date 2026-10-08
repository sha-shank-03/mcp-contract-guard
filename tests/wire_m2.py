"""Independent raw messages, request audit, and cancellation observation."""
import json
import sys
from pathlib import Path

mode = sys.argv[1]
audit = Path(sys.argv[2]) if len(sys.argv) > 2 else None
tool = {"name": "sum", "inputSchema": {"type": "object", "properties": {
    "a": {"type": "integer"}, "b": {"type": "integer"}}, "required": ["a", "b"]}, "outputSchema": {"type": "integer"}}
for line in sys.stdin.buffer:
    message = json.loads(line)
    method, rid = message.get("method"), message.get("id")
    if audit:
        with audit.open("a", encoding="utf-8") as target:
            target.write(json.dumps({"method": method, "id": rid,
                "cancelledId": message.get("params", {}).get("requestId"),
                "hasModernMeta": "io.modelcontextprotocol/protocolVersion" in message.get("params", {}).get("_meta", {})}) + "\n")
    if rid is None:
        if method == "notifications/cancelled":
            break
        continue
    if method == "server/discover":
        result = {"resultType": "complete", "supportedVersions": ["2026-07-28"], "capabilities": {"tools": {}}, "ttlMs": 0, "cacheScope": "private"}
    elif method == "tools/list":
        result = {"resultType": "complete", "tools": [tool], "ttlMs": 0, "cacheScope": "private"}
    else:
        result = {"resultType": "complete", "content": [{"type": "text", "text": "synthetic"}], "structuredContent": 5}
        if mode == "silent":
            continue
        if mode == "exit":
            raise SystemExit(7)
        if mode == "invalid-utf8":
            sys.stdout.buffer.write(b'\xff\n'); sys.stdout.flush(); continue
        if mode == "truncated":
            sys.stdout.buffer.write(b'{"jsonrpc":"2.0"}'); sys.stdout.flush(); break
        if mode == "missing-content":
            result.pop("content")
        elif mode == "bad-content":
            result["content"] = [{"type": "text", "text": 42}]
        elif mode == "unknown-result-type":
            result["resultType"] = "unadvertised-extension"
        elif mode == "input-required":
            result = {"resultType": "input_required", "requestState": "opaque-mock"}
    response = {"jsonrpc": "2.0", "id": rid, "result": result}
    if method == "tools/call" and mode == "wrong-id":
        response["id"] = rid + 1
    if method == "tools/call" and mode == "both":
        response["error"] = {"code": -32602, "message": "mock"}
    if method == "tools/call" and mode == "neither":
        response.pop("result")
    if method == "tools/call" and mode in ("rpc-error", "bad-error"):
        response = {"jsonrpc": "2.0", "id": rid, "error": {
            "code": True if mode == "bad-error" else -32602, "message": "mock"}}
    if method == "tools/call" and mode == "tool-error":
        response["result"] = {"resultType": "complete", "content": [{"type": "text", "text": "mock error"}], "isError": True}
    print(json.dumps(response), flush=True)
    if mode == "duplicate" and method == "tools/call":
        print(json.dumps(response), flush=True)
