import json
import queue
import subprocess
import threading
import time

from .common import GuardError, MAX_FRAME, strict_json


class Stdio:
    """One in-flight request, bounded byte framing, direct-child cleanup."""

    def __init__(self, argv, *, max_frame=MAX_FRAME, timeout=2.0):
        self.argv, self.max_frame, self.timeout = argv, max_frame, timeout
        self.frames = queue.Queue(maxsize=32)
        self.failure = None
        self.writer_error = None
        self.eof = False
        self.stderr_bytes = 0
        self.notifications = 0
        self.completed_ids = set()
        self.cancellation_attempted = False
        self.cancellation_write_completed = False
        self.process = None
        self.threads = []
        self.cleanup = {"directChildExited": False}

    def open(self):
        try:
            self.process = subprocess.Popen(
                self.argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, shell=False, bufsize=0,
            )
        except (OSError, ValueError) as error:
            raise GuardError("SERVER_START", "The server command could not be launched.",
                             "Supply an existing executable and an explicit argument list.", exit_code=2) from error
        for function in (self._read_stdout, self._drain_stderr):
            thread = threading.Thread(target=function, daemon=True)
            thread.start()
            self.threads.append(thread)
        return self

    def _read_stdout(self):
        pending = bytearray()
        try:
            while chunk := self.process.stdout.read(65536):
                pending.extend(chunk)
                while (end := pending.find(b"\n")) >= 0:
                    if end + 1 > self.max_frame:
                        raise GuardError("FRAME_LIMIT", "A server frame exceeded the byte limit.",
                                         "Reduce response size; the default limit is 1 MiB per frame.")
                    frame = bytes(pending[:end + 1])
                    del pending[:end + 1]
                    try:
                        self.frames.put_nowait(frame)
                    except queue.Full:
                        raise GuardError("QUEUE_LIMIT", "The server exceeded the bounded receive queue.",
                                         "Reduce unsolicited messages or response bursts.")
                if len(pending) >= self.max_frame:
                    raise GuardError("FRAME_LIMIT", "An unterminated server frame exceeded the byte limit.",
                                     "Write one bounded newline-delimited JSON message per frame.")
            if pending:
                raise GuardError("TRUNCATED_FRAME", "The server closed stdout before the frame newline.",
                                 "Terminate every JSON-RPC frame with a newline.")
        except GuardError as error:
            self.failure = error
        except OSError:
            self.failure = GuardError("STDIO_READ", "Reading the server pipe failed.",
                                      "Inspect the server lifecycle and stdio framing.")
        finally:
            self.eof = True

    def _drain_stderr(self):
        try:
            while chunk := self.process.stderr.read(65536):
                self.stderr_bytes += len(chunk)
        except OSError:
            pass

    def _send(self, payload):
        try:
            view = memoryview(payload)
            while view:
                written = self.process.stdin.write(view)
                if not written:
                    raise OSError("short write")
                view = view[written:]
        except (OSError, ValueError):
            self.writer_error = GuardError("STDIO_WRITE", "Writing to the server pipe failed.",
                                           "Check that the server reads stdin and remains alive.")

    def exchange(self, message, *, timeout=None, notification_validator=None):
        payload = (json.dumps(message, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
        if len(payload) > self.max_frame:
            raise GuardError("REQUEST_LIMIT", "The harness request exceeds its frame limit.",
                             "Reduce case arguments or schemas.")
        self.writer_error = None
        writer = threading.Thread(target=self._send, args=(payload,), daemon=True)
        writer.start()
        self.threads.append(writer)
        deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
        while True:
            if self.failure:
                raise self.failure
            if self.writer_error:
                raise self.writer_error
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                # Best effort only: cleanup terminates the child even if stdin is blocked.
                cancelled = {"jsonrpc": "2.0", "method": "notifications/cancelled",
                             "params": {"requestId": message["id"], "reason": "local request deadline"}}
                if not writer.is_alive():
                    self.cancellation_attempted = True
                    cancel = threading.Thread(target=self._send, args=(
                        (json.dumps(cancelled) + "\n").encode("utf-8"),), daemon=True)
                    cancel.start()
                    self.threads.append(cancel)
                    cancel.join(timeout=0.05)
                    self.cancellation_write_completed = not cancel.is_alive() and self.writer_error is None
                raise GuardError("REQUEST_TIMEOUT", "The local request deadline expired.",
                                 "Inspect server latency; no call was retried and cancellation is best effort.")
            try:
                frame = self.frames.get(timeout=min(0.05, remaining))
            except queue.Empty:
                # The reader must finish inspecting buffered bytes before EOF wins.
                if self.failure:
                    raise self.failure
                if self.eof:
                    raise GuardError("SERVER_EXIT", "The server stopped before replying.",
                                     "Keep the stdio server alive until its input is closed.")
                continue
            try:
                response = strict_json(frame)
            except (ValueError, UnicodeError, RecursionError) as error:
                raise GuardError("WIRE_JSON", "A server frame is not strict UTF-8 JSON.",
                                 "Write valid JSON with unique keys and finite numbers only to stdout.") from error
            if not isinstance(response, dict):
                raise GuardError("WIRE_ENVELOPE", "An MCP frame must contain one JSON-RPC object.",
                                 "Do not send a JSON-RPC batch or non-object response.")
            if "method" in response and "id" not in response:
                self.notifications += 1
                if self.notifications > 32:
                    raise GuardError("NOTIFICATION_LIMIT", "The run exceeded its notification limit.",
                                     "Reduce notifications or use a harness supporting this stream.")
                if notification_validator:
                    notification_validator(response)
                continue
            if response.get("jsonrpc") != "2.0" or "method" in response:
                raise GuardError("WIRE_ENVELOPE", "The server sent an invalid response envelope.",
                                 "Return a JSON-RPC 2.0 response; modern servers do not initiate requests.")
            response_id = response.get("id")
            if isinstance(response_id, (str, int)) and (type(response_id), response_id) in self.completed_ids:
                raise GuardError("DUPLICATE_RESPONSE", "The server repeated a completed response ID.",
                                 "Emit exactly one response for each request.", pointer="/id")
            if type(response.get("id")) is not type(message["id"]) or response.get("id") != message["id"]:
                raise GuardError("RESPONSE_ID", "The response ID does not match the active request.",
                                 "Echo the exact request ID and emit one response per request.", pointer="/id")
            if ("result" in response) == ("error" in response):
                raise GuardError("WIRE_ENVELOPE", "A response must contain exactly one result or error.",
                                 "Return one result or one JSON-RPC error, never both or neither.")
            self.completed_ids.add((type(message["id"]), message["id"]))
            return response

    def drain_after_close(self, notification_validator=None):
        """Inspect final buffered messages so the last response cannot hide a duplicate."""
        if self.failure:
            raise self.failure
        while not self.frames.empty():
            frame = self.frames.get_nowait()
            try:
                message = strict_json(frame)
            except (ValueError, UnicodeError, RecursionError) as error:
                raise GuardError("WIRE_JSON", "Trailing server output is not strict JSON.", "Write valid MCP messages only.") from error
            if isinstance(message, dict) and "method" in message and "id" not in message:
                self.notifications += 1
                if self.notifications > 32:
                    raise GuardError("NOTIFICATION_LIMIT", "The run exceeded its notification limit.", "Reduce unsolicited messages.")
                if notification_validator:
                    notification_validator(message)
                continue
            response_id = message.get("id") if isinstance(message, dict) else None
            if isinstance(response_id, (int, str)) and (type(response_id), response_id) in self.completed_ids:
                raise GuardError("DUPLICATE_RESPONSE", "The server repeated a completed response ID.",
                                 "Emit exactly one response per request.", pointer="/id")
            raise GuardError("RESPONSE_ID", "The server sent an unsolicited trailing response.", "Reply only to active requests.")

    def close(self):
        if self.process is None:
            return
        forced = False
        active_writer = any(thread.is_alive() for thread in self.threads[2:])
        if active_writer and self.process.poll() is None:
            self.process.terminate()
            forced = True
        try:
            self.process.stdin.close()
        except (OSError, ValueError):
            pass
        try:
            self.process.wait(timeout=0.4)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            forced = True
            try:
                self.process.wait(timeout=0.4)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=0.4)
        for thread in self.threads:
            thread.join(timeout=0.1)
        # Do not close a pipe while a reader is blocked on a descendant-held handle.
        if not self.threads[0].is_alive():
            self.process.stdout.close()
        if not self.threads[1].is_alive():
            self.process.stderr.close()
        self.cleanup = {"directChildExited": self.process.poll() is not None,
                        "forcedTermination": forced,
                        "readerThreadsStopped": not any(t.is_alive() for t in self.threads[:2]),
                        "serverPid": self.process.pid,
                        "stderrBytes": self.stderr_bytes,
                        "cancellationAttempted": self.cancellation_attempted,
                        "cancellationWriteCompleted": self.cancellation_write_completed,
                        "descendantContainment": "not_provided"}
