"""Run example programs on the simulated chain (hub -> UART -> server -> sensor)."""

import asyncio
import sys
import types

import pytest

import fakes
import line_sensor
import line_sensor_pybricks as bundle
from fakes import StopProgram
from line_sensor_ur_server import LineSensorURServer

from conftest import REPO_ROOT, load_module

EV3_DIR = REPO_ROOT / "examples" / "ev3-robocup"


class FakeScreen:
    def __init__(self):
        self.calls = []

    def clear(self):
        self.calls.append(("clear",))

    def draw_text(self, x, y, text, *args):
        self.calls.append(("text", text))

    def draw_line(self, x1, y1, x2, y2, width=1, *args):
        self.calls.append(("line", x1, y1, x2, y2))

    def draw_circle(self, x, y, r, fill=False, *args):
        self.calls.append(("circle", x, y, r, fill))

    def texts(self):
        return [call[1] for call in self.calls if call[0] == "text"]


class FakeMotor:
    instances = []

    def __init__(self, port, direction=None):
        self.port = port
        self.duty = []
        self.stopped = 0
        FakeMotor.instances.append(self)

    def dc(self, value):
        self.duty.append(value)

    def stop(self):
        self.stopped += 1
        self.duty.append(None)


class FakeEV3Brick:
    last = None
    center_presses = 0  # the first N polls of the buttons report CENTER pressed

    def __init__(self):
        self.screen = FakeScreen()
        self.polls = 0
        self.buttons = types.SimpleNamespace(pressed=self._pressed)
        FakeEV3Brick.last = self

    def _pressed(self):
        self.polls += 1
        return {"CENTER"} if self.polls <= self.center_presses else set()


async def multitask(*awaitables, race=False):
    """Pybricks multitask(): run the awaitables together."""
    tasks = [asyncio.ensure_future(a) for a in awaitables]
    when = asyncio.FIRST_COMPLETED if race else asyncio.ALL_COMPLETED
    done, pending = await asyncio.wait(tasks, return_when=when)
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    failures = [task.exception() for task in done if task.exception()]
    if failures:
        raise failures[0]
    return [task.result() for task in tasks]


@pytest.fixture
def ev3(monkeypatch, bench, device):
    """A simulated EV3 whose line sensor is on port S1, behind an LMS-ESP32."""
    FakeMotor.instances = []

    hubs = types.ModuleType("pybricks.hubs")
    hubs.EV3Brick = FakeEV3Brick
    ev3devices = types.ModuleType("pybricks.ev3devices")
    ev3devices.Motor = FakeMotor
    monkeypatch.setitem(sys.modules, "pybricks.hubs", hubs)
    monkeypatch.setitem(sys.modules, "pybricks.ev3devices", ev3devices)

    parameters = sys.modules["pybricks.parameters"]
    monkeypatch.setattr(parameters, "Button", types.SimpleNamespace(CENTER="CENTER"), raising=False)
    monkeypatch.setattr(parameters, "Color", types.SimpleNamespace(BLACK="BLACK", WHITE="WHITE"), raising=False)
    monkeypatch.setattr(
        parameters, "Direction", types.SimpleNamespace(CLOCKWISE=1, COUNTERCLOCKWISE=-1), raising=False
    )

    tools = sys.modules["pybricks.tools"]
    monkeypatch.setattr(tools, "multitask", multitask, raising=False)
    run = fakes.install_run_task(monkeypatch, bench, bundle, [bundle, line_sensor, tools], limit_ms=8000)

    server = LineSensorURServer()
    bench.link("uart1", "portS1")
    bench.endpoint("uart1").on_data = server.process
    device.log.clear()
    return types.SimpleNamespace(bench=bench, device=device, run=run, server=server)


def run_example(name):
    """Execute an example until the fake clock stops it; return the stopped program."""
    path = EV3_DIR / name
    with pytest.raises(StopProgram):
        load_module("example_" + path.stem, path)
    program = sys.modules.pop("example_" + path.stem)
    return program


