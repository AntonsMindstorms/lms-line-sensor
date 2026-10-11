"""LineSensorI2C against the simulated sensor firmware."""

import sys
from unittest.mock import MagicMock

import pytest

import fakes
from fakes import (
    CMD_BLACKLINE,
    CMD_CALIBRATE,
    CMD_DEBUG,
    CMD_GET_CAL_MAX,
    CMD_GET_CAL_MIN,
    CMD_GET_CONF_VALUE,
    CMD_GET_CONFIG,
    CMD_GET_UID,
    CMD_GET_VERSION,
    CMD_IS_CALIBRATED,
    CMD_LEDS,
    CMD_LOAD_CAL,
    CMD_LOAD_CONFIG,
    CMD_NEOPIXEL,
    CMD_SAVE_CAL,
    CMD_SAVE_CONFIG,
    CMD_SET_CAL_MAX,
    CMD_SET_CAL_MIN,
    CMD_SET_CONF_VALUE,
    CMD_SET_EMITTER,
    CMD_SET_MODE_CAL,
    CMD_SET_MODE_RAW,
    CMD_UART_TEST,
)
from line_sensor import BaseLineSensor, LineSensorI2C


@pytest.fixture
def sensor(device):
    """A driver on the simulated bus with a quiet command log."""
    driver = LineSensorI2C()
    driver.sleep = MagicMock()
    device.log.clear()
    return driver


class TestConstants:
    def test_command_numbers_match_the_firmware_table(self):
        expected = {
            "CMD_GET_VERSION": fakes.CMD_GET_VERSION,
            "CMD_DEBUG": fakes.CMD_DEBUG,
            "CMD_CALIBRATE": fakes.CMD_CALIBRATE,
            "CMD_IS_CALIBRATED": fakes.CMD_IS_CALIBRATED,
            "CMD_LOAD_CAL": fakes.CMD_LOAD_CAL,
            "CMD_SAVE_CAL": fakes.CMD_SAVE_CAL,
            "CMD_GET_CAL_MIN": fakes.CMD_GET_CAL_MIN,
            "CMD_GET_CAL_MAX": fakes.CMD_GET_CAL_MAX,
            "CMD_SET_CAL_MIN": fakes.CMD_SET_CAL_MIN,
            "CMD_SET_CAL_MAX": fakes.CMD_SET_CAL_MAX,
            "CMD_NEOPIXEL": fakes.CMD_NEOPIXEL,
            "CMD_LEDS": fakes.CMD_LEDS,
            "CMD_SET_EMITTER": fakes.CMD_SET_EMITTER,
            "CMD_GET_CONF_VALUE": fakes.CMD_GET_CONF_VALUE,
            "CMD_SET_CONF_VALUE": fakes.CMD_SET_CONF_VALUE,
            "CMD_GET_CONFIG": fakes.CMD_GET_CONFIG,
            "CMD_LOAD_CONFIG": fakes.CMD_LOAD_CONFIG,
            "CMD_SAVE_CONFIG": fakes.CMD_SAVE_CONFIG,
            "CMD_UART_TEST": fakes.CMD_UART_TEST,
            "CMD_BLACKLINE": fakes.CMD_BLACKLINE,
            "CMD_GET_UID": fakes.CMD_GET_UID,
        }
        for name, number in expected.items():
            assert getattr(LineSensorI2C, name) == number, name

    def test_mode_values_double_as_the_mode_commands(self):
        assert BaseLineSensor.MODE_RAW == CMD_SET_MODE_RAW
        assert BaseLineSensor.MODE_CALIBRATED == CMD_SET_MODE_CAL


class TestInit:
    def test_loads_calibration_then_selects_calibrated_mode(self, device):
        LineSensorI2C()
        assert device.commands() == [(CMD_LOAD_CAL, b""), (CMD_SET_MODE_CAL, b"")]

    def test_raw_mode_is_selected_after_calibrated_mode(self, device):
        LineSensorI2C(mode=BaseLineSensor.MODE_RAW)
        assert [c for c, _ in device.commands()] == [
            CMD_LOAD_CAL,
            CMD_SET_MODE_CAL,
            CMD_SET_MODE_RAW,
        ]
        assert device.mode == CMD_SET_MODE_RAW

    def test_bus_settings_are_passed_to_machine_i2c(self, bench):
        LineSensorI2C(i2c_id=0, scl_pin=7, sda_pin=8, freq=400000)
        bus = bench.i2c_buses[-1]
        assert (bus.i2c_id, bus.scl, bus.sda, bus.freq) == (0, 7, 8, 400000)

    def test_defaults_match_the_lms_esp32_qwiic_port(self, bench):
        driver = LineSensorI2C()
        bus = bench.i2c_buses[-1]
        assert (bus.i2c_id, bus.scl, bus.sda, bus.freq) == (1, 4, 5, 100000)
        assert driver.device_addr == 0x33

    def test_polarity_defaults_to_the_firmware_default(self, device):
        assert LineSensorI2C().black_line is device.black_line is True

    def test_without_machine_module_the_error_points_to_pybricks(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "machine", None)
        with pytest.raises(RuntimeError, match="LineSensorUR"):
            LineSensorI2C()


