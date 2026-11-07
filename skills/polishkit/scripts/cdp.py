"""Drive a Chromium browser over CDP with a hand-rolled WebSocket client.

Usage:
  python cdp.py [--out DIR]        manual spike: launch, connect, dark-mode
                                   data: URL, screenshot, PNG stats

This is the WS-A spike: proof that a stdlib-only client can do the full
launch -> WebSocket -> CDP round trip on loopback. The frame codec and the
id router are plain functions/classes so the protocol tests need no browser
and no sockets.

Design notes:
- Plaintext ws:// on loopback only. The debugger endpoint host is checked
  with visual_capture._addresses before any socket is opened; anything that
  is not 127.0.0.1 / ::1 / localhost is refused.
- --remote-debugging-port=0 is the safe launch mode (no fixed port, no
  cross-user reaching), so the chosen port is read from DevToolsActivePort
  in the fresh profile: line 1 is the port, line 2 the browser ws path.
- Client frames are always masked (RFC 6455 section 5.3); server frames must
  be unmasked and masked ones are a protocol error. No permessage-deflate is
  offered, so no compressed frames can arrive.
- One message size guard (MAX_MESSAGE_BYTES) mirrors image_diff's limits:
  a declared or accumulated message above it fails without allocating.
- Read-only: writes PNGs only into --out.
"""

import argparse
import base64
import hashlib
import http.client
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
from collections import deque
from pathlib import Path
from urllib.parse import quote, urlparse

sys.dont_write_bytecode = True
import image_diff  # noqa: E402  (sibling module; no third-party dependencies)
import visual_capture  # noqa: E402

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
# A CDP screenshot is at most a few MB; the guard exists so a broken or
# hostile peer cannot make the client buffer without bound.
MAX_MESSAGE_BYTES = 64 * 1024 * 1024
OP_CONT, OP_TEXT, OP_BINARY, OP_CLOSE, OP_PING, OP_PONG = 0x0, 0x1, 0x2, 0x8, 0x9, 0xA
OPCODES = (OP_CONT, OP_TEXT, OP_BINARY, OP_CLOSE, OP_PING, OP_PONG)
DEFAULT_TIMEOUT = 30.0
ENDPOINT_TIMEOUT = 10.0
PORT_FILE_TIMEOUT = 10.0


class ProtocolError(Exception):
    """The peer violated RFC 6455 or sent something we cannot trust."""


class NeedMoreData(Exception):
    """The buffer does not hold a full frame yet (streaming parser signal)."""


class ConnectionClosed(Exception):
    """The WebSocket was closed (by a close frame or the stream ending)."""


class NonLoopbackHost(Exception):
    """A debugger endpoint host that is not loopback was refused."""


class BrowserError(Exception):
    """The browser could not be launched or its endpoint discovered."""


class CDPError(Exception):
    """A CDP command returned an error response."""

    def __init__(self, message, error=None):
        super().__init__(message)
        self.error = error or {}
        self.code = self.error.get("code")


def accept_key(key):
    """Sec-WebSocket-Accept for a handshake key (RFC 6455 section 1.3)."""
    digest = hashlib.sha1((key + GUID).encode("ascii")).digest()  # noqa: S324 - RFC-mandated SHA-1
    return base64.b64encode(digest).decode("ascii")


def apply_mask(payload, key):
    """XOR the payload with the 4-byte mask key (RFC 6455 section 5.3)."""
    if len(key) != 4:
        raise ProtocolError("mask key must be exactly 4 bytes")
    return bytes(value ^ key[index % 4] for index, value in enumerate(payload))


