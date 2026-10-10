"""Async use: inside Pybricks ``run_task()`` every LineSensorUR call is awaitable.

The driver detects this itself (see ``BaseLineSensor._then``); there are no
separate async methods. Outside ``run_task()`` the same calls return plain
values.
"""

import asyncio

import pytest

import fakes
import line_sensor
import line_sensor_pybricks as bundle
from fakes import CONFIG, ScriptedRemote
from line_sensor import LineSensorUR
from line_sensor_ur_server import LineSensorURServer


class AsyncRemote(ScriptedRemote):
    """uRemote under run_task(): call() returns an awaitable, nothing is sent
    until it runs."""

    def call(self, command, *arguments):
        async def reply():
            await asyncio.sleep(0)
            return ScriptedRemote.call(self, command, *arguments)

        return reply()


def run(awaitable):
    async def main():
        return await awaitable

    return asyncio.run(main())


@pytest.fixture
def waits(monkeypatch):
    """Replace line_sensor.wait with an awaitable one that records its argument."""
    recorded = []

    async def fake_wait(milliseconds):
        recorded.append(milliseconds)

    monkeypatch.setattr(line_sensor, "wait", fake_wait)
    return recorded


@pytest.fixture
def sensor():
    driver = LineSensorUR("B", settle_ms=0, remote_class=AsyncRemote)
    return driver


class TestAwaitableDriver:
    def test_the_constructor_defers_the_config_read_until_awaited(self, sensor):
        assert sensor.version is None and sensor.cal_duration is None
        assert sensor.ur.calls == []  # nothing was sent yet
        assert run(sensor.get_config()) == tuple(CONFIG)
        assert sensor.version == "5.6"
        assert sensor.cal_duration == 4

    def test_reads_are_awaitable_and_decoded(self, sensor):
        assert run(sensor.position()) == 72
        assert run(sensor.sensors()) == (10, 20, 30, 40, 50, 60, 70, 80)
        assert run(sensor.position_derivative_shape()) == (72, -28, "T")
        assert run(sensor.is_calibrated()) is True
        assert run(sensor.blackline()) is True
        assert run(sensor.get_uid()) == tuple(range(12))
        assert run(sensor.uid_hex()) == "000102030405060708090a0b"
        assert run(sensor.get_configuration())["cal_duration"] == 4

    def test_the_settle_time_is_awaited(self, sensor, waits):
        sensor.settle_ms = 2
        assert run(sensor.shape()) == "T"
        assert waits == [2]

    def test_calibrate_awaits_every_step_in_order(self, sensor, waits):
        assert run(sensor.calibrate()) is True
        assert [command for command, _ in sensor.ur.calls] == [
            "leds",
            "calibrate",
            "get_config",  # learns the duration: the constructor could not await it
            "is_calibrated",
        ]
        assert waits == [5000]

    def test_calibrate_with_an_explicit_duration_skips_the_config_read(self, sensor, waits):
        run(sensor.calibrate(duration=2))
        assert "get_config" not in [command for command, _ in sensor.ur.calls]
        assert waits == [3000]

    def test_set_calibration_sends_both_tables(self, sensor):
        run(sensor.set_calibration([0] * 8, [255] * 8))
        assert [command for command, _ in sensor.ur.calls] == ["set_cal_min", "set_cal_max"]

    @pytest.mark.parametrize(
        "call",
        [
            lambda s: s.position(),
            lambda s: s.mode(1),
            lambda s: s.mode_raw(),
            lambda s: s.leds(1),
            lambda s: s.ir_power(True),
            lambda s: s.neopixel(0, 1, 2, 3),
            lambda s: s.save_calibration(),
            lambda s: s.load_calibration(),
            lambda s: s.start_calibration(),
            lambda s: s.get_cal_min(),
            lambda s: s.set_cal_duration(3),
            lambda s: s.load_config(),
        ],
    )
    def test_every_command_is_awaitable_in_async_mode(self, sensor, call):
        result = call(sensor)
        assert hasattr(result, "send"), "expected an awaitable, got %r" % (result,)
        run(result)
        assert len(sensor.ur.calls) == 1

    def test_validation_errors_are_still_raised_immediately(self, sensor):
        with pytest.raises(ValueError, match="needs 8 values"):
            sensor.set_cal_min([1, 2, 3])
        assert sensor.ur.calls == []