class TestReading:
    def test_sensors_returns_eight_ints(self, sensor, device):
        device.set_reading(values=[1, 2, 3, 4, 5, 6, 7, 8])
        assert sensor.sensors() == (1, 2, 3, 4, 5, 6, 7, 8)

    def test_position_derivative_and_shape(self, sensor, device):
        device.set_reading(position=-40, derivative=12, shape="Y")
        assert sensor.position() == -40
        assert sensor.derivative() == 12
        assert sensor.shape() == "Y"
        assert sensor.position_derivative_shape() == (-40, 12, "Y")

    def test_data_without_indices_is_the_whole_packet(self, sensor, device):
        assert sensor.data() == tuple(device.packet())
        assert len(sensor.data()) == 13

    def test_data_with_indices(self, sensor, device):
        device.set_reading(position=3, shape="|")
        assert sensor.data(sensor.POSITION, sensor.SHAPE) == (3, "|")

    def test_min_and_max_fields_are_raw(self, sensor, device):
        device.minimum, device.maximum = 11, 222
        assert sensor.data(sensor.MIN, sensor.MAX) == (11, 222)

    def test_a_read_is_one_transaction_and_sends_no_command(self, sensor, device):
        sensor.data()
        assert device.log == []

    def test_polarity_is_applied_by_firmware_not_by_the_library(self, sensor, device):
        device.set_reading(values=[0, 10, 20, 30, 40, 50, 60, 70])
        assert sensor.blackline(False) is False
        assert sensor.sensors() == (255, 245, 235, 225, 215, 205, 195, 185)
        assert sensor.blackline(True) is True
        assert sensor.sensors() == (0, 10, 20, 30, 40, 50, 60, 70)


class TestModesAndCalibration:
    def test_mode_commands(self, sensor, device):
        sensor.mode_raw()
        sensor.mode_calibrated()
        assert device.commands() == [(CMD_SET_MODE_RAW, b""), (CMD_SET_MODE_CAL, b"")]

    @pytest.mark.parametrize("save, flag", [(False, 0), (True, 1)])
    def test_start_calibration_sends_the_save_flag(self, sensor, device, save, flag):
        sensor.start_calibration(save=save)
        assert device.commands() == [(CMD_CALIBRATE, bytes([flag]))]

    def test_start_calibration_does_not_save_by_default(self, sensor, device):
        sensor.start_calibration()
        assert device.calibrate_save is False

    def test_save_calibration_is_a_single_command(self, sensor, device):
        sensor.save_calibration()
        assert device.commands() == [(CMD_SAVE_CAL, b"")]

    def test_load_calibration(self, sensor, device):
        sensor.load_calibration()
        assert device.commands() == [(CMD_LOAD_CAL, b"")]

    def test_calibrate_sets_duration_starts_with_save_and_waits(self, sensor, device):
        sensor.calibrate(duration=8)
        assert device.commands() == [
            (CMD_SET_CONF_VALUE, bytes([BaseLineSensor.CONFIG_CAL_DURATION, 8])),
            (CMD_CALIBRATE, b"\x01"),
        ]
        sensor.sleep.assert_called_once_with(9)  # duration plus one second slack
        assert device.config[BaseLineSensor.CONFIG_CAL_DURATION] == 8

    def test_calibrate_defaults_to_five_seconds(self, sensor, device):
        sensor.calibrate()
        sensor.sleep.assert_called_once_with(6)

    def test_calibration_saved_when_the_firmware_finishes(self, sensor, device):
        device.cal_min = [3] * 8
        sensor.calibrate(duration=1)
        device.finish_calibration()
        assert device.stored_cal[0] == [3] * 8
        assert sensor.is_calibrated() is True

    def test_is_calibrated_reads_one_byte(self, sensor, device):
        device.calibrated = False
        assert sensor.is_calibrated() is False
        device.calibrated = True
        assert sensor.is_calibrated() is True
        assert device.commands() == [(CMD_IS_CALIBRATED, b"")] * 2


