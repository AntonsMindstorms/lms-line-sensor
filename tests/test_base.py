"""BaseLineSensor: constants and the high-level API built on ``data()``."""

import pytest

import line_sensor
from line_sensor import BaseLineSensor, LineSensorI2C, LineSensorUR

PACKET = [10, 20, 30, 40, 50, 60, 70, 80, 200, 5, 90, 100, ord("T")]


class RecordingSensor(BaseLineSensor):
    """The smallest concrete sensor: records what the base class asks for."""

    def __init__(self, packet=PACKET, config=(5, 6, 1, 5, 128, 1, 0)):
        self.packet = list(packet)
        self.config = config
        self.calls = []

    def data(self, *indices):
        self.calls.append(("data", indices))
        return self._select_indices(self.packet, indices)

    def mode(self, mode=None):
        self.calls.append(("mode", mode))
        return mode

    def get_config(self):
        return self.config

    def get_uid(self):
        return bytes(range(12))

    def set_conf_value(self, index, value):
        self.calls.append(("set_conf_value", index, value))
        return value

    def set_cal_min(self, values):
        self.calls.append(("set_cal_min", tuple(values)))

    def set_cal_max(self, values):
        self.calls.append(("set_cal_max", tuple(values)))
        return "max-result"


class TestConstants:
    """The constants are the firmware's contract (firmware/README.md)."""

    def test_packet_layout(self):
        assert BaseLineSensor.RAW_BYTES == 13
        assert BaseLineSensor.SENSOR_COUNT == 8
        assert (
            BaseLineSensor.POSITION,
            BaseLineSensor.MIN,
            BaseLineSensor.MAX,
            BaseLineSensor.DERIVATIVE,
            BaseLineSensor.SHAPE,
        ) == (8, 9, 10, 11, 12)
        assert BaseLineSensor.VALUES == -1

    def test_modes(self):
        assert BaseLineSensor.MODE_RAW == 0
        assert BaseLineSensor.MODE_CALIBRATED == 1
        assert BaseLineSensor.MODE_CALIBRATING == 3

    def test_obsolete_saving_mode_aliases_digital(self):
        assert BaseLineSensor.MODE_SAVING == BaseLineSensor.MODE_DIGITAL == 2

    def test_led_modes(self):
        assert BaseLineSensor.LEDS_OFF == 0
        assert BaseLineSensor.LEDS_VALUES == 1
        assert BaseLineSensor.LEDS_VALUES_INVERTED == 2
        assert BaseLineSensor.LEDS_POSITION == 3

    def test_shape_characters(self):
        assert BaseLineSensor.SHAPE_NONE == " "
        assert BaseLineSensor.SHAPE_STRAIGHT == "|"
        assert BaseLineSensor.SHAPE_T == "T"
        assert BaseLineSensor.SHAPE_L_LEFT == "<"
        assert BaseLineSensor.SHAPE_L_RIGHT == ">"
        assert BaseLineSensor.SHAPE_Y == "Y"

    def test_config_indices_follow_the_eeprom_layout(self):
        assert BaseLineSensor.CONFIG_MAJ_VERSION == 0
        assert BaseLineSensor.CONFIG_MIN_VERSION == 1
        assert BaseLineSensor.CONFIG_LOAD_CAL_STARTUP == 2
        assert BaseLineSensor.CONFIG_CAL_DURATION == 3
        assert BaseLineSensor.CONFIG_SHAPE_THRESHOLD_BLACK == 4
        assert BaseLineSensor.CONFIG_IR_POWER == 5
        assert BaseLineSensor.CONFIG_CRC == 6

    @pytest.mark.parametrize("backend", [LineSensorI2C, LineSensorUR])
    def test_backends_do_not_redefine_constants(self, backend):
        for name, value in vars(BaseLineSensor).items():
            if name.isupper():
                assert getattr(backend, name) == value, name
                assert name not in vars(backend), name + " is shadowed"


class TestSelectIndices:
    sensor = RecordingSensor()

    def test_no_indices_returns_the_raw_packet(self):
        assert self.sensor._select_indices(PACKET, ()) == tuple(PACKET)

    def test_values_index_returns_the_eight_channels(self):
        assert self.sensor._select_indices(PACKET, (BaseLineSensor.VALUES,)) == (
            10, 20, 30, 40, 50, 60, 70, 80,
        )

    @pytest.mark.parametrize(
        "raw, signed", [(0, -128), (64, -64), (128, 0), (200, 72), (255, 127)]
    )
    def test_position_and_derivative_are_centered_on_128(self, raw, signed):
        packet = [0] * 8 + [raw, 0, 0, raw, 32]
        assert self.sensor._select_indices(packet, (BaseLineSensor.POSITION,)) == signed
        assert self.sensor._select_indices(packet, (BaseLineSensor.DERIVATIVE,)) == signed

    @pytest.mark.parametrize("character", list(" |T<>Y"))
    def test_shape_is_a_character(self, character):
        packet = [0] * 12 + [ord(character)]
        assert self.sensor._select_indices(packet, (BaseLineSensor.SHAPE,)) == character

    def test_min_and_max_stay_raw_bytes(self):
        assert self.sensor._select_indices(PACKET, (BaseLineSensor.MIN,)) == 5
        assert self.sensor._select_indices(PACKET, (BaseLineSensor.MAX,)) == 90

    def test_several_indices_come_back_in_request_order(self):
        result = self.sensor._select_indices(
            PACKET, (BaseLineSensor.SHAPE, BaseLineSensor.POSITION)
        )
        assert result == ("T", 72)

    def test_values_are_flattened_into_a_multi_index_result(self):
        result = self.sensor._select_indices(
            PACKET, (BaseLineSensor.POSITION, BaseLineSensor.VALUES, BaseLineSensor.SHAPE)
        )
        assert result == (72, 10, 20, 30, 40, 50, 60, 70, 80, "T")

    def test_invert_values_only_touches_the_channels(self):
        result = self.sensor._select_indices(
            PACKET,
            (BaseLineSensor.VALUES, BaseLineSensor.POSITION),
            invert_values=True,
        )
        assert result == (245, 235, 225, 215, 205, 195, 185, 175, 72)

    def test_accepts_bytes_and_returns_tuples(self):
        assert self.sensor._select_indices(bytes(PACKET), ()) == tuple(PACKET)
        result = self.sensor._select_indices(bytes(PACKET), (BaseLineSensor.VALUES,))
        assert isinstance(result, tuple)


