"""Byte-level tests for the CDP WebSocket client (no browser, no sockets).

Run from the plugin root: python -B -m unittest discover -s tests
Frames are built inline the way make_fixtures.py builds PNGs: the protocol
under test is exercised against bytes we construct by hand. Only the
loopback-guard tests touch the resolver, never the network.
"""

import json
import struct
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

TESTS = Path(__file__).resolve().parent
SCRIPTS = TESTS.parent / "skills" / "polishkit" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import cdp  # noqa: E402

RFC_KEY = "dGhlIHNhbXBsZSBub25jZQ=="
RFC_ACCEPT = "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="


class HandshakeTests(unittest.TestCase):
    def test_accept_key_matches_rfc_6455_section_1_3_vector(self):
        self.assertEqual(cdp.accept_key(RFC_KEY), RFC_ACCEPT)

    def test_request_carries_required_headers_and_no_deflate(self):
        request = cdp.handshake_request("/devtools/browser/x", "127.0.0.1", 9222, "KEY").decode("ascii")
        self.assertTrue(request.startswith("GET /devtools/browser/x HTTP/1.1\r\n"))
        self.assertIn("Host: 127.0.0.1:9222\r\n", request)
        self.assertIn("Upgrade: websocket\r\n", request)
        self.assertIn("Connection: Upgrade\r\n", request)
        self.assertIn("Sec-WebSocket-Key: KEY\r\n", request)
        self.assertIn("Sec-WebSocket-Version: 13\r\n", request)
        self.assertNotIn("permessage-deflate", request)

    def test_valid_response_verifies_against_the_rfc_vector(self):
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {RFC_ACCEPT}\r\n"
            "\r\n"
        ).encode("latin-1")
        headers = cdp.verify_handshake(response, RFC_KEY)
        self.assertEqual(headers["sec-websocket-accept"], RFC_ACCEPT)

    def test_wrong_accept_is_rejected(self):
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Accept: /nope=\r\n"
            "\r\n"
        ).encode("latin-1")
        with self.assertRaises(cdp.ProtocolError):
            cdp.verify_handshake(response, RFC_KEY)

    def test_non_101_response_is_rejected(self):
        response = b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n"
        with self.assertRaises(cdp.ProtocolError):
            cdp.verify_handshake(response, RFC_KEY)

    def test_unsolicited_permessage_deflate_is_rejected(self):
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {RFC_ACCEPT}\r\n"
            "Sec-WebSocket-Extensions: permessage-deflate\r\n"
            "\r\n"
        ).encode("latin-1")
        with self.assertRaises(cdp.ProtocolError):
            cdp.verify_handshake(response, RFC_KEY)