def encode_frame(opcode, payload=b"", fin=True, mask=True, key=None):
    """Encode one frame. Client frames are masked; tests may build unmasked
    'server' frames with mask=False."""
    payload = bytes(payload)
    if opcode >= 0x8:  # control frames are never fragmented and stay small
        fin = True
        if len(payload) > 125:
            raise ProtocolError("control frame payload must be 125 bytes or fewer")
    mask_bit = 0x80 if mask else 0x00
    header = bytearray([((0x80 if fin else 0x00) | opcode)])
    length = len(payload)
    if length < 126:
        header.append(mask_bit | length)
    elif length <= 0xFFFF:
        header.append(mask_bit | 126)
        header += struct.pack(">H", length)
    else:
        header.append(mask_bit | 127)
        header += struct.pack(">Q", length)
    if not mask:
        return bytes(header) + payload
    key = os.urandom(4) if key is None else bytes(key)
    header += key
    return bytes(header) + apply_mask(payload, key)


def parse_frame(buf, offset=0, allow_mask=False):
    """Parse one frame at offset; raise NeedMoreData until it is complete.

    Returns (fin, opcode, payload, next_offset). Server frames must be
    unmasked (RFC 6455 section 5.1); allow_mask=True exists only to decode
    client-side frames in tests.
    """
    if len(buf) - offset < 2:
        raise NeedMoreData
    first, second = buf[offset], buf[offset + 1]
    fin = bool(first & 0x80)
    if first & 0x70:
        raise ProtocolError("RSV bits set but no extension was negotiated")
    opcode = first & 0x0F
    if opcode not in OPCODES:
        raise ProtocolError(f"reserved opcode {opcode:#04x}")
    masked = bool(second & 0x80)
    length = second & 0x7F
    position = offset + 2
    if length == 126:
        if len(buf) - position < 2:
            raise NeedMoreData
        length = struct.unpack(">H", buf[position:position + 2])[0]
        position += 2
    elif length == 127:
        if len(buf) - position < 8:
            raise NeedMoreData
        extended = struct.unpack(">Q", buf[position:position + 8])[0]
        position += 8
        if extended & 0x8000000000000000:
            raise ProtocolError("64-bit length has the high bit set")
        length = extended
    if length > MAX_MESSAGE_BYTES:
        raise ProtocolError(f"frame declares {length} bytes, above the {MAX_MESSAGE_BYTES}-byte guard")
    if opcode >= 0x8:
        if not fin:
            raise ProtocolError("control frames must not be fragmented")
        if length > 125:
            raise ProtocolError("control frame payload must be 125 bytes or fewer")
    key = None
    if masked:
        if not allow_mask:
            raise ProtocolError("server frame is masked; clients mask, servers do not (RFC 6455 section 5.1)")
        if len(buf) - position < 4:
            raise NeedMoreData
        key = bytes(buf[position:position + 4])
        position += 4
    if len(buf) - position < length:
        raise NeedMoreData
    payload = bytes(buf[position:position + length])
    position += length
    if key is not None:
        payload = apply_mask(payload, key)
    return fin, opcode, payload, position


class MessageAssembler:
    """Feed raw stream bytes; get complete (opcode, payload) messages.

    Text messages come back as str (strict UTF-8), everything else as bytes.
    Control frames pass through as they complete, so ping/close may interleave
    a fragmented data message (RFC 6455 section 5.4).
    """

    def __init__(self, max_bytes=MAX_MESSAGE_BYTES):
        self.max_bytes = max_bytes
        self.peer_closed = False
        self._buffer = bytearray()
        self._fragments = None  # None, or (opcode, bytearray) in progress

    def feed(self, data):
        self._buffer += data
        messages = []
        while True:
            try:
                fin, opcode, payload, consumed = parse_frame(self._buffer)
            except NeedMoreData:
                break
            del self._buffer[:consumed]
            if opcode in (OP_TEXT, OP_BINARY):
                if self._fragments is not None:
                    raise ProtocolError("new data frame while a message is still fragmented")
                if fin:
                    messages.append(self._finished(opcode, payload))
                else:
                    self._fragments = (opcode, bytearray(payload))
                    self._enforce_limit()
            elif opcode == OP_CONT:
                if self._fragments is None:
                    raise ProtocolError("continuation frame with no fragmented message in progress")
                base_opcode, accumulated = self._fragments
                accumulated += payload
                self._enforce_limit()
                if fin:
                    self._fragments = None
                    messages.append(self._finished(base_opcode, bytes(accumulated)))
            elif opcode == OP_CLOSE:
                self.peer_closed = True
                messages.append((opcode, payload))
            else:  # OP_PING / OP_PONG
                messages.append((opcode, payload))
        return messages

    def _enforce_limit(self):
        # Decompression-bomb discipline, same spirit as image_diff's MAX_* guards.
        if self._fragments is not None and len(self._fragments[1]) > self.max_bytes:
            raise ProtocolError(f"message grew above the {self.max_bytes}-byte guard")

    def _finished(self, opcode, payload):
        if opcode == OP_TEXT:
            try:
                return (opcode, payload.decode("utf-8"))
            except UnicodeDecodeError as exc:
                raise ProtocolError(f"text message is not valid UTF-8: {exc}") from exc
        return (opcode, payload)

    def eof(self):
        """The stream ended: leftover bytes or an open fragment is an error."""
        if self._buffer or self._fragments is not None:
            raise ProtocolError("connection closed mid-frame or mid-message")


