"""Independent raw-wire fixtures for M1 boundaries; no harness imports."""
import json
import sys
import time

mode = sys.argv[1]
for line in sys.stdin.buffer:
    request = json.loads(line)
    request_id = request.get("id")
    if request_id is None:
        continue
    if mode == "timeout":
        time.sleep(20)
        continue
    if mode == "exit":
        raise SystemExit(7)
    if mode == "malformed":
        sys.stdout.buffer.write(b'{"jsonrpc": "2.0", BROKEN}\n')
    elif mode == "oversize":
        sys.stdout.buffer.write(b"x" * (1024 * 1024 + 1))
    elif mode == "wrong-id":
        print(json.dumps({"jsonrpc": "2.0", "id": True, "result": {}}))
    elif mode == "both":
        print(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": {},
                          "error": {"code": -32603, "message": "fault"}}))
    elif mode == "stderr":
        sys.stderr.buffer.write(b"fictional diagnostic\n" * 20000)
        sys.stderr.flush()
        print(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": {
            "resultType": "complete", "supportedVersions": ["2026-07-28"],
            "capabilities": {"tools": {}}, "ttlMs": 0, "cacheScope": "private"}}))
    elif mode == "other-invalid-with-default":
        print(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": {
            "supportedVersions": ["2026-07-28"], "capabilities": {"tools": {}},
            "ttlMs": "not an integer", "cacheScope": "private"}}))
    elif mode == "notification":
        print(json.dumps({"jsonrpc": "2.0", "method": "not/a/defined/notification"}))
    sys.stdout.flush()
