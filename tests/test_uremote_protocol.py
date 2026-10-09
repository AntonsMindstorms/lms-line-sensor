"""The uRemote wire protocol, checked against three implementations.

``firmware``  micropython/vendor/uremote.py (LMS-ESP32, OpenMV, Pybricks)
``pybricks``  micropython/vendor/uremote_pybricks.py (hub-only trim)
``desktop``   usb/uremote.py (pyserial)

Frames are built and checked with the independent encoder in ``fakes.py``.
"""

import importlib
import sys
import types
from types import SimpleNamespace

import pytest

import fakes
from fakes import frame

STATUS_OK, STATUS_ERR = 0, 1


@pytest.fixture(params=["firmware", "pybricks", "desktop"])
def impl(request, bench, desktop_uremote):
    """(client, peer, module) with ``peer`` wired to the client's UART."""
    if request.param == "firmware":
        module = importlib.import_module("uremote")
        client = module.uRemote(5)
        peer = bench.link("uart5", "peer")[1]
    elif request.param == "pybricks":
        module = importlib.import_module("uremote_pybricks")
        client = module.uRemote("B")
        peer = bench.link("portB", "peer")[1]
    else:
        module = desktop_uremote
        port, peer = bench.link("serial", "peer")
        client = module.uRemote("COM1", serial_instance=port, settle_time=0, wait_recv=30)
    client.kind = request.param
    return SimpleNamespace(client=client, peer=peer, module=module, kind=request.param)


def script_reply(peer, *replies):
    """Answer each request the client sends with the next scripted reply."""
    sent = []
    queue = list(replies)

    def respond():
        sent.append(peer.take())
        if queue:
            peer.write(queue.pop(0))

    peer.on_data = respond
    return sent


ARGUMENT_SETS = [
    (),
    (0,),
    (-5,),
    (123456789,),
    (True,),
    (False,),
    (b"",),
    (b"\x00\xff\x10",),
    ("",),
    ("abc",),
    (1, True, b"x", "s"),
    tuple(range(8)),
]


class TestEncoding:
    @pytest.mark.parametrize("arguments", ARGUMENT_SETS)
    def test_payload_matches_the_reference_encoder(self, impl, arguments):
        assert impl.client._encode(STATUS_OK, "cmd", *arguments) == fakes.encode_payload(
            STATUS_OK, "cmd", *arguments
        )

    def test_status_lives_in_the_top_three_bits_of_the_header(self, impl):
        payload = impl.client._encode(STATUS_ERR, "x")
        assert payload[0] == (1 << 5) | 1

    def test_booleans_are_not_sent_as_numbers(self, impl):
        assert impl.client._encode(0, "b", True)[2] == ord("B")

    def test_overlong_command_name_is_rejected(self, impl):
        with pytest.raises(impl.module.uRemoteError):
            impl.client._encode(0, "x" * 32)

    def test_longest_command_name_is_accepted(self, impl):
        assert impl.client._encode(0, "x" * 31)[0] & 0x1F == 31

    @pytest.mark.parametrize("argument", [1.5, None, [1], (1,)])
    def test_unsupported_argument_types(self, impl, argument):
        with pytest.raises(TypeError):
            impl.client._encode(0, "cmd", argument)

    def test_packet_has_a_length_byte_and_preamble(self, impl):
        packet = impl.client._packet(b"payload")
        assert packet == bytes([4 + 7]) + b"<$MU" + b"payload"

    def test_oversized_frames_are_rejected(self, impl):
        impl.client._packet(b"x" * 251)  # 255 bytes with the preamble: allowed
        with pytest.raises(impl.module.uRemoteError, match="too large"):
            impl.client._packet(b"x" * 252)