def guard_loopback(host):
    """Refuse any debugger host that does not resolve to loopback only.

    Reuses visual_capture._addresses so both tools share one resolver and one
    notion of what counts as local.
    """
    addresses = visual_capture._addresses(host)  # noqa: SLF001 - documented sibling reuse
    if not addresses or not all(address.is_loopback for address in addresses):
        raise NonLoopbackHost(
            f"refusing to dial non-loopback debugger host {host!r} "
            f"(resolved {sorted(str(address) for address in addresses)})"
        )
    return host


def ws_url_parts(url):
    """Parse a ws:// URL, guarding the host; return (host, port, path)."""
    parsed = urlparse(url)
    if parsed.scheme != "ws":
        raise ValueError(f"only ws:// endpoints are supported, got {parsed.scheme or 'no scheme'!r}")
    if not parsed.hostname:
        raise ValueError("endpoint URL has no host")
    guard_loopback(parsed.hostname)
    return parsed.hostname, parsed.port or 80, parsed.path or "/"


def handshake_request(path, host, port, key):
    """The GET request bytes. No Sec-WebSocket-Extensions: permessage-deflate
    is deliberately not offered, so the server cannot send compressed frames."""
    return (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    ).encode("ascii")


def verify_handshake(response, key):
    """Validate a 101 response; return its headers keyed by lower-case name."""
    try:
        text = response.decode("latin-1")
    except UnicodeDecodeError as exc:
        raise ProtocolError(f"handshake response is not decodable: {exc}") from exc
    if "\r\n\r\n" not in text:
        raise ProtocolError("handshake response is truncated")
    lines = text.split("\r\n\r\n", 1)[0].split("\r\n")
    if not lines[0].startswith("HTTP/1.1 101"):
        raise ProtocolError(f"handshake refused: {lines[0]}")
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            name, value = line.split(":", 1)
            headers[name.strip().lower()] = value.strip()
    if headers.get("upgrade", "").lower() != "websocket":
        raise ProtocolError("handshake response lacks Upgrade: websocket")
    if "upgrade" not in headers.get("connection", "").lower():
        raise ProtocolError("handshake response lacks Connection: Upgrade")
    if headers.get("sec-websocket-accept") != accept_key(key):
        raise ProtocolError("Sec-WebSocket-Accept does not match the handshake key")
    if "permessage-deflate" in headers.get("sec-websocket-extensions", "").lower():
        raise ProtocolError("server offered permessage-deflate though we did not request it")
    return headers


