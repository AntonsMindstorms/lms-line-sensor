"""The whole chain, as deployed:

    hub LineSensorUR --UART--> LineSensorURServer --I2C--> sensor firmware

Run once with the standalone Pybricks bundle as the hub driver (what a SPIKE
hub actually uploads) and once with the full ``line_sensor.LineSensorUR``.
"""

from types import SimpleNamespace

import pytest

import line_sensor
import line_sensor_pybricks
import uremote
from line_sensor import LineSensorI2C
from line_sensor_ur_server import LineSensorURServer


@pytest.fixture(params=["pybricks-bundle", "full-driver"])
def stack(request, bench):
    server = LineSensorURServer()
    # The ESP32 runs its service loop; here it reacts as soon as bytes arrive.
    # This must be in place before the hub connects: its constructor already
    # asks the sensor for its configuration.
    bench.endpoint("uart1").on_data = server.process
    if request.param == "pybricks-bundle":
        hub_end = bench.link("uart1", "portB")[1]
        hub = line_sensor_pybricks.LineSensorUR("B", settle_ms=0)
        error = line_sensor_pybricks.uRemoteError
    else:
        hub_end = bench.link("uart1", "uart2")[1]
        hub = line_sensor.LineSensorUR(2, settle_ms=0)
        error = uremote.uRemoteError
    bench.sensor.log.clear()
    return SimpleNamespace(hub=hub, server=server, device=bench.sensor, error=error, wire=hub_end)


READINGS = [
    dict(values=[0, 0, 0, 255, 255, 0, 0, 0], position=0, derivative=0, shape="|"),
    dict(values=[255, 200, 10, 0, 0, 0, 0, 0], position=-100, derivative=-7, shape="<"),
    dict(values=[0, 0, 0, 0, 0, 10, 200, 255], position=127, derivative=20, shape=">"),
    dict(values=[255] * 8, position=-128, derivative=127, shape="T"),
    dict(values=[5, 6, 7, 8, 9, 10, 11, 12], position=1, derivative=-128, shape=" "),
]


class TestReadings:
    @pytest.mark.parametrize("reading", READINGS)
    def test_hub_and_direct_i2c_agree(self, stack, device, reading):
        device.set_reading(**reading)
        direct = LineSensorI2C()
        hub = stack.hub
        assert hub.sensors() == direct.sensors() == tuple(reading["values"])
        assert hub.position() == direct.position() == reading["position"]
        assert hub.derivative() == direct.derivative() == reading["derivative"]
        assert hub.shape() == direct.shape() == reading["shape"]
        assert hub.position_derivative_shape() == direct.position_derivative_shape()
        assert hub.data() == direct.data()
        assert hub.data(hub.SHAPE, hub.POSITION) == direct.data(direct.SHAPE, direct.POSITION)

    def test_a_read_costs_one_i2c_transaction_and_no_commands(self, stack, device):
        stack.hub.position_derivative_shape()
        assert device.log == []

    def test_readings_follow_the_sensor(self, stack, device):
        device.set_reading(position=10)
        assert stack.hub.position() == 10
        device.set_reading(position=-10)
        assert stack.hub.position() == -10


class TestPolarity:
    def test_white_line_round_trip(self, stack, device):
        device.set_reading(values=[0, 10, 20, 30, 40, 50, 60, 70])
        hub = stack.hub
        assert hub.blackline() is True
        assert hub.blackline(False) is False
        assert device.black_line is False
        assert hub.blackline() is False
        assert hub.sensors() == (255, 245, 235, 225, 215, 205, 195, 185)
        assert hub.blackline(True) is True
        assert hub.sensors() == (0, 10, 20, 30, 40, 50, 60, 70)


