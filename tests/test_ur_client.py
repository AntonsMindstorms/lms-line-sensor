"""LineSensorUR: which uRemote commands each method sends and how it decodes replies."""

import pytest

import line_sensor
from line_sensor import BaseLineSensor, LineSensorUR

from fakes import CONFIG, PACKET, ScriptedRemote as FakeRemote


@pytest.fixture
def sensor():
    driver = LineSensorUR("B", settle_ms=0, remote_class=FakeRemote)
    driver.ur.calls.clear()
    return driver


class TestConnect:
    def test_the_port_is_passed_to_the_remote(self):
        driver = LineSensorUR("B", remote_class=FakeRemote)
        assert driver.ur.args == ("B",)

    def test_no_port_uses_the_remote_default(self):
        driver = LineSensorUR(remote_class=FakeRemote)
        assert driver.ur.args == ()

    def test_version_and_calibration_time_come_from_the_config(self):
        driver = LineSensorUR("B", remote_class=FakeRemote)
        assert driver.version == "5.6"
        assert driver.cal_duration == 4
        assert driver.ur.commands == ["get_config"]

    def test_it_uses_the_uremote_error_class_of_the_library(self):
        import uremote

        assert LineSensorUR("B", remote_class=FakeRemote).ur_error is uremote.uRemoteError

    def test_a_failing_remote_fails_the_constructor(self):
        class Dead(FakeRemote):
            def call(self, command, *arguments):
                raise RuntimeError("no data")

        with pytest.raises(RuntimeError):
            LineSensorUR("B", remote_class=Dead)


class TestReading:
    def test_everything_is_read_with_one_all_command(self, sensor):
        assert sensor.position_derivative_shape() == (72, -28, "T")
        assert sensor.ur.calls == [("all", ())]

    def test_sensors(self, sensor):
        assert sensor.sensors() == (10, 20, 30, 40, 50, 60, 70, 80)

    def test_data_without_indices_is_the_whole_packet(self, sensor):
        assert sensor.data() == tuple(PACKET)

    def test_data_with_indices(self, sensor):
        assert sensor.data(sensor.MIN, sensor.MAX) == (5, 90)

    def test_replies_may_be_lists_or_bytes(self, sensor):
        sensor.ur.replies["all"] = list(PACKET)
        assert sensor.shape() == "T"

    def test_settle_time_is_waited_before_every_read(self):
        driver = LineSensorUR("B", settle_ms=7, remote_class=FakeRemote)
        before = line_sensor_clock()
        driver.position()
        driver.position()
        assert line_sensor_clock() - before == 14

    def test_zero_settle_time_does_not_wait(self, sensor):
        before = line_sensor_clock()
        sensor.position()
        assert line_sensor_clock() == before

    def test_read_all_and_read_sensors(self, sensor):
        assert sensor.read_all() == tuple(PACKET)
        assert sensor.read_sensors() == tuple(PACKET[:8])
        assert sensor.ur.commands == ["all", "data"]

    def test_raw_helper_commands(self, sensor):
        sensor.ur.replies.update(pos=200, shape=84, pdr=bytes([1, 2, 3]))
        assert sensor.position_byte() == 200
        assert sensor.shape_byte() == 84
        assert sensor.pds_raw() == (200, 100, 84)
        assert sensor.pdr_raw() == (1, 2, 3)
        assert sensor.ur.commands == ["pos", "shape", "pds", "pdr"]


class TestModes:
    def test_mode_get_and_set(self, sensor):
        sensor.mode()
        sensor.mode(1)
        assert sensor.ur.calls == [("mode", ()), ("mode", (1,))]

    def test_mode_zero_is_a_set_not_a_get(self, sensor):
        sensor.mode(0)
        assert sensor.ur.calls == [("mode", (0,))]

    def test_named_mode_commands(self, sensor):
        sensor.mode_raw()
        sensor.mode_calibrated()
        sensor.current_mode()
        assert sensor.ur.commands == ["set_mode_raw", "set_mode_cal", "cur_mode"]


class TestPolarity:
    def test_get(self, sensor):
        assert sensor.blackline() is True
        assert sensor.ur.calls == [("blackline", ())]

    @pytest.mark.parametrize("black", [True, False])
    def test_set_sends_a_real_boolean(self, sensor, black):
        sensor.ur.replies["blackline"] = int(black)
        assert sensor.blackline(black) is black
        (command, arguments), = sensor.ur.calls
        assert command == "blackline"
        assert arguments == (black,)
        assert type(arguments[0]) is bool

    def test_false_is_not_mistaken_for_a_get(self, sensor):
        sensor.ur.replies["blackline"] = 0
        sensor.blackline(False)
        assert sensor.ur.calls == [("blackline", (False,))]

    def test_empty_reply_means_false(self, sensor):
        sensor.ur.replies["blackline"] = None
        assert sensor.blackline() is False