class Connection:
    """A WebSocket client over plaintext TCP (loopback CDP endpoints only)."""

    def __init__(self, url, timeout=ENDPOINT_TIMEOUT):
        self.url = url
        host, port, path = ws_url_parts(url)  # NonLoopbackHost before any dial
        self.closed = False
        self._assembler = MessageAssembler()
        self._queue = deque()
        try:
            self.sock = socket.create_connection((host, port), timeout=timeout)
        except OSError as exc:
            raise BrowserError(f"cannot connect to {host}:{port}: {exc}") from exc
        try:
            key = base64.b64encode(os.urandom(16)).decode("ascii")
            self.sock.sendall(handshake_request(path, host, port, key))
            verify_handshake(self._read_handshake(timeout), key)
        except Exception:
            self.sock.close()
            raise

    def _read_handshake(self, timeout):
        self.sock.settimeout(timeout)
        data = bytearray()
        while b"\r\n\r\n" not in data:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ProtocolError("connection closed during handshake")
            data += chunk
            if len(data) > 16384:
                raise ProtocolError("handshake response above 16 KiB")
        return bytes(data)  # CDP never sends frames before the first request

    def send_text(self, text):
        self._send(OP_TEXT, text.encode("utf-8"))

    def _send(self, opcode, payload):
        if self.closed:
            raise ConnectionClosed("connection already closed")
        self.sock.sendall(encode_frame(opcode, payload))

    def receive_message(self, timeout):
        """Next (opcode, payload) message; answers pings, raises on close."""
        deadline = time.monotonic() + timeout
        while True:
            if self._queue:
                opcode, payload = self._queue.popleft()
                if opcode == OP_PING:
                    self._send(OP_PONG, payload)
                    continue
                if opcode == OP_PONG:
                    continue
                if opcode == OP_CLOSE:
                    self.closed = True
                    try:
                        self._send(OP_CLOSE, payload)
                    except OSError:
                        pass
                    raise ConnectionClosed("server closed the connection")
                return opcode, payload
            if self.closed or self._assembler.peer_closed:
                raise ConnectionClosed("connection is closed")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("no message arrived before the timeout")
            self.sock.settimeout(remaining)
            try:
                chunk = self.sock.recv(65536)
            except socket.timeout:
                raise TimeoutError("no message arrived before the timeout") from None
            if not chunk:
                self._assembler.eof()
                raise ConnectionClosed("connection closed by peer")
            self._queue.extend(self._assembler.feed(chunk))

    def close(self):
        if not self.closed:
            self.closed = True
            try:
                self._send(OP_CLOSE, struct.pack(">H", 1000))
            except (OSError, ConnectionClosed):
                pass  # the peer may have closed first; closing is still done
        try:
            self.sock.close()
        except OSError:
            pass


class Session:
    """Thin CDP JSON layer: ids pair requests with responses, events queue
    by method. Callers use send() directly; that is the whole API."""

    def __init__(self, connection):
        self._connection = connection
        self._next_id = 0
        self._pending = {}  # id -> {"response": msg | None, "error": err | None}
        self._handlers = {}  # method -> callable(event message)
        self.events = deque(maxlen=4096)

    def on(self, method, handler):
        """Register a handler that receives the full event message."""
        self._handlers[method] = handler

    def send(self, method, params=None, session=None, timeout=DEFAULT_TIMEOUT):
        """Run one CDP command; return its result. Raises CDPError for error
        responses and TimeoutError when the response does not arrive in time."""
        self._next_id += 1
        message_id = self._next_id
        message = {"id": message_id, "method": method, "params": dict(params or {})}
        if session is not None:
            message["sessionId"] = session
        slot = {"response": None, "error": None}
        self._pending[message_id] = slot
        self._connection.send_text(json.dumps(message))
        deadline = time.monotonic() + timeout
        try:
            while slot["response"] is None and slot["error"] is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"no response to {method} (id {message_id}) within {timeout:g}s")
                self.pump(remaining)
        finally:
            self._pending.pop(message_id, None)
        if slot["error"] is not None:
            raise CDPError(slot["error"].get("message", "unknown CDP error"), slot["error"])
        return slot["response"].get("result", {})

    def pump(self, timeout):
        """Read and route one message from the connection."""
        opcode, payload = self._connection.receive_message(timeout)
        if opcode != OP_TEXT:
            raise ProtocolError("CDP speaks JSON text frames, not binary")
        self.route(json.loads(payload))

    def route(self, message):
        """Route one decoded CDP message.

        Returns ("response", slot) when it completes a pending request,
        ("event", message) for events, None for an unknown (late) id.
        Kept public so the id-router is testable without sockets.
        """
        if "id" in message:
            slot = self._pending.get(message["id"])
            if slot is None:
                return None
            if message.get("error") is not None:
                slot["error"] = message["error"]
            else:
                slot["response"] = message
            return ("response", slot)
        handler = self._handlers.get(message.get("method"))
        if handler is not None:
            handler(message)
        self.events.append(message)
        return ("event", message)

    def close(self):
        self._connection.close()