class TestPolarity:
    @pytest.mark.parametrize("black, byte", [(True, 1), (False, 0), (1, 1), (0, 0)])
    def test_blackline_sends_command_23(self, sensor, device, black, byte):
        assert sensor.blackline(black) is bool(black)
        assert device.commands() == [(CMD_BLACKLINE, bytes([byte]))]
        assert sensor.black_line is bool(black)

    def test_blackline_requires_a_value(self, sensor):
        with pytest.raises(TypeError):
            sensor.blackline()


class TestOutputs:
    @pytest.mark.parametrize("power, byte", [(True, 1), (False, 0), (1, 1), (0, 0)])
    def test_ir_power(self, sensor, device, power, byte):
        sensor.ir_power(power)
        assert device.commands() == [(CMD_SET_EMITTER, bytes([byte]))]

    def test_set_emitter_is_an_alias(self, sensor, device):
        sensor.set_emitter(True)
        assert device.emitter is True

    @pytest.mark.parametrize("name", ["leds", "rgb_mode", "led_mode"])
    def test_led_mode_and_its_aliases(self, sensor, device, name):
        getattr(sensor, name)(BaseLineSensor.LEDS_POSITION)
        assert device.commands() == [(CMD_LEDS, b"\x03")]

    @pytest.mark.parametrize("name", ["neopixel", "set_neopixel"])
    def test_neopixel_and_its_alias(self, sensor, device, name):
        getattr(sensor, name)(4, 10, 20, 30)
        assert device.commands() == [(CMD_NEOPIXEL, bytes([4, 10, 20, 30]))]
        assert device.neopixels[4] == (10, 20, 30)

    def test_out_of_range_colour_is_rejected_before_anything_is_sent(self, sensor, device):
        with pytest.raises(ValueError):
            sensor.neopixel(0, 256, 0, 0)
        assert device.log == []


class TestCalibrationLimits:
    @pytest.mark.parametrize("name", ["get_min", "get_cal_min"])
    def test_get_min(self, sensor, device, name):
        device.cal_min = [1, 2, 3, 4, 5, 6, 7, 8]
        assert getattr(sensor, name)() == (1, 2, 3, 4, 5, 6, 7, 8)
        assert device.commands() == [(CMD_GET_CAL_MIN, b"")]

    @pytest.mark.parametrize("name", ["get_max", "get_cal_max"])
    def test_get_max(self, sensor, device, name):
        device.cal_max = [9] * 8
        assert getattr(sensor, name)() == (9,) * 8
        assert device.commands() == [(CMD_GET_CAL_MAX, b"")]

    @pytest.mark.parametrize("name", ["set_min", "set_cal_min"])
    def test_set_min(self, sensor, device, name):
        getattr(sensor, name)([1, 2, 3, 4, 5, 6, 7, 8])
        assert device.commands() == [(CMD_SET_CAL_MIN, bytes([1, 2, 3, 4, 5, 6, 7, 8]))]
        assert device.cal_min == [1, 2, 3, 4, 5, 6, 7, 8]

    @pytest.mark.parametrize("name", ["set_max", "set_cal_max"])
    def test_set_max(self, sensor, device, name):
        getattr(sensor, name)([200] * 8)
        assert device.commands() == [(CMD_SET_CAL_MAX, bytes([200] * 8))]

    def test_values_are_truncated_to_bytes(self, sensor, device):
        sensor.set_min([256, 257, -1, 1.9, 0, 0, 0, 0])
        assert device.cal_min == [0, 1, 255, 1, 0, 0, 0, 0]

    @pytest.mark.parametrize("name", ["set_min", "set_max"])
    @pytest.mark.parametrize("count", [0, 7, 9])
    def test_exactly_eight_values_are_required(self, sensor, device, name, count):
        with pytest.raises(ValueError):
            getattr(sensor, name)([0] * count)
        assert device.log == []

    def test_set_calibration_sets_both_limits(self, sensor, device):
        sensor.set_calibration([1] * 8, [2] * 8)
        assert device.cal_min == [1] * 8
        assert device.cal_max == [2] * 8