class TestCalibration:
    def test_start_calibration_flag(self, sensor):
        sensor.start_calibration()
        sensor.start_calibration(save=True)
        assert sensor.ur.calls == [("calibrate", (0,)), ("calibrate", (1,))]

    def test_calibrate_flow_uses_the_stored_duration(self, sensor):
        before = line_sensor_clock()
        assert sensor.calibrate() is True
        assert sensor.ur.calls == [
            ("leds", (BaseLineSensor.LEDS_OFF,)),
            ("calibrate", (1,)),
            ("is_calibrated", ()),
        ]
        assert line_sensor_clock() - before == 5000  # (4 s + 1 s slack)

    def test_calibrate_with_explicit_duration_and_no_save(self, sensor):
        before = line_sensor_clock()
        sensor.calibrate(duration=2, save=False)
        assert ("calibrate", (0,)) in sensor.ur.calls
        assert line_sensor_clock() - before == 3000

    def test_calibrate_returns_the_calibrated_flag(self, sensor):
        sensor.ur.replies["is_calibrated"] = 0
        assert sensor.calibrate(duration=0) is False

    def test_is_calibrated_coerces_to_bool(self, sensor):
        sensor.ur.replies["is_calibrated"] = None
        assert sensor.is_calibrated() is False
        sensor.ur.replies["is_calibrated"] = 1
        assert sensor.is_calibrated() is True

    def test_save_and_load(self, sensor):
        sensor.save_calibration()
        sensor.load_calibration()
        assert sensor.ur.commands == ["save_cal", "load_cal"]

    def test_limits(self, sensor):
        sensor.ur.replies.update(get_cal_min=bytes(range(8)), get_cal_max=bytes([9] * 8))
        assert sensor.get_cal_min() == tuple(range(8))
        assert sensor.get_cal_max() == (9,) * 8

    @pytest.mark.parametrize("name", ["set_cal_min", "set_cal_max"])
    def test_setting_limits_spreads_the_values(self, sensor, name):
        getattr(sensor, name)([1, 2, 3, 4, 5, 6, 7, 8])
        assert sensor.ur.calls == [(name, (1, 2, 3, 4, 5, 6, 7, 8))]

    @pytest.mark.parametrize("name", ["set_cal_min", "set_cal_max"])
    @pytest.mark.parametrize("count", [0, 7, 9])
    def test_exactly_eight_limits_are_required(self, sensor, name, count):
        with pytest.raises(ValueError, match=name + " needs 8 values"):
            getattr(sensor, name)([0] * count)
        assert sensor.ur.calls == []

    def test_set_calibration_sets_both(self, sensor):
        sensor.set_calibration([1] * 8, [2] * 8)
        assert sensor.ur.commands == ["set_cal_min", "set_cal_max"]


class TestConfiguration:
    def test_get_config(self, sensor):
        assert sensor.get_config() == tuple(CONFIG)

    def test_named_view_of_the_config(self, sensor):
        config = sensor.get_configuration()
        assert config["maj_version"] == 5
        assert config["cal_duration"] == 4

    def test_conf_value_commands(self, sensor):
        sensor.get_conf_value(3)
        sensor.set_conf_value(3, 9)
        assert sensor.ur.calls == [("get_conf_value", (3,)), ("set_conf_value", (3, 9))]

    def test_named_setters_go_through_set_conf_value(self, sensor):
        sensor.set_cal_duration(9)
        sensor.set_ir_emitter_startup(False)
        assert sensor.ur.calls == [("set_conf_value", (3, 9)), ("set_conf_value", (5, 0))]

    def test_load_and_save_config(self, sensor):
        sensor.load_config()
        sensor.save_config()
        assert sensor.ur.commands == ["load_config", "save_config"]


class TestOutputs:
    def test_leds(self, sensor):
        sensor.leds(3)
        assert sensor.ur.calls == [("leds", (3,))]

    def test_neopixel(self, sensor):
        sensor.neopixel(2, 10, 20, 30)
        assert sensor.ur.calls == [("neopixel", (2, 10, 20, 30))]

    @pytest.mark.parametrize("power, flag", [(True, 1), (False, 0), (5, 1), (0, 0)])
    def test_ir_power_sends_zero_or_one(self, sensor, power, flag):
        sensor.ir_power(power)
        assert sensor.ur.calls == [("set_emitter", (flag,))]

    def test_set_emitter_is_an_alias(self, sensor):
        sensor.set_emitter(True)
        assert sensor.ur.calls == [("set_emitter", (1,))]


class TestIdentity:
    def test_uid(self, sensor):
        assert sensor.get_uid() == tuple(range(12))
        assert sensor.uid_hex() == "000102030405060708090a0b"

    def test_firmware_version_is_formatted_as_text(self, sensor):
        assert sensor.get_version() == "5.6"

    def test_ping_and_debug_pass_through(self, sensor):
        sensor.ur.replies.update(ping=1234, debug=(1, 2, 3, 4, 5, 6))
        assert sensor.ping() == 1234
        assert sensor.debug() == (1, 2, 3, 4, 5, 6)


class TestErrors:
    def test_remote_errors_propagate_unchanged(self, sensor):
        failure = sensor.ur_error("mode get is not available over I2C")
        sensor.ur.replies["mode"] = failure
        with pytest.raises(sensor.ur_error, match="not available"):
            sensor.mode()


def line_sensor_clock():
    """The fake clock that ``line_sensor.wait`` advances."""
    import fakes

    return fakes.Bench.current.clock.now