class TestConfiguration:
    def test_the_hub_learns_version_and_calibration_time_on_connect(self, stack):
        assert stack.hub.version == "5.6"
        assert stack.hub.cal_duration == 5

    def test_named_view_matches_the_sensor_config(self, stack, device):
        config = stack.hub.get_configuration()
        assert list(config.values()) == device.config
        assert config["crc"] == device._crc()

    def test_config_setters_reach_the_firmware(self, stack, device):
        """Regression: the Pybricks bundle used to lack set_conf_value."""
        hub = stack.hub
        hub.set_cal_duration(9)
        hub.set_load_cal_startup(False)
        hub.set_shape_threshold_black(77)
        hub.set_ir_emitter_startup(False)
        assert device.config[2:6] == [0, 9, 77, 0]
        assert device.config[6] == device._crc()

    def test_config_survives_a_save_and_load(self, stack, device):
        stack.hub.save_config()
        stack.hub.load_config()
        assert [c for c, _ in device.log] == [fakes_cmd("SAVE_CONFIG"), fakes_cmd("LOAD_CONFIG")]


class TestCalibration:
    def test_calibrate_starts_the_firmware_timer_and_waits(self, stack, device, bench):
        before = bench.clock.now
        stack.hub.calibrate(duration=2)
        assert device.calibrating and device.calibrate_save
        assert bench.clock.now - before >= 3000
        assert device.leds_mode == 0  # LEDs are switched off while calibrating

    def test_calibrate_defaults_to_the_duration_in_the_sensor_config(self, stack, device, bench):
        before = bench.clock.now
        stack.hub.calibrate()
        assert bench.clock.now - before >= 6000  # 5 s + 1 s slack

    def test_is_calibrated_reflects_the_firmware(self, stack, device):
        device.calibrated = False
        assert stack.hub.is_calibrated() is False
        stack.hub.start_calibration(save=False)
        device.finish_calibration()
        assert stack.hub.is_calibrated() is True

    def test_limits_round_trip(self, stack, device):
        hub = stack.hub
        hub.set_calibration([1, 2, 3, 4, 5, 6, 7, 8], [250] * 8)
        assert device.cal_min == [1, 2, 3, 4, 5, 6, 7, 8]
        assert hub.get_cal_min() == (1, 2, 3, 4, 5, 6, 7, 8)
        assert hub.get_cal_max() == (250,) * 8

    def test_save_and_load(self, stack, device):
        stack.hub.set_cal_min([9] * 8)
        stack.hub.save_calibration()
        assert device.stored_cal[0] == [9] * 8
        device.cal_min = [0] * 8
        stack.hub.load_calibration()
        assert device.cal_min == [9] * 8


class TestOutputsAndIdentity:
    def test_emitter(self, stack, device):
        stack.hub.ir_power(True)
        assert device.emitter is True
        stack.hub.ir_power(False)
        assert device.emitter is False

    def test_leds_and_neopixels(self, stack, device):
        stack.hub.leds(3)
        assert device.leds_mode == 3
        stack.hub.neopixel(2, 10, 20, 30)
        assert device.neopixels == {2: (10, 20, 30)}

    @pytest.mark.parametrize("mode", ["mode_raw", "mode_calibrated"])
    def test_modes(self, stack, device, mode):
        getattr(stack.hub, mode)()
        expected = 0 if mode == "mode_raw" else 1
        assert device.mode == expected

    def test_uid(self, stack, device):
        assert stack.hub.get_uid() == tuple(device.UID)


class TestFailures:
    def test_remote_validation_errors_reach_the_hub(self, stack):
        with pytest.raises(stack.error, match="not available over I2C"):
            stack.hub.mode()
        with pytest.raises(stack.error, match="LED mode must be in range 0..3"):
            stack.hub.leds(9)

    def test_unknown_commands(self, stack):
        with pytest.raises(stack.error, match="function not found remotely"):
            stack.hub.ur.call("does_not_exist")

    def test_i2c_failures_surface_as_errors_and_recover(self, stack, device):
        device.read_failures = 99
        with pytest.raises(stack.error):
            stack.hub.position()
        device.read_failures = 0
        device.set_reading(position=4)
        assert stack.hub.position() == 4

    def test_a_silent_server_times_out(self, stack, bench):
        bench.endpoint("uart1").on_data = None
        with pytest.raises(stack.error, match="No data"):
            stack.hub.position()


def fakes_cmd(name):
    import fakes

    return getattr(fakes, "CMD_" + name)