class TestAsyncLineFollower:
    NAME = "p_controller_line_mower_async.py"

    def motors(self):
        left, right = FakeMotor.instances
        return left, right

    def drive_values(self, motor):
        return [value for value in motor.duty if value is not None]

    def test_it_steers_with_the_p_controller(self, ev3):
        ev3.device.set_reading(position=50, shape="|")
        run_example(self.NAME)
        left, right = self.motors()
        assert self.drive_values(left)[-1] == pytest.approx(30 + 50 * 0.8)
        assert self.drive_values(right)[-1] == pytest.approx(30 - 50 * 0.8)

    def test_it_steers_the_other_way_for_a_line_on_the_left(self, ev3):
        ev3.device.set_reading(position=-50, shape="|")
        run_example(self.NAME)
        left, right = self.motors()
        assert self.drive_values(left)[-1] < self.drive_values(right)[-1]

    def test_it_stops_on_white(self, ev3):
        ev3.device.set_reading(position=0, shape=" ")
        run_example(self.NAME)
        left, right = self.motors()
        assert self.drive_values(left)[-1] == 0
        assert self.drive_values(right)[-1] == 0

    def test_the_motors_are_stopped_when_the_program_ends(self, ev3):
        run_example(self.NAME)
        left, right = self.motors()
        assert left.duty[-1] is None and right.duty[-1] is None

    def test_the_sensor_is_prepared_before_driving(self, ev3):
        run_example(self.NAME)
        commands = [number for number, _ in ev3.device.log]
        assert fakes.CMD_LOAD_CAL in commands
        assert fakes.CMD_SET_EMITTER in commands
        assert ev3.device.emitter is True
        assert ev3.device.mode == fakes.CMD_SET_MODE_CAL

    @pytest.mark.parametrize("position, look", [(100, 6), (-100, -7), (0, 0)])
    def test_the_eyes_look_where_the_line_is(self, ev3, position, look):
        ev3.device.set_reading(position=position, shape="|")
        run_example(self.NAME)
        pupils = [
            c for c in FakeEV3Brick.last.screen.calls if c[0] == "circle" and c[4] and c[3] == 8
        ]
        assert [pupils[-2][1], pupils[-1][1]] == [59 + look, 119 + look]

    def test_the_position_dot_tracks_the_line(self, ev3):
        ev3.device.set_reading(position=64, shape="|")
        run_example(self.NAME)
        dots = [c for c in FakeEV3Brick.last.screen.calls if c[0] == "circle" and c[3] == 4]
        assert dots[-1][1] == 89 + 64 * 80 // 128

    def test_the_face_is_only_redrawn_when_something_changes(self, ev3):
        run_example(self.NAME)
        screen = FakeEV3Brick.last.screen
        redraws = sum(1 for c in screen.calls if c == ("clear",))
        assert 1 <= redraws < 20  # 3 s of 40 ms frames would be 75 if drawn blindly

    def test_a_lost_line_makes_the_face_surprised(self, ev3):
        ev3.device.set_reading(shape=" ")
        run_example(self.NAME)
        mouths = [c for c in FakeEV3Brick.last.screen.calls if c[0] == "circle" and c[3] == 10]
        assert mouths

    def test_the_face_keeps_animating_while_calibrating(self, ev3, monkeypatch):
        """CENTER starts calibration; the screen reacts while the driver waits."""
        ev3.device.config[3] = 1  # one second of calibration (plus one second slack)
        monkeypatch.setattr(FakeEV3Brick, "center_presses", 1)
        run_example(self.NAME)

        assert fakes.CMD_CALIBRATE in [number for number, _ in ev3.device.log]
        assert ev3.device.calibrate_save is True

        screen = FakeEV3Brick.last.screen
        texts = screen.texts()
        first = next(i for i, t in enumerate(texts) if "Calibrating" in t)
        assert any("CENTER = calibrate" in t for t in texts[first:]), "face did not return"

        # Drawing continued during the calibration wait: the dizzy face and the
        # wobbly mouth were drawn, not just a frozen "Calibrating" message.
        crosses = [c for c in screen.calls if c[0] == "line" and c[1] != c[3] and c[2] != c[4]]
        assert crosses, "dizzy X eyes were not drawn"

    def test_the_robot_stops_while_calibrating_and_drives_again_afterwards(self, ev3, monkeypatch):
        ev3.device.config[3] = 1
        ev3.device.set_reading(position=20, shape="|")
        monkeypatch.setattr(FakeEV3Brick, "center_presses", 1)
        run_example(self.NAME)
        left, _ = self.motors()
        first_stop = left.duty.index(None)
        assert any(value is not None for value in left.duty[first_stop:]), "it never drove again"