class TestDecoding:
    @pytest.mark.parametrize(
        "arguments, expected",
        [
            ((), []),
            ((7,), 7),
            ((-7,), -7),
            ((True,), True),
            ((b"\x01\x02",), b"\x01\x02"),
            (("hi",), "hi"),
            ((1, 2, 3), [1, 2, 3]),
            ((1, b"a", "s", False), [1, b"a", "s", False]),
        ],
    )
    def test_arguments_come_back_as_sent(self, impl, arguments, expected):
        payload = fakes.encode_payload(STATUS_OK, "cmd", *arguments)
        assert impl.client._decode(payload) == (STATUS_OK, "cmd", expected)

    def test_status_is_decoded(self, impl):
        payload = fakes.encode_payload(STATUS_ERR, "cmd", "boom")
        assert impl.client._decode(payload) == (STATUS_ERR, "cmd", "boom")

    def test_booleans_decode_to_booleans(self, impl):
        _, _, value = impl.client._decode(fakes.encode_payload(0, "c", True))
        assert value is True

    def test_empty_input_reports_the_last_receive_error(self, impl):
        assert impl.client._decode_command(b"") == (STATUS_ERR, "", "no bytes received")

    def test_unknown_argument_type_is_a_decode_error(self, impl):
        payload = bytes([3]) + b"cmd" + bytes([ord("Z"), 1, 0])
        status, command, message = impl.client._decode_command(payload)
        assert (status, command) == (STATUS_ERR, "")
        assert message.startswith("decode error")

    def test_a_cut_off_argument_header_is_a_decode_error(self, impl):
        payload = fakes.encode_payload(0, "cmd", 12345)[:5]  # type byte, no length
        status, _, message = impl.client._decode_command(payload)
        assert status == STATUS_ERR
        assert message.startswith("decode error")


class TestCall:
    def test_the_request_frame_is_exactly_as_specified(self, impl):
        sent = script_reply(impl.peer, frame(STATUS_OK, "leds", 2))
        impl.client.call("leds", 2)
        assert sent == [frame(STATUS_OK, "leds", 2)]

    @pytest.mark.parametrize(
        "reply_args, expected",
        [
            ((), None),
            ((5,), 5),
            ((b"\x01\x02",), b"\x01\x02"),
            (("text",), "text"),
            ((1, 2, 3), (1, 2, 3)),
        ],
    )
    def test_results_are_none_a_scalar_or_a_tuple(self, impl, reply_args, expected):
        script_reply(impl.peer, frame(STATUS_OK, "cmd", *reply_args))
        assert impl.client.call("cmd") == expected

    def test_an_error_reply_raises_with_the_remote_message(self, impl):
        script_reply(impl.peer, frame(STATUS_ERR, "cmd", "cmd: nope"))
        with pytest.raises(impl.module.uRemoteError, match="cmd: nope"):
            impl.client.call("cmd")

    def test_a_reply_to_another_command_is_an_error(self, impl):
        script_reply(impl.peer, frame(STATUS_OK, "other", 1))
        with pytest.raises(impl.module.uRemoteError, match="unexpected reply: other"):
            impl.client.call("cmd")

    def test_no_reply_times_out(self, impl):
        with pytest.raises(impl.module.uRemoteError, match="No data"):
            impl.client.call("cmd")

    def test_bad_preamble(self, impl):
        bad = bytes([4 + 2]) + b"<$XX" + b"ab"
        script_reply(impl.peer, bad)
        with pytest.raises(impl.module.uRemoteError, match="Preamble mismatch"):
            impl.client.call("cmd")

    @pytest.mark.parametrize("length", [0, 4])
    def test_invalid_frame_length(self, impl, length):
        script_reply(impl.peer, bytes([length]) + b"<$MUxyz")
        with pytest.raises(impl.module.uRemoteError, match="Invalid frame length"):
            impl.client.call("cmd")

    def test_truncated_frame_times_out(self, impl):
        good = frame(STATUS_OK, "cmd", 1)
        script_reply(impl.peer, good[:-2])
        with pytest.raises(impl.module.uRemoteError, match="Inter-byte|Incomplete"):
            impl.client.call("cmd")

    def test_stale_bytes_are_discarded_before_a_call(self, impl):
        impl.client.uart.rx.extend(b"stale garbage")
        script_reply(impl.peer, frame(STATUS_OK, "cmd", 9))
        assert impl.client.call("cmd") == 9

    def test_the_client_recovers_after_an_error(self, impl):
        script_reply(
            impl.peer,
            frame(STATUS_ERR, "cmd", "bad"),
            frame(STATUS_OK, "cmd", 3),
        )
        with pytest.raises(impl.module.uRemoteError):
            impl.client.call("cmd")
        assert impl.client.call("cmd") == 3

    def test_exchange_returns_the_raw_reply_without_raising(self, impl):
        script_reply(impl.peer, frame(STATUS_ERR, "cmd", "bad"))
        assert impl.client.exchange("cmd") == (STATUS_ERR, "cmd", "bad")

    def test_a_frame_split_across_reads_is_reassembled(self, impl):
        good = frame(STATUS_OK, "cmd", 1, 2)
        sent = []

        def respond():
            sent.append(impl.peer.take())
            impl.peer.write(good[:5])
            impl.peer.write(good[5:])

        impl.peer.on_data = respond
        assert impl.client.call("cmd") == (1, 2)