class TestBytesTuple:
    @pytest.mark.parametrize(
        "value, expected",
        [
            (None, ()),
            ((1, 2), (1, 2)),
            ([1, 2], (1, 2)),
            (b"\x01\x02", (1, 2)),
            (bytearray(b"\x01\x02"), (1, 2)),
            (7, (7,)),
        ],
    )
    def test_normalises_firmware_replies(self, value, expected):
        assert BaseLineSensor._bytes_tuple(value) == expected


class TestHighLevelReads:
    """Each helper asks ``data()`` for exactly the fields it names."""

    def setup_method(self):
        self.sensor = RecordingSensor()

    def test_sensors(self):
        assert self.sensor.sensors() == (10, 20, 30, 40, 50, 60, 70, 80)
        assert self.sensor.calls == [("data", (BaseLineSensor.VALUES,))]

    def test_position(self):
        assert self.sensor.position() == 72
        assert self.sensor.calls == [("data", (BaseLineSensor.POSITION,))]

    def test_derivative_and_its_alias(self):
        assert self.sensor.derivative() == -28
        assert self.sensor.position_derivative() == -28

    def test_shape(self):
        assert self.sensor.shape() == "T"

    def test_position_derivative_shape_is_one_read(self):
        assert self.sensor.position_derivative_shape() == (72, -28, "T")
        assert self.sensor.calls == [
            ("data", (BaseLineSensor.POSITION, BaseLineSensor.DERIVATIVE, BaseLineSensor.SHAPE))
        ]


class TestModesAndCalibration:
    def setup_method(self):
        self.sensor = RecordingSensor()

    def test_mode_helpers_delegate_to_mode(self):
        self.sensor.mode_raw()
        self.sensor.mode_calibrated()
        assert self.sensor.calls == [
            ("mode", BaseLineSensor.MODE_RAW),
            ("mode", BaseLineSensor.MODE_CALIBRATED),
        ]

    def test_set_calibration_sets_min_then_max_and_returns_the_max_result(self):
        minimum, maximum = [1] * 8, [2] * 8
        assert self.sensor.set_calibration(minimum, maximum) == "max-result"
        assert self.sensor.calls == [
            ("set_cal_min", (1,) * 8),
            ("set_cal_max", (2,) * 8),
        ]

    @pytest.mark.parametrize("values", [[], [1] * 7, [1] * 9])
    def test_require_sensor_count_rejects_wrong_lengths(self, values):
        with pytest.raises(ValueError, match="set_min needs 8 values"):
            self.sensor._require_sensor_count(values, "set_min")

    def test_require_sensor_count_accepts_eight(self):
        self.sensor._require_sensor_count([0] * 8, "set_min")


class TestConfiguration:
    def test_named_dictionary(self):
        assert RecordingSensor().get_configuration() == {
            "maj_version": 5,
            "min_version": 6,
            "load_cal_startup": 1,
            "cal_duration": 5,
            "shape_threshold_black": 128,
            "ir_power": 1,
            "crc": 0,
        }

    def test_raw_form(self):
        assert RecordingSensor().get_configuration(as_text=False) == (5, 6, 1, 5, 128, 1, 0)

    def test_short_config_is_padded_with_none(self):
        result = RecordingSensor(config=(5, 6)).get_configuration()
        assert result["min_version"] == 6
        assert result["crc"] is None

    @pytest.mark.parametrize(
        "method, argument, index, value",
        [
            ("set_load_cal_startup", True, BaseLineSensor.CONFIG_LOAD_CAL_STARTUP, 1),
            ("set_load_cal_startup", False, BaseLineSensor.CONFIG_LOAD_CAL_STARTUP, 0),
            ("set_cal_duration", 9, BaseLineSensor.CONFIG_CAL_DURATION, 9),
            ("set_shape_threshold_black", 77, BaseLineSensor.CONFIG_SHAPE_THRESHOLD_BLACK, 77),
            ("set_ir_emitter_startup", True, BaseLineSensor.CONFIG_IR_POWER, 1),
            ("set_ir_emitter_startup", False, BaseLineSensor.CONFIG_IR_POWER, 0),
        ],
    )
    def test_setters_write_the_matching_config_byte(self, method, argument, index, value):
        sensor = RecordingSensor()
        assert getattr(sensor, method)(argument) == value
        assert sensor.calls == [("set_conf_value", index, value)]

    def test_uid_hex(self):
        assert RecordingSensor().uid_hex() == "000102030405060708090a0b"


def test_version_string_is_defined():
    assert isinstance(line_sensor.__version__, str)
    assert line_sensor.__version__.count(".") == 2