def read_devtools_port(profile_dir, process=None, timeout=PORT_FILE_TIMEOUT):
    """Poll <profile>/DevToolsActivePort; return (port, browser_path_suffix).

    With --remote-debugging-port=0 this file is the only reliable way to learn
    the picked port: line 1 is the port, line 2 the browser ws path suffix.
    """
    deadline = time.monotonic() + timeout
    path = Path(profile_dir) / "DevToolsActivePort"
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise BrowserError(f"browser exited with code {process.returncode} before opening the debug port")
        try:
            lines = path.read_text(encoding="ascii").split()
        except OSError:
            time.sleep(0.1)
            continue
        if lines and lines[0].isdigit():
            port = int(lines[0])
            if 0 < port <= 65535:
                return port, (lines[1] if len(lines) > 1 else "")
        time.sleep(0.1)
    raise BrowserError(f"DevToolsActivePort did not appear in {profile_dir} within {timeout:g}s")


def discover_endpoint(port, timeout=ENDPOINT_TIMEOUT):
    """GET /json/version on the loopback debugger; return its JSON.

    The returned webSocketDebuggerUrl is loopback-checked here so a tampered
    endpoint can never hand us a remote host.
    """
    deadline = time.monotonic() + timeout
    last_error = "no attempt"
    while time.monotonic() < deadline:
        try:
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2.0)
            try:
                connection.request("GET", "/json/version")
                response = connection.getresponse()
                body = response.read()
                status = response.status
            finally:
                connection.close()
            if status == 200:
                endpoint = json.loads(body.decode("utf-8"))
                if not endpoint.get("webSocketDebuggerUrl"):
                    raise BrowserError("endpoint JSON has no webSocketDebuggerUrl")
                ws_url_parts(endpoint["webSocketDebuggerUrl"])  # loopback guard
                return endpoint
            last_error = f"HTTP {status}"
        except BrowserError:
            raise
        except (OSError, ValueError) as exc:
            last_error = str(exc)
        time.sleep(0.1)
    raise BrowserError(f"devtools endpoint not reachable on 127.0.0.1:{port}: {last_error}")


def wait_for_event(session, method, timeout, match=None):
    """Pump the session until an event of `method` arrives; None on deadline."""
    deadline = time.monotonic() + timeout
    while True:
        for message in list(session.events):
            if message.get("method") == method and (match is None or match(message)):
                return message
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        try:
            session.pump(remaining)
        except TimeoutError:
            pass