class TestServerSide:
    """``uRemote.process()`` exists only in the full firmware library."""

    @pytest.fixture
    def server(self, bench):
        module = importlib.import_module("uremote")
        server = module.uRemote(1)
        peer = bench.link("uart1", "peer")[1]
        return SimpleNamespace(server=server, peer=peer, module=module)

    @pytest.fixture
    def main(self, monkeypatch):
        import __main__

        def register(name, function):
            monkeypatch.setattr(__main__, name, function, raising=False)

        return register

    def test_an_idle_process_call_returns_immediately(self, server):
        server.server.process()
        assert server.peer.rx == b""

    def test_a_request_calls_the_function_in_main(self, server, main):
        main("add_numbers", lambda a, b: a + b)
        server.peer.write(frame(STATUS_OK, "add_numbers", 2, 3))
        server.server.process()
        assert server.peer.take() == frame(STATUS_OK, "add_numbers", 5)

    def test_a_tuple_result_is_sent_as_several_values(self, server, main):
        main("pair", lambda: (1, "x"))
        server.peer.write(frame(STATUS_OK, "pair"))
        server.server.process()
        assert server.peer.take() == frame(STATUS_OK, "pair", 1, "x")

    def test_none_is_an_empty_reply(self, server, main):
        main("nothing", lambda: None)
        server.peer.write(frame(STATUS_OK, "nothing"))
        server.server.process()
        assert server.peer.take() == frame(STATUS_OK, "nothing")

    def test_an_unknown_command_is_an_error_reply(self, server):
        server.peer.write(frame(STATUS_OK, "does_not_exist_anywhere"))
        server.server.process()
        assert server.peer.take() == frame(
            STATUS_ERR,
            "does_not_exist_anywhere",
            "does_not_exist_anywhere() function not found remotely",
        )

    def test_a_failing_handler_is_an_error_reply(self, server, main):
        def broken():
            raise ValueError("bad input")

        main("broken", broken)
        server.peer.write(frame(STATUS_OK, "broken"))
        server.server.process()
        assert server.peer.take() == frame(STATUS_ERR, "broken", "broken: bad input")

    def test_garbage_is_ignored(self, server):
        server.peer.write(b"\x05<$XXjunk")
        server.server.process()
        assert server.peer.take() == b""


class TestDesktopClient:
    """Behaviour specific to usb/uremote.py."""

    @pytest.fixture
    def client(self, bench, desktop_uremote):
        port, peer = bench.link("serial", "peer")
        client = desktop_uremote.uRemote(
            "COM1", serial_instance=port, settle_time=0, wait_recv=30
        )
        return SimpleNamespace(client=client, port=port, peer=peer, module=desktop_uremote)

    def test_a_truncated_argument_is_detected(self, client):
        payload = fakes.encode_payload(0, "cmd", 12345)[:-2]
        status, _, message = client.client._decode_command(payload)
        assert status == STATUS_ERR
        assert "invalid argument length" in message

    def test_the_conventional_alias(self, client):
        assert client.module.URemote is client.module.uRemote

    def test_non_ascii_text_is_length_prefixed_in_bytes(self, client):
        payload = client.client._encode(0, "c", "é")
        assert payload[-4:] == bytes([ord("S"), 2]) + "é".encode()

    def test_a_command_name_is_required(self, client):
        with pytest.raises(client.module.uRemoteError):
            client.client._encode(0, "")

    def test_arguments_over_255_bytes_are_rejected(self, client):
        with pytest.raises(client.module.uRemoteError, match="too large"):
            client.client._encode(0, "c", b"x" * 256)

    def test_bytearray_and_memoryview_are_sent_as_bytes(self, client):
        expected = fakes.encode_payload(0, "c", b"ab")
        assert client.client._encode(0, "c", bytearray(b"ab")) == expected
        assert client.client._encode(0, "c", memoryview(b"ab")) == expected

    def test_the_context_manager_closes_the_port(self, client):
        with client.client:
            assert client.port.is_open
        assert not client.port.is_open

    def test_closing_twice_is_harmless(self, client):
        client.client.close()
        client.client.close()
        assert not client.port.is_open

    def test_a_short_write_is_an_error(self, client):
        client.port.write = lambda data: len(data) - 1
        with pytest.raises(client.module.uRemoteError, match="incomplete"):
            client.client.call("cmd")

    def test_a_failing_write_is_an_error(self, client):
        def broken(data):
            raise OSError("unplugged")

        client.port.write = broken
        with pytest.raises(client.module.uRemoteError, match="Serial write failed"):
            client.client.call("cmd")