class TestPlainDriverStaysPlain:
    """Outside run_task() nothing is awaitable and nothing changes for users."""

    @pytest.mark.parametrize(
        "call",
        [
            lambda s: s.position(),
            lambda s: s.sensors(),
            lambda s: s.get_config(),
            lambda s: s.get_configuration(),
            lambda s: s.is_calibrated(),
            lambda s: s.uid_hex(),
            lambda s: s.calibrate(duration=0),
            lambda s: s.set_calibration([0] * 8, [1] * 8),
            lambda s: s.leds(1),
        ],
    )
    def test_results_are_plain_values(self, call):
        sensor = LineSensorUR("B", settle_ms=0, remote_class=ScriptedRemote)
        assert not hasattr(call(sensor), "send")

    def test_the_config_is_read_by_the_constructor(self):
        sensor = LineSensorUR("B", remote_class=ScriptedRemote)
        assert sensor.version == "5.6"

    def test_the_bundled_driver_follows_the_same_rules(self):
        assert not hasattr(bundle.LineSensorUR._then, "send")
        for name in ("_then", "_finish_async", "_wait", "_call_bytes", "_call_bool"):
            assert hasattr(bundle.LineSensorUR, name), name


@pytest.fixture
def run_task_mode(monkeypatch, bench):
    """Make the Pybricks bundle behave as if inside ``run_task()``."""
    fakes.install_run_task(
        monkeypatch, bench, bundle, [bundle, line_sensor], always=True
    )
    return bench


class TestBundleOnTheWire:
    """The generated Pybricks bundle against the real server, in both modes."""

    @pytest.fixture
    def chain(self, bench, device):
        server = LineSensorURServer()
        bench.link("uart1", "portB")
        bench.endpoint("uart1").on_data = server.process
        device.log.clear()
        return server

    def test_blocking_outside_run_task(self, chain, device):
        hub = bundle.LineSensorUR("B", settle_ms=0)
        device.set_reading(position=12, shape="Y")
        assert hub.version == "5.6"
        assert hub.position_derivative_shape() == (12, 0, "Y")

    def test_awaitable_inside_run_task(self, chain, device, run_task_mode):
        hub = bundle.LineSensorUR("B", settle_ms=0)
        device.set_reading(position=12, derivative=3, shape="Y")

        async def main():
            assert hub.version is None
            reading = await hub.position_derivative_shape()
            config = await hub.get_config()
            return reading, config, hub.version

        reading, config, version = asyncio.run(main())
        assert reading == (12, 3, "Y")
        assert config == tuple(device.config)
        assert version == "5.6"

    def test_commands_reach_the_sensor_in_run_task_mode(self, chain, device, run_task_mode):
        hub = bundle.LineSensorUR("B", settle_ms=0)

        async def main():
            await hub.blackline(False)
            await hub.leds(3)
            await hub.set_cal_duration(9)  # needs set_conf_value in the bundle

        asyncio.run(main())
        assert device.black_line is False
        assert device.leds_mode == 3
        assert device.config[3] == 9

    def test_concurrent_tasks_do_not_interleave_transactions(
        self, chain, device, run_task_mode, bench
    ):
        """multitask(): the server answers a tick late, so every call must wait
        for the previous one instead of flushing its reply."""
        device.set_reading(values=[1, 2, 3, 4, 5, 6, 7, 8], position=-9, shape="T")
        hub = bundle.LineSensorUR("B", settle_ms=0)

        loop_ref = {}
        bench.endpoint("uart1").on_data = lambda: loop_ref["loop"].call_soon(chain.process)

        async def main():
            loop_ref["loop"] = asyncio.get_running_loop()
            return await asyncio.gather(
                hub.position(), hub.shape(), hub.sensors(), hub.position(), hub.shape()
            )

        results = asyncio.run(main())
        assert results == [-9, "T", (1, 2, 3, 4, 5, 6, 7, 8), -9, "T"]