class EncodeTests(unittest.TestCase):
    def test_masked_text_frame_layout_with_zero_key(self):
        # Zero mask key means the payload passes through unchanged, so the
        # exact byte layout is checkable by hand: FIN|text, MASK|len 2, key.
        frame = cdp.encode_frame(cdp.OP_TEXT, b"Hi", key=bytes(4))
        self.assertEqual(frame, b"\x81\x82\x00\x00\x00\x00Hi")

    def test_masking_round_trip_with_fixed_key(self):
        frame = cdp.encode_frame(cdp.OP_TEXT, b"Hello", key=b"\x01\x02\x03\x04")
        self.assertEqual(frame[1] & 0x80, 0x80)  # client frames carry the mask bit
        fin, opcode, payload, _ = cdp.parse_frame(frame, allow_mask=True)
        self.assertEqual((fin, opcode, payload), (True, cdp.OP_TEXT, b"Hello"))

    def test_apply_mask_known_vector(self):
        self.assertEqual(cdp.apply_mask(b"Hello", b"\x01\x02\x03\x04"), b"Igohn")

    def test_short_length_uses_the_seven_bit_form(self):
        self.assertEqual(cdp.encode_frame(cdp.OP_TEXT, b"abc", mask=False), b"\x81\x03abc")

    def test_length_126_switches_to_the_sixteen_bit_form(self):
        frame = cdp.encode_frame(cdp.OP_BINARY, bytes(126), mask=False)
        self.assertEqual(frame[:4], b"\x82\x7e\x00\x7e")  # server frame: no mask bit
        self.assertEqual(len(frame), 4 + 126)

    def test_length_65536_switches_to_the_sixty_four_bit_form(self):
        frame = cdp.encode_frame(cdp.OP_BINARY, bytes(65536), mask=False)
        self.assertEqual(frame[:10], b"\x82\x7f\x00\x00\x00\x00\x00\x01\x00\x00")
        self.assertEqual(len(frame), 10 + 65536)

    def test_length_125_stays_in_the_seven_bit_form(self):
        frame = cdp.encode_frame(cdp.OP_BINARY, bytes(125), mask=False)
        self.assertEqual(frame[:2], b"\x82\x7d")

    def test_close_frame_carries_the_status_code(self):
        frame = cdp.encode_frame(cdp.OP_CLOSE, struct.pack(">H", 1000), mask=False)
        self.assertEqual(frame, b"\x88\x02\x03\xe8")

    def test_ping_and_pong_opcodes_lay_out_correctly(self):
        self.assertEqual(cdp.encode_frame(cdp.OP_PING, b"pi", mask=False)[:2], b"\x89\x02")
        self.assertEqual(cdp.encode_frame(cdp.OP_PONG, b"pi", mask=False)[:2], b"\x8a\x02")

    def test_first_fragment_clears_the_fin_bit(self):
        self.assertEqual(cdp.encode_frame(cdp.OP_TEXT, b"He", fin=False, mask=False)[:2], b"\x01\x02")

    def test_client_frames_are_masked_by_default(self):
        frame = cdp.encode_frame(cdp.OP_TEXT, b"x")
        self.assertTrue(frame[1] & 0x80)
        self.assertNotEqual(frame[6:], b"x")  # masked payload, random key

    def test_mask_key_must_be_four_bytes(self):
        with self.assertRaises(cdp.ProtocolError):
            cdp.encode_frame(cdp.OP_TEXT, b"x", key=b"short")


