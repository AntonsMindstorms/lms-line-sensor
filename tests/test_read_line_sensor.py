"""usb/read_line_sensor.py: the desktop command-line reader."""

import sys

import pytest

from conftest import REPO_ROOT, load_module

SPACE = 32


class FakeSensor:
    """Stands in for the URemote context manager."""

    def __init__(self, packets, uid=bytes(range(12))):
        self.packets = list(packets)
        self.uid = uid
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def call(self, command):
        self.calls.append(command)
        if command == "get_uid":
            return self.uid
        if command == "all":
            return self.packets.pop(0)
        return None


def packet(position=128, shape=ord("|"), values=(1, 2, 3, 4, 5, 6, 7, 8), minimum=3, maximum=250):
    return bytes(list(values) + [position, minimum, maximum, 128, shape])


@pytest.fixture
def cli(monkeypatch, desktop_uremote):
    """The script, loaded against the desktop uRemote, ready to run with fakes."""
    monkeypatch.setitem(sys.modules, "uremote", desktop_uremote)
    module = load_module("read_line_sensor", REPO_ROOT / "usb" / "read_line_sensor.py")
    monkeypatch.delitem(sys.modules, "read_line_sensor", raising=False)

    class Run:
        def __init__(self):
            self.module = module
            self.sensor = None
            self.opened = []
            self.sleeps = []

        def start(self, *argv, packets=(), uid=None, stop_after=None):
            sensor = FakeSensor(packets) if uid is None else FakeSensor(packets, uid)
            self.sensor = sensor

            def open_port(port):
                self.opened.append(port)
                return sensor

            def sleep(seconds):
                self.sleeps.append(seconds)
                if not sensor.packets:
                    raise KeyboardInterrupt

            monkeypatch.setattr(module, "URemote", open_port)
            monkeypatch.setattr(module.time, "sleep", sleep)
            monkeypatch.setattr(sys, "argv", ["read_line_sensor.py", *argv])
            return module.main()

    return Run()


def test_reads_until_interrupted_and_reports_a_clean_stop(cli, capsys):
    status = cli.start("--port", "COM9", packets=[packet(), packet()])
    out = capsys.readouterr().out
    assert status == 0
    assert cli.opened == ["COM9"]
    assert out.count("values=") == 2
    assert out.rstrip().endswith("Stopped.")


def test_the_uid_is_printed_in_upper_case_hex(cli, capsys):
    cli.start("--port", "X", packets=[packet()])
    assert "Sensor UID: 000102030405060708090A0B" in capsys.readouterr().out


def test_a_reading_line_shows_values_limits_and_shape(cli, capsys):
    cli.start("--port", "X", packets=[packet(shape=ord("T"))])
    line = [l for l in capsys.readouterr().out.splitlines() if l.startswith("values=")][0]
    assert "values=[1, 2, 3, 4, 5, 6, 7, 8]" in line
    assert "min=  3" in line and "max=250" in line
    assert line.endswith("shape=T")


def test_a_blank_shape_is_shown_as_none(cli, capsys):
    cli.start("--port", "X", packets=[packet(shape=SPACE)])
    assert "shape=None" in capsys.readouterr().out


@pytest.mark.parametrize("raw, shown", [(0, -128), (255, 128), (64, -64)])
def test_position_uses_the_documented_conversion(cli, capsys, raw, shown):
    """firmware/README.md: round(position_byte * 256 / 255 - 128)."""
    cli.start("--port", "X", packets=[packet(position=raw)])
    assert "position=%4d" % shown in capsys.readouterr().out


@pytest.mark.parametrize(
    "arguments, expected",
    [
        ((), ["get_uid", "all"]),
        (("--mode", "current"), ["get_uid", "all"]),
        (("--mode", "raw"), ["set_mode_raw", "get_uid", "all"]),
        (("--mode", "calibrated"), ["set_mode_cal", "get_uid", "all"]),
    ],
)
def test_mode_option(cli, arguments, expected):
    cli.start("--port", "X", *arguments, packets=[packet()])
    assert cli.sensor.calls == expected


def test_interval_is_the_sleep_between_reads(cli):
    cli.start("--port", "X", "--interval", "0.5", packets=[packet(), packet()])
    assert cli.sleeps == [0.5, 0.5]


@pytest.mark.parametrize("interval", ["0", "-1"])
def test_non_positive_interval_is_rejected(cli, interval):
    with pytest.raises(SystemExit, match="greater than zero"):
        cli.start("--port", "X", "--interval", interval)


def test_without_a_port_option_the_user_chooses(cli, monkeypatch):
    monkeypatch.setattr(cli.module, "select_serial_port", lambda: "/dev/ttyACM3")
    cli.start(packets=[packet()])
    assert cli.opened == ["/dev/ttyACM3"]


def test_an_invalid_uid_is_an_error(cli, capsys):
    assert cli.start("--port", "X", packets=[packet()], uid="not bytes") == 1
    assert "get_uid returned invalid data" in capsys.readouterr().out


@pytest.mark.parametrize("bad", [b"short", None, "text"])
def test_an_invalid_packet_is_an_error(cli, capsys, bad):
    assert cli.start("--port", "X", packets=[bad]) == 1
    assert "invalid sensor packet" in capsys.readouterr().out


def test_connection_errors_are_reported_not_raised(cli, monkeypatch, capsys):
    def refuse(port):
        raise cli.module.uRemoteError("Cannot open X")

    monkeypatch.setattr(cli.module, "URemote", refuse)
    monkeypatch.setattr(sys, "argv", ["read_line_sensor.py", "--port", "X"])
    assert cli.module.main() == 1
    assert "uRemote error: Cannot open X" in capsys.readouterr().out
