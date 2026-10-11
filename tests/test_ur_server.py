"""LineSensorURServer: native uRemote commands served on top of an I2C sensor."""

import ast
from types import SimpleNamespace

import pytest

import fakes
from fakes import frame
from line_sensor import BaseLineSensor, LineSensorI2C
from line_sensor_ur_server import LineSensorURServer

from conftest import REPO_ROOT

STATUS_OK, STATUS_ERR = 0, 1


@pytest.fixture
def server(bench):
    server = LineSensorURServer()
    bench.link("uart1", "hub")
    bench.sensor.log.clear()
    return server


@pytest.fixture
def hub(bench, server):
    """The wire end a client would be attached to."""
    return bench.endpoint("hub")


def client_commands():
    """Every command name LineSensorUR sends, taken from its source."""
    source = (REPO_ROOT / "micropython" / "line_sensor.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    ur = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "LineSensorUR")
    names = set()
    for node in ast.walk(ur):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("call", "_call_bytes", "_call_bool")
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            names.add(node.args[0].value)
    return sorted(names)


class TestConstruction:
    def test_default_uart_settings(self, bench, server):
        settings = bench.endpoint("uart1").init_kwargs
        assert settings["baudrate"] == 115200
        assert settings["timeout"] == 1000
        assert "rx" not in settings and "tx" not in settings

    def test_uart_options_are_passed_through(self, bench):
        LineSensorURServer(uart_id=2, baudrate=57600, uart_timeout=50, rx=3, tx=4)
        settings = bench.endpoint("uart2").init_kwargs
        assert (settings["baudrate"], settings["timeout"]) == (57600, 50)
        assert (settings["rx"], settings["tx"]) == (3, 4)

    def test_it_creates_an_i2c_sensor_on_the_qwiic_pins(self, bench, server):
        assert isinstance(server.sensor, LineSensorI2C)
        bus = bench.i2c_buses[-1]
        assert (bus.i2c_id, bus.scl, bus.sda, bus.freq) == (1, 4, 5, 100000)

    def test_i2c_options_are_passed_through(self, bench):
        LineSensorURServer(i2c_id=0, scl_pin=7, sda_pin=8, i2c_freq=400000, device_addr=0x33)
        bus = bench.i2c_buses[-1]
        assert (bus.i2c_id, bus.scl, bus.sda, bus.freq) == (0, 7, 8, 400000)

    def test_an_existing_sensor_is_used_as_is(self, bench):
        sensor = SimpleNamespace()
        server = LineSensorURServer(sensor=sensor)
        assert server.sensor is sensor
        assert bench.i2c_buses == []


class TestCommandTable:
    @pytest.mark.parametrize("command", client_commands())
    def test_every_command_the_client_sends_is_served(self, server, command):
        assert command in server._handlers, command

    def test_the_client_command_list_was_found(self):
        assert len(client_commands()) >= 25

    @pytest.mark.parametrize(
        "alias, target",
        [
            ("get_version", "version"),
            ("debug_status", "debug"),
            ("save", "save_cal"),
            ("load", "load_cal"),
            ("pdr", "pds"),
            ("emitter", "set_emitter"),
            ("led", "leds"),
        ],
    )
    def test_aliases_share_a_handler(self, server, alias, target):
        assert server._handlers[alias] == server._handlers[target]


class TestReading:
    def test_data_is_the_eight_channel_bytes(self, server, device):
        device.set_reading(values=[1, 2, 3, 4, 5, 6, 7, 8])
        assert server.dispatch("data") == bytes([1, 2, 3, 4, 5, 6, 7, 8])

    def test_pos_shape_and_pds_return_raw_bytes(self, server, device):
        device.set_reading(position=-3, derivative=4, shape="<")
        assert server.dispatch("pos") == 125
        assert server.dispatch("shape") == ord("<")
        assert server.dispatch("pds") == (125, 132, ord("<"))
        assert server.dispatch("pdr") == (125, 132, ord("<"))

    def test_all_is_the_whole_packet(self, server, device):
        assert server.dispatch("all") == device.packet()
        assert len(server.dispatch("all")) == 13

    def test_a_read_sends_no_command_to_the_sensor(self, server, device):
        server.dispatch("all")
        assert device.log == []

    def test_a_short_i2c_read_is_an_error(self, server):
        server.sensor.robust_i2c_readfrom = lambda address, count: b"\x00" * 5
        with pytest.raises(OSError, match="returned 5 bytes, expected 13"):
            server.dispatch("all")

    def test_i2c_errors_are_retried_by_the_sensor_driver(self, server, device):
        device.read_failures = 3
        assert len(server.dispatch("all")) == 13


class TestModes:
    def test_named_commands(self, server, device):
        assert server.dispatch("set_mode_raw") == 0
        assert device.mode == fakes.CMD_SET_MODE_RAW
        assert server.dispatch("set_mode_cal") == 1
        assert device.mode == fakes.CMD_SET_MODE_CAL

    @pytest.mark.parametrize("mode", [0, 1])
    def test_mode_setter(self, server, device, mode):
        assert server.dispatch("mode", mode) == mode
        assert device.mode == mode

    @pytest.mark.parametrize("mode", [2, 3, 4, -1])
    def test_other_modes_are_refused_because_they_would_collide_with_commands(
        self, server, device, mode
    ):
        with pytest.raises(ValueError, match="mode must be 0"):
            server.dispatch("mode", mode)
        assert device.log == []

    def test_mode_cannot_be_read_over_i2c(self, server):
        with pytest.raises(ValueError, match="not available over I2C"):
            server.dispatch("mode")
        with pytest.raises(ValueError, match="not available over I2C"):
            server.dispatch("cur_mode")


class TestCalibration:
    @pytest.mark.parametrize("args, save", [((), False), ((0,), False), ((1,), True), ((True,), True)])
    def test_calibrate(self, server, device, args, save):
        assert server.dispatch("calibrate", *args) == 1
        assert device.calibrating is True
        assert device.calibrate_save is save

    def test_is_calibrated(self, server, device):
        device.calibrated = False
        assert server.dispatch("is_calibrated") == 0
        device.calibrated = True
        assert server.dispatch("is_calibrated") == 1

    def test_save_and_load(self, server, device):
        device.cal_min = [7] * 8
        assert server.dispatch("save_cal") == 1
        assert device.stored_cal[0] == [7] * 8
        device.cal_min = [0] * 8
        assert server.dispatch("load_cal") == 1
        assert device.cal_min == [7] * 8

    def test_limits_round_trip(self, server, device):
        assert server.dispatch("set_cal_min", 1, 2, 3, 4, 5, 6, 7, 8) == 1
        assert server.dispatch("set_cal_max", *([200] * 8)) == 1
        assert server.dispatch("get_cal_min") == bytes([1, 2, 3, 4, 5, 6, 7, 8])
        assert server.dispatch("get_cal_max") == bytes([200] * 8)

    @pytest.mark.parametrize("container", [bytes, bytearray, list, tuple])
    def test_limits_may_arrive_as_one_array_argument(self, server, device, container):
        server.dispatch("set_cal_min", container(range(8)))
        assert device.cal_min == list(range(8))

    @pytest.mark.parametrize("count", [0, 7, 9])
    def test_exactly_eight_limits_are_required(self, server, device, count):
        with pytest.raises(ValueError, match="set_cal_min needs 8 values"):
            server.dispatch("set_cal_min", *([1] * count))
        assert device.log == []

    @pytest.mark.parametrize("bad", [256, -1])
    def test_limits_must_be_bytes(self, server, device, bad):
        with pytest.raises(ValueError, match="0..255"):
            server.dispatch("set_cal_max", *([bad] + [0] * 7))
        assert device.log == []


class TestConfiguration:
    def test_get_config(self, server, device):
        assert server.dispatch("get_config") == bytes(device.config)

    def test_a_short_config_is_an_error(self, server):
        server.sensor.get_config = lambda: (1, 2, 3)
        with pytest.raises(OSError, match="3 config bytes, expected 7"):
            server.dispatch("get_config")

    def test_conf_values(self, server, device):
        assert server.dispatch("get_conf_value", 3) == 5
        assert server.dispatch("set_conf_value", 3, 9) == 1
        assert device.config[3] == 9

    @pytest.mark.parametrize("index", [-1, 7, 255])
    def test_conf_index_is_bounded(self, server, device, index):
        with pytest.raises(ValueError, match="0..6"):
            server.dispatch("get_conf_value", index)
        with pytest.raises(ValueError, match="0..6"):
            server.dispatch("set_conf_value", index, 1)
        assert device.log == []

    @pytest.mark.parametrize("value", [-1, 256])
    def test_conf_value_is_a_byte(self, server, device, value):
        with pytest.raises(ValueError, match="0..255"):
            server.dispatch("set_conf_value", 3, value)

    def test_load_and_save_config(self, server, device):
        assert server.dispatch("load_config") == 1
        assert server.dispatch("save_config") == 1
        assert [c for c, _ in device.log] == [fakes.CMD_LOAD_CONFIG, fakes.CMD_SAVE_CONFIG]

    def test_uid(self, server, device):
        assert server.dispatch("get_uid") == device.UID

    def test_a_short_uid_is_an_error(self, server):
        server.sensor.get_uid = lambda: (1, 2, 3)
        with pytest.raises(OSError, match="3 UID bytes, expected 12"):
            server.dispatch("get_uid")

    def test_version(self, server):
        assert server.dispatch("version") == (5, 6)
        assert server.dispatch("get_version") == (5, 6)


class TestOutputs:
    @pytest.mark.parametrize("value, state", [(1, True), (0, False), (True, True), (7, True)])
    def test_emitter(self, server, device, value, state):
        assert server.dispatch("set_emitter", value) == 1
        assert device.emitter is state

    @pytest.mark.parametrize("mode", [0, 1, 2, 3])
    def test_leds_returns_the_mode(self, server, device, mode):
        assert server.dispatch("leds", mode) == mode
        assert device.leds_mode == mode

    @pytest.mark.parametrize("mode", [4, 255, -1, 256])
    def test_leds_mode_is_bounded(self, server, device, mode):
        with pytest.raises(ValueError):
            server.dispatch("leds", mode)
        assert device.log == []

    def test_leds_cannot_be_read_over_i2c(self, server):
        with pytest.raises(ValueError, match="not available over I2C"):
            server.dispatch("leds")

    @pytest.mark.parametrize("index", [0, 4, 8])
    def test_neopixel(self, server, device, index):
        assert server.dispatch("neopixel", index, 1, 2, 3) == 1
        assert device.neopixels[index] == (1, 2, 3)

    @pytest.mark.parametrize(
        "arguments",
        [(9, 0, 0, 0), (-1, 0, 0, 0), (0, 256, 0, 0), (0, 0, -1, 0), (0, 0, 0, 256)],
    )
    def test_neopixel_is_bounded(self, server, device, arguments):
        with pytest.raises(ValueError):
            server.dispatch("neopixel", *arguments)
        assert device.log == []


class TestPolarity:
    def test_default_is_black_line(self, server):
        assert server.dispatch("blackline") == 1

    @pytest.mark.parametrize("black", [True, False])
    def test_set_and_get(self, server, device, black):
        assert server.dispatch("blackline", black) == int(black)
        assert device.black_line is black
        assert server.dispatch("blackline") == int(black)

    def test_white_line_inverts_readings_in_the_firmware(self, server, device):
        device.set_reading(values=[0, 255, 100, 0, 0, 0, 0, 0])
        server.dispatch("blackline", False)
        assert server.dispatch("data") == bytes([255, 0, 155, 255, 255, 255, 255, 255])


class TestStatusCommands:
    def test_ping_is_the_millisecond_clock(self, server, bench):
        bench.clock.now = 4321
        assert server.dispatch("ping") == 4321

    def test_debug_reports_what_i2c_can_know(self, server, device, bench):
        bench.clock.now = 99
        device.calibrated = True
        device.config[5] = 1
        assert server.dispatch("debug") == (99, -1, 1, 1, -1, 0)
        device.calibrated = False
        device.config[5] = 0
        assert server.dispatch("debug_status") == (99, -1, 0, 0, -1, 0)

    def test_debug_survives_an_unreadable_config(self, server):
        def fail(index):
            raise OSError("i2c")

        server.sensor.get_value = fail
        assert server.dispatch("debug")[3] == 0

    def test_print_echoes(self, server):
        assert server.dispatch("print", "hello") == "hello"


class TestDispatch:
    def test_unknown_commands_are_reported(self, server):
        with pytest.raises(ValueError, match="no_such_command_xyz\\(\\) function not found remotely"):
            server.dispatch("no_such_command_xyz")

    def test_application_functions_in_main_are_served(self, server, monkeypatch):
        import __main__

        monkeypatch.setattr(__main__, "app_hello", lambda name: "hi " + name, raising=False)
        assert server.dispatch("app_hello", "bob") == "hi bob"

    def test_sensor_commands_win_over_application_functions(self, server, monkeypatch):
        import __main__

        monkeypatch.setattr(__main__, "ping", lambda: "shadowed", raising=False)
        assert server.dispatch("ping") != "shadowed"

    def test_non_callables_in_main_are_ignored(self, server, monkeypatch):
        import __main__

        monkeypatch.setattr(__main__, "app_value", 5, raising=False)
        with pytest.raises(ValueError, match="function not found"):
            server.dispatch("app_value")


class TestLastCommands:
    def test_initial_state(self, server):
        assert server.dispatch("last_commands") == ("-", "", 0, "-", "", 0)

    def test_uart_and_i2c_commands_are_tracked(self, server, bench):
        bench.clock.now = 500
        server.dispatch("leds", 2)
        assert server.dispatch("last_commands") == ("leds", "2", 500, "leds", "2", 500)

    def test_diagnostics_do_not_overwrite_the_command_under_investigation(self, server):
        server.dispatch("set_emitter", 1)
        server.dispatch("debug")
        server.dispatch("debug_status")
        server.dispatch("last_commands")
        assert server.dispatch("last_commands")[:2] == ("set_emitter", "1")

    def test_a_failed_command_is_still_recorded(self, server):
        with pytest.raises(ValueError):
            server.dispatch("leds", 9)
        assert server.dispatch("last_commands")[:2] == ("leds", "9")
        assert server.dispatch("last_commands")[3] == "-"  # never reached I2C

    @pytest.mark.parametrize(
        "arguments, text",
        [
            ((), ""),
            ((1, 2, 3), "1, 2, 3"),
            ((True, False), "true, false"),
            ((b"\x0a\xff",), "[0AFF]"),
            ((bytearray(b"\x01"), "x"), "[01], x"),
        ],
    )
    def test_argument_formatting(self, server, arguments, text):
        assert server._format_arguments(arguments) == text

    def test_formatted_arguments_are_cut_at_64_characters(self, server):
        assert len(server._format_arguments(tuple(range(100)))) == 64


class TestProcess:
    def test_idle(self, server, hub):
        assert server.process() is False
        assert hub.rx == b""

    def test_a_request_gets_a_reply(self, server, hub, device):
        hub.write(frame(STATUS_OK, "leds", 3))
        assert server.process() is True
        assert hub.take() == frame(STATUS_OK, "leds", 3)
        assert device.leds_mode == 3

    def test_byte_and_tuple_results(self, server, hub, device):
        hub.write(frame(STATUS_OK, "get_uid"))
        server.process()
        assert hub.take() == frame(STATUS_OK, "get_uid", device.UID)
        hub.write(frame(STATUS_OK, "version"))
        server.process()
        assert hub.take() == frame(STATUS_OK, "version", 5, 6)

    def test_boolean_arguments_survive_the_wire(self, server, hub, device):
        hub.write(frame(STATUS_OK, "blackline", False))
        server.process()
        assert hub.take() == frame(STATUS_OK, "blackline", 0)
        assert device.black_line is False

    def test_a_failing_handler_sends_an_error_reply(self, server, hub):
        hub.write(frame(STATUS_OK, "leds", 9))
        assert server.process() is True
        assert hub.take() == frame(STATUS_ERR, "leds", "leds: LED mode must be in range 0..3")

    def test_an_unknown_command_sends_an_error_reply(self, server, hub):
        hub.write(frame(STATUS_OK, "nonexistent_cmd"))
        assert server.process() is True
        assert hub.take() == frame(
            STATUS_ERR, "nonexistent_cmd", "nonexistent_cmd() function not found remotely"
        )

    def test_an_i2c_failure_becomes_an_error_reply(self, server, hub, device):
        device.read_failures = 99
        hub.write(frame(STATUS_OK, "all"))
        assert server.process() is True
        reply = hub.take()
        assert reply[5] >> 5 == STATUS_ERR  # status bits of the payload header

    def test_garbage_is_dropped_without_a_reply(self, server, hub):
        hub.write(b"\x06<$XXzz")
        assert server.process() is False
        assert hub.take() == b""

    def test_requests_are_handled_one_per_call(self, server, hub):
        hub.write(frame(STATUS_OK, "set_emitter", 1))
        server.process()
        hub.take()
        hub.write(frame(STATUS_OK, "set_emitter", 0))
        server.process()
        assert hub.take() == frame(STATUS_OK, "set_emitter", 1)

    def test_the_uart_command_is_recorded(self, server, hub):
        hub.write(frame(STATUS_OK, "leds", 1))
        server.process()
        assert server._last_uart_command == "leds"


class TestRunForever:
    def run(self, server, idle_ms, polls=3):
        count = {"n": 0}

        def process():
            count["n"] += 1
            if count["n"] == polls:
                raise KeyboardInterrupt

        server.process = process
        with pytest.raises(KeyboardInterrupt):
            server.run_forever(idle_ms)
        return count["n"]

    def test_idle_time_is_slept_between_polls(self, server, bench):
        assert self.run(server, idle_ms=5) == 3
        assert bench.clock.now == 10  # the third poll interrupts before its sleep

    def test_no_idle_time_by_default(self, server, bench):
        self.run(server, idle_ms=0)
        assert bench.clock.now == 0

    def test_negative_idle_time_is_clamped(self, server, bench):
        self.run(server, idle_ms=-5)
        assert bench.clock.now == 0