class TestConfiguration:
    def test_version(self, sensor, device):
        assert sensor.version() == (5, 6)
        assert device.commands() == [(CMD_GET_VERSION, b"")]

    def test_get_value_reads_one_config_byte(self, sensor, device):
        assert sensor.get_value(BaseLineSensor.CONFIG_CAL_DURATION) == 5
        assert device.commands() == [(CMD_GET_CONF_VALUE, b"\x03")]

    def test_set_value_writes_and_returns_the_value(self, sensor, device):
        assert sensor.set_value(BaseLineSensor.CONFIG_SHAPE_THRESHOLD_BLACK, 99) == 99
        assert device.config[BaseLineSensor.CONFIG_SHAPE_THRESHOLD_BLACK] == 99

    def test_config_field_aliases(self, sensor, device):
        sensor.set_config_field(3, 12)
        assert sensor.get_config_field(3) == 12

    def test_get_config_returns_seven_bytes(self, sensor, device):
        assert sensor.get_config() == tuple(device.config)
        assert len(sensor.get_config()) == 7

    def test_config_names_the_fields(self, sensor, device):
        assert sensor.config() == {
            "maj_version": 5,
            "min_version": 6,
            "load_cal_startup": 1,
            "cal_duration": 5,
            "shape_threshold_black": 128,
            "ir_power": 1,
            "crc": device.config[6],
        }

    def test_base_class_configuration_view_agrees(self, sensor):
        assert sensor.get_configuration() == sensor.config()

    @pytest.mark.parametrize(
        "method, argument, index, value",
        [
            ("set_load_cal_startup", False, 2, 0),
            ("set_cal_duration", 20, 3, 20),
            ("set_shape_threshold_black", 100, 4, 100),
            ("set_threshold_shape", 101, 4, 101),
            ("set_ir_emitter_startup", False, 5, 0),
        ],
    )
    def test_named_setters_write_the_right_index(self, sensor, device, method, argument, index, value):
        getattr(sensor, method)(argument)
        assert device.config[index] == value

    def test_changing_config_keeps_the_crc_valid(self, sensor, device):
        sensor.set_cal_duration(33)
        assert sensor.get_config()[6] == device._crc()

    def test_save_and_load_config(self, sensor, device):
        sensor.save_config()
        sensor.load_config()
        assert device.commands() == [(CMD_SAVE_CONFIG, b""), (CMD_LOAD_CONFIG, b"")]

    def test_load_config_applies_the_startup_emitter_state(self, sensor, device):
        sensor.load_config()
        assert device.emitter is True

    @pytest.mark.parametrize("level", [0, 3])
    def test_debug_sends_the_legacy_command_and_echoes_the_level(self, sensor, device, level):
        assert sensor.debug(level) == level
        assert device.commands() == [(CMD_DEBUG, bytes([level]))]

    def test_uid(self, sensor, device):
        assert sensor.get_uid() == tuple(device.UID)
        assert sensor.uid_hex() == device.UID.hex()
        assert len(sensor.uid_hex()) == 24

    @pytest.mark.parametrize("result", [0, 1])
    def test_uart_test_returns_the_firmware_result(self, sensor, device, result):
        device.uart_test_result = result
        assert sensor.uart_test() == result
        assert device.commands() == [(CMD_UART_TEST, b"")]
        # The firmware needs 50 ms to run the loopback before the read.
        assert device.log and fakes.Bench.current.clock.now >= 50


class TestWriteCommand:
    def test_integer_command(self, sensor, device):
        sensor.write_command(CMD_SET_MODE_RAW)
        assert device.commands() == [(0, b"")]

    @pytest.mark.parametrize("payload", [(4, 1), [4, 1], bytes([4, 1]), bytearray([4, 1])])
    def test_sequence_commands(self, sensor, device, payload):
        sensor.write_command(payload)
        assert device.commands() == [(4, b"\x01")]


class TestRetries:
    """Transient I2C errors are retried up to four times."""

    def test_a_read_survives_three_failures(self, sensor, device):
        device.read_failures = 3
        assert len(sensor.data()) == 13
        assert device.read_failures == 0

    def test_a_read_fails_after_four_attempts(self, sensor, device):
        device.read_failures = 10
        with pytest.raises(OSError):
            sensor.data()
        assert device.read_failures == 6  # exactly four attempts were made

    def test_a_write_survives_three_failures(self, sensor, device):
        device.write_failures = 3
        sensor.ir_power(True)
        assert device.emitter is True

    def test_a_write_fails_after_four_attempts(self, sensor, device):
        device.write_failures = 10
        with pytest.raises(OSError):
            sensor.ir_power(True)
        assert device.write_failures == 6
        assert device.emitter is False

    def test_the_last_error_is_the_one_raised(self, sensor, device):
        errors = [OSError(1, "first"), OSError(2, "second"), OSError(3, "third"), OSError(4, "last")]
        calls = iter(errors)

        def failing():
            raise next(calls)

        with pytest.raises(OSError) as raised:
            sensor._retry(failing)
        assert raised.value.args[0] == 4

    def test_a_wrong_address_is_an_error(self, device):
        driver = LineSensorI2C(device_addr=0x33)
        driver.device_addr = 0x34
        with pytest.raises(OSError):
            driver.data()