def install_fake_pyserial(monkeypatch, ports=(), open_error=None):
    serial = types.ModuleType("serial")
    tools = types.ModuleType("serial.tools")
    list_ports = types.ModuleType("serial.tools.list_ports")

    class SerialException(Exception):
        pass

    opened = []

    def Serial(**kwargs):
        if open_error:
            raise SerialException(open_error)
        port = fakes.FakeUART("serial")
        port.init_kwargs = kwargs
        opened.append(port)
        return port

    serial.Serial = Serial
    serial.SerialException = SerialException
    serial.tools = tools
    tools.list_ports = list_ports
    list_ports.comports = lambda: list(ports)
    for name, module in [
        ("serial", serial),
        ("serial.tools", tools),
        ("serial.tools.list_ports", list_ports),
    ]:
        monkeypatch.setitem(sys.modules, name, module)
    return opened


def port_info(device, description="USB Serial", manufacturer=None):
    return SimpleNamespace(device=device, description=description, manufacturer=manufacturer)


class TestDesktopSerialPorts:
    def test_opening_a_port_uses_the_line_sensor_serial_settings(self, monkeypatch, desktop_uremote):
        opened = install_fake_pyserial(monkeypatch)
        desktop_uremote.uRemote("COM7", settle_time=0)
        assert opened[0].init_kwargs["port"] == "COM7"
        assert opened[0].init_kwargs["baudrate"] == 115200

    def test_open_failure_names_the_port(self, monkeypatch, desktop_uremote):
        install_fake_pyserial(monkeypatch, open_error="busy")
        with pytest.raises(desktop_uremote.uRemoteError, match="Cannot open COM7: busy"):
            desktop_uremote.uRemote("COM7", settle_time=0)

    def test_missing_pyserial_is_explained(self, monkeypatch, desktop_uremote):
        monkeypatch.setitem(sys.modules, "serial", None)
        with pytest.raises(desktop_uremote.uRemoteError, match="pip install pyserial"):
            desktop_uremote.uRemote("COM7", settle_time=0)
        with pytest.raises(desktop_uremote.uRemoteError, match="pip install pyserial"):
            desktop_uremote.list_serial_ports()

    def test_ports_are_sorted_case_insensitively(self, monkeypatch, desktop_uremote):
        install_fake_pyserial(
            monkeypatch, ports=[port_info("/dev/ttyUSB1"), port_info("/dev/ttyACM0"), port_info("COM3")]
        )
        devices = [p.device for p in desktop_uremote.list_serial_ports()]
        assert devices == ["/dev/ttyACM0", "/dev/ttyUSB1", "COM3"]

    def test_selecting_a_port_retries_until_the_answer_is_valid(self, monkeypatch, desktop_uremote):
        install_fake_pyserial(
            monkeypatch,
            ports=[port_info("COM3", manufacturer="WCH"), port_info("COM5")],
        )
        answers = iter(["", "x", "0", "3", " 2 "])
        printed = []
        chosen = desktop_uremote.select_serial_port(
            input_fn=lambda prompt: next(answers), output_fn=printed.append
        )
        assert chosen == "COM5"
        assert any("COM3" in line and "WCH" in line for line in printed)
        assert printed.count("Please enter one of the listed numbers.") == 4

    def test_no_ports_is_an_error(self, monkeypatch, desktop_uremote):
        install_fake_pyserial(monkeypatch, ports=[])
        with pytest.raises(desktop_uremote.uRemoteError, match="No serial ports"):
            desktop_uremote.select_serial_port(input_fn=lambda _: "1", output_fn=lambda _: None)