DEMO_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
  :root { color-scheme: light dark; }
  body { margin: 0; font-family: system-ui, sans-serif; }
  @media (prefers-color-scheme: light) {
    body { background: #f4f5f7; color: #1a1c1e; }
    .card { background: #ffffff; border: 1px solid #d5d8dd; }
    .accent { color: #0b57d0; }
    .bar { background: linear-gradient(90deg, #0b57d0, #a8c7fa); }
  }
  @media (prefers-color-scheme: dark) {
    body { background: #101418; color: #e3e6ea; }
    .card { background: #1b2129; border: 1px solid #2c3540; }
    .accent { color: #7cacf8; }
    .bar { background: linear-gradient(90deg, #7cacf8, #0842a0); }
  }
  .card { border-radius: 12px; padding: 24px; margin: 24px; }
  .bar { height: 8px; border-radius: 4px; margin: 0 24px; }
  h1 { font-size: 28px; margin: 0 0 8px; }
</style>
</head>
<body>
  <div class="card">
    <h1>CDP spike</h1>
    <p class="accent">prefers-color-scheme probe</p>
    <p>If this text is light on a dark ground, Emulation.setEmulatedMedia worked.</p>
  </div>
  <div class="bar"></div>
</body>
</html>
"""


def run_roundtrip(out_dir=None):
    """Manual spike: launch, connect, navigate a data: URL, capture dark and
    light, prove both a real render and that the media emulation took effect."""
    out = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="fa-cdp-out-"))
    out.mkdir(parents=True, exist_ok=True)
    browser = visual_capture.find_browser()
    if not browser:
        print(json.dumps({"ok": False, "reason": "no Chromium-family browser found at an absolute path"}))
        return 2
    profile = Path(tempfile.mkdtemp(prefix="fa-cdp-profile-"))
    process = None
    connection = None
    timings = {}
    try:
        started = time.monotonic()
        command = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            f"--user-data-dir={profile}",
            "--remote-debugging-port=0",
            "about:blank",
        ]
        process = subprocess.Popen(  # noqa: S603 - absolute browser path, list form, no shell
            command, shell=False, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        port, suffix = read_devtools_port(profile, process)
        endpoint = discover_endpoint(port)
        timings["launch_and_discover_s"] = round(time.monotonic() - started, 3)

        started = time.monotonic()
        connection = Connection(endpoint["webSocketDebuggerUrl"])
        session = Session(connection)
        timings["connect_and_handshake_s"] = round(time.monotonic() - started, 3)

        started = time.monotonic()
        target_id = session.send("Target.createTarget", {"url": "about:blank"})["targetId"]
        session_id = session.send(
            "Target.attachToTarget", {"targetId": target_id, "flatten": True}
        )["sessionId"]
        session.send("Page.enable", session=session_id)
        data_url = "data:text/html;charset=utf-8," + quote(DEMO_HTML)
        session.send("Page.navigate", {"url": data_url}, session=session_id)
        loaded = wait_for_event(
            session, "Page.loadEventFired", 5.0,
            match=lambda message: message.get("sessionId") == session_id,
        )
        timings["attach_navigate_load_s"] = round(time.monotonic() - started, 3)

        shots = {}
        for theme in ("dark", "light"):
            started = time.monotonic()
            session.send(
                "Emulation.setEmulatedMedia",
                {"features": [{"name": "prefers-color-scheme", "value": theme}]},
                session=session_id,
            )
            result = session.send("Page.captureScreenshot", {"format": "png"}, session=session_id)
            path = out / f"cdp-{theme}.png"
            path.write_bytes(base64.b64decode(result["data"]))
            shots[theme] = path
            timings[f"{theme}_capture_s"] = round(time.monotonic() - started, 3)

        summary = {
            "ok": True,
            "browser": browser,
            "port": port,
            "ws_path_matches_suffix": (
                urlparse(endpoint["webSocketDebuggerUrl"]).path == suffix if suffix else None
            ),
            "load_event_seen": loaded is not None,
            "out_dir": str(out),
            "timings_s": timings,
            "dark_stats": image_diff.stats(shots["dark"]),
            "real_render": image_diff.stats(shots["dark"])["distinct_colors_sampled"] > 100,
            "theme_switch_diff": image_diff.diff(shots["light"], shots["dark"]),
        }
        try:
            session.send("Target.closeTarget", {"targetId": target_id})
        except (CDPError, OSError):
            pass
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    finally:
        if connection is not None:
            try:
                session.send("Browser.close", timeout=3.0)
            except (Exception, KeyboardInterrupt):
                pass
            connection.close()
        if process is not None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
            except OSError:
                pass
        shutil.rmtree(profile, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="WS-A spike: real render over a stdlib-only CDP WebSocket client.")
    parser.add_argument("--out", default=None, help="directory for the PNGs (default: a fresh temp dir)")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    return run_roundtrip(args.out)


if __name__ == "__main__":
    sys.exit(main())