class DecodeTests(unittest.TestCase):
    def test_unmasked_server_text_frame_parses(self):
        fin, opcode, payload, consumed = cdp.parse_frame(b"\x81\x05Hello")
        self.assertEqual((fin, opcode, payload, consumed), (True, cdp.OP_TEXT, b"Hello", 7))

    def test_unmasked_server_binary_frame_parses(self):
        fin, opcode, payload, _ = cdp.parse_frame(b"\x82\x03abc")
        self.assertEqual((fin, opcode, payload), (True, cdp.OP_BINARY, b"abc"))

    def test_masked_server_frame_is_rejected(self):
        with self.assertRaises(cdp.ProtocolError):
            cdp.parse_frame(cdp.encode_frame(cdp.OP_TEXT, b"Hi"))  # client frame = masked

    def test_rsv_bits_set_without_extension_are_rejected(self):
        with self.assertRaises(cdp.ProtocolError):
            cdp.parse_frame(b"\x91\x00")  # FIN + RSV1 + text

    def test_reserved_opcode_is_rejected(self):
        with self.assertRaises(cdp.ProtocolError):
            cdp.parse_frame(b"\x83\x00")  # opcode 3

    def test_fragmented_control_frame_is_rejected(self):
        with self.assertRaises(cdp.ProtocolError):
            cdp.parse_frame(b"\x09\x00")  # ping with FIN clear

    def test_control_frame_above_125_bytes_is_rejected(self):
        with self.assertRaises(cdp.ProtocolError):
            cdp.parse_frame(b"\x89\x7e\x00\x7e" + bytes(126))  # unmasked ping, 16-bit length

    def test_truncated_frame_raises_need_more_data(self):
        with self.assertRaises(cdp.NeedMoreData):
            cdp.parse_frame(b"\x81\x05He")

    def test_truncated_extended_length_raises_need_more_data(self):
        with self.assertRaises(cdp.NeedMoreData):
            cdp.parse_frame(b"\x82\xfe\x00")

    def test_oversized_declared_length_is_rejected_without_allocation(self):
        with self.assertRaises(cdp.ProtocolError):
            cdp.parse_frame(b"\x82\x7f" + struct.pack(">Q", cdp.MAX_MESSAGE_BYTES + 1))

    def test_fragments_assemble_in_order(self):
        assembler = cdp.MessageAssembler()
        messages = assembler.feed(
            cdp.encode_frame(cdp.OP_TEXT, b"Hel", fin=False, mask=False)
            + cdp.encode_frame(cdp.OP_CONT, b"lo w", fin=False, mask=False)
            + cdp.encode_frame(cdp.OP_CONT, b"orld", mask=False)
        )
        self.assertEqual(messages, [(cdp.OP_TEXT, "Hello world")])

    def test_control_frame_interleaves_a_fragmented_message(self):
        assembler = cdp.MessageAssembler()
        messages = assembler.feed(
            cdp.encode_frame(cdp.OP_TEXT, b"abc", fin=False, mask=False)
            + cdp.encode_frame(cdp.OP_PING, b"pi", mask=False)
            + cdp.encode_frame(cdp.OP_CONT, b"def", mask=False)
        )
        self.assertEqual(messages, [(cdp.OP_PING, b"pi"), (cdp.OP_TEXT, "abcdef")])

    def test_continuation_without_a_started_message_is_rejected(self):
        assembler = cdp.MessageAssembler()
        with self.assertRaises(cdp.ProtocolError):
            assembler.feed(cdp.encode_frame(cdp.OP_CONT, b"x", mask=False))

    def test_new_data_frame_during_fragmentation_is_rejected(self):
        assembler = cdp.MessageAssembler()
        with self.assertRaises(cdp.ProtocolError):
            assembler.feed(
                cdp.encode_frame(cdp.OP_TEXT, b"a", fin=False, mask=False)
                + cdp.encode_frame(cdp.OP_TEXT, b"b", mask=False)
            )

    def test_invalid_utf8_in_a_text_message_is_rejected(self):
        assembler = cdp.MessageAssembler()
        with self.assertRaises(cdp.ProtocolError):
            assembler.feed(b"\x81\x02\xff\xfe")

    def test_fragment_accumulation_over_the_limit_is_rejected(self):
        assembler = cdp.MessageAssembler(max_bytes=8)
        with self.assertRaises(cdp.ProtocolError):
            assembler.feed(
                cdp.encode_frame(cdp.OP_TEXT, b"12345", fin=False, mask=False)
                + cdp.encode_frame(cdp.OP_CONT, b"6789", mask=False)
            )

    def test_close_frame_passes_through_and_marks_the_assembler(self):
        assembler = cdp.MessageAssembler()
        messages = assembler.feed(cdp.encode_frame(cdp.OP_CLOSE, struct.pack(">H", 1000), mask=False))
        self.assertEqual(messages, [(cdp.OP_CLOSE, b"\x03\xe8")])
        self.assertTrue(assembler.peer_closed)

    def test_eof_with_a_partial_frame_is_a_protocol_error(self):
        assembler = cdp.MessageAssembler()
        assembler.feed(b"\x81\x05He")
        with self.assertRaises(cdp.ProtocolError):
            assembler.eof()

    def test_eof_with_an_open_fragment_is_a_protocol_error(self):
        assembler = cdp.MessageAssembler()
        assembler.feed(cdp.encode_frame(cdp.OP_TEXT, b"a", fin=False, mask=False))
        with self.assertRaises(cdp.ProtocolError):
            assembler.eof()

    def test_clean_eof_after_complete_messages_is_accepted(self):
        assembler = cdp.MessageAssembler()
        assembler.feed(b"\x81\x00")
        assembler.eof()  # must not raise


class FakeTransport:
    """Stands in for Connection so the id-router is testable without sockets."""

    def __init__(self, script=None):
        self.sent = []
        self._script = list(script or [])

    def send_text(self, text):
        self.sent.append(text)

    def receive_message(self, timeout):
        if self._script:
            return self._script.pop(0)
        raise TimeoutError("script exhausted")

    def close(self):
        pass


class SessionTests(unittest.TestCase):
    def test_send_pairs_request_with_response_over_fake_transport(self):
        transport = FakeTransport([(cdp.OP_TEXT, json.dumps({"id": 1, "result": {"a": 2}}))])
        session = cdp.Session(transport)
        self.assertEqual(session.send("Target.getVersion"), {"a": 2})
        sent = json.loads(transport.sent[0])
        self.assertEqual(sent, {"id": 1, "method": "Target.getVersion", "params": {}})

    def test_send_raises_cdp_error_for_error_responses(self):
        script = [(cdp.OP_TEXT, json.dumps({"id": 1, "error": {"code": -32000, "message": "boom"}}))]
        session = cdp.Session(FakeTransport(script))
        with self.assertRaises(cdp.CDPError) as caught:
            session.send("X.y")
        self.assertEqual(caught.exception.code, -32000)
        self.assertIn("boom", str(caught.exception))

    def test_send_times_out_and_cleans_the_pending_slot(self):
        session = cdp.Session(FakeTransport())
        with self.assertRaises(TimeoutError):
            session.send("X.y", timeout=0.2)
        self.assertEqual(session._pending, {})

    def test_send_includes_session_id_when_given(self):
        script = [(cdp.OP_TEXT, json.dumps({"id": 1, "result": {}}))]
        transport = FakeTransport(script)
        session = cdp.Session(transport)
        session.send("Page.navigate", {"url": "data:text/html,x"}, session="S-1")
        sent = json.loads(transport.sent[0])
        self.assertEqual(sent["sessionId"], "S-1")
        self.assertEqual(sent["params"], {"url": "data:text/html,x"})

    def test_events_arriving_while_awaiting_a_response_are_queued(self):
        script = [
            (cdp.OP_TEXT, json.dumps({"method": "Page.frameStartedLoading", "params": {}})),
            (cdp.OP_TEXT, json.dumps({"id": 1, "result": {}})),
        ]
        session = cdp.Session(FakeTransport(script))
        session.send("Page.navigate")
        methods = [message["method"] for message in session.events]
        self.assertEqual(methods, ["Page.frameStartedLoading"])

    def test_response_routes_to_a_pending_id(self):
        session = cdp.Session(None)
        session._pending[7] = {"response": None, "error": None}
        kind, slot = session.route({"id": 7, "result": {"ok": True}})
        self.assertEqual(kind, "response")
        self.assertEqual(slot["response"]["result"], {"ok": True})

    def test_error_response_flags_the_slot(self):
        session = cdp.Session(None)
        session._pending[7] = {"response": None, "error": None}
        kind, slot = session.route({"id": 7, "error": {"code": -32601, "message": "nope"}})
        self.assertEqual(kind, "response")
        self.assertEqual(slot["error"]["code"], -32601)
        self.assertIsNone(slot["response"])

    def test_unknown_response_id_is_ignored(self):
        session = cdp.Session(None)
        self.assertIsNone(session.route({"id": 99, "result": {}}))

    def test_event_routes_by_method_into_the_queue(self):
        session = cdp.Session(None)
        kind, message = session.route({"method": "Page.loadEventFired", "params": {"ts": 1}})
        self.assertEqual(kind, "event")
        self.assertEqual(message["method"], "Page.loadEventFired")
        self.assertEqual(session.events[-1]["params"], {"ts": 1})

    def test_registered_handler_receives_the_event(self):
        seen = []
        session = cdp.Session(None)
        session.on("Page.loadEventFired", seen.append)
        session.route({"method": "Page.loadEventFired", "params": {}})
        self.assertEqual(seen, [{"method": "Page.loadEventFired", "params": {}}])


class LoopbackGuardTests(unittest.TestCase):
    def test_loopback_ip_is_allowed(self):
        self.assertEqual(cdp.guard_loopback("127.0.0.1"), "127.0.0.1")

    def test_localhost_is_allowed(self):
        self.assertEqual(cdp.guard_loopback("localhost"), "localhost")

    def test_public_ip_is_refused(self):
        with self.assertRaises(cdp.NonLoopbackHost):
            cdp.guard_loopback("203.0.113.1")  # TEST-NET-3, no DNS needed

    def test_ws_url_with_a_non_loopback_host_is_refused(self):
        with self.assertRaises(cdp.NonLoopbackHost):
            cdp.ws_url_parts("ws://203.0.113.1:9222/devtools/browser")

    def test_non_ws_scheme_is_refused(self):
        with self.assertRaises(ValueError):
            cdp.ws_url_parts("http://127.0.0.1:9222/json/version")


if __name__ == "__main__":
    unittest.main()
