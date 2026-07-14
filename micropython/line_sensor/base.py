"""Shared API and constants for LMS line sensor drivers."""

__version__ = "0.3.0"


class BaseLineSensor:
    """Base class for LMS Line Sensor implementations."""

    RAW_BYTES = 13
    SENSOR_COUNT = 8

    MODE_RAW = 0
    MODE_CALIBRATED = 1
    MODE_SAVING = 2
    MODE_CALIBRATING = 3

    POSITION = 8
    MIN = 9
    MAX = 10
    DERIVATIVE = 11
    SHAPE = 12
    VALUES = -1

    LEDS_OFF = 0
    LEDS_VALUES = 1
    LEDS_VALUES_INVERTED = 2
    LEDS_POSITION = 3
    LEDS_MAX = 4

    SHAPE_NONE = " "
    SHAPE_STRAIGHT = "|"
    SHAPE_T = "T"
    SHAPE_L_LEFT = "<"
    SHAPE_L_RIGHT = ">"
    SHAPE_Y = "Y"

    CONFIG_MAJ_VERSION = 0
    CONFIG_MIN_VERSION = 1
    CONFIG_LOAD_CAL_STARTUP = 2
    CONFIG_CAL_DURATION = 3
    CONFIG_SHAPE_THRESHOLD_BLACK = 4
    CONFIG_IR_POWER = 5
    CONFIG_CRC = 6

    def _decode_index(self, raw, idx, invert_values=False):
        if idx == self.VALUES:
            values = tuple(raw[: self.SENSOR_COUNT])
            if invert_values:
                return tuple(255 - value for value in values)
            return values
        if idx == self.POSITION or idx == self.DERIVATIVE:
            return raw[idx] - 128
        if idx == self.SHAPE:
            return chr(raw[idx])
        return raw[idx]

    def _select_indices(self, raw, indices, invert_values=False):
        raw = tuple(raw)
        if not indices:
            return raw

        if len(indices) == 1:
            return self._decode_index(raw, indices[0], invert_values=invert_values)

        out = []
        for idx in indices:
            decoded = self._decode_index(raw, idx, invert_values=invert_values)
            if idx == self.VALUES:
                out.extend(decoded)
            else:
                out.append(decoded)
        return tuple(out)

    @staticmethod
    def _bytes_tuple(value):
        if value is None:
            return ()
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            return tuple(value)
        if isinstance(value, (bytes, bytearray)):
            return tuple(value)
        return (value,)

    def _require_sensor_count(self, values, method_name):
        if len(values) != self.SENSOR_COUNT:
            raise ValueError(method_name + " needs 8 values")

    def set_calibration(self, minimum, maximum):
        """Set calibration min and max arrays."""
        self.set_min(minimum)
        return self.set_max(maximum)

    def get_config(self):
        """Return config as a dictionary."""
        raw = self.show_config()
        names = (
            "maj_version",
            "min_version",
            "load_cal_startup",
            "cal_duration",
            "shape_threshold_black",
            "ir_power",
            "crc",
        )
        result = {}
        for index, name in enumerate(names):
            result[name] = raw[index] if index < len(raw) else None
        return result

    def uid_hex(self):
        """[pybricks:omit] Return CH32V203 UID as a hex string."""
        return "".join("%02x" % byte for byte in self.get_uid())

    def set_load_cal_startup(self, calibrated=True):
        """Configure whether calibration is loaded during firmware startup."""
        return self.set_value(self.CONFIG_LOAD_CAL_STARTUP, 1 if calibrated else 0)

    def set_cal_duration(self, seconds):
        """Set firmware calibration duration in seconds."""
        return self.set_value(self.CONFIG_CAL_DURATION, seconds)

    def set_shape_threshold_black(self, threshold):
        """Set the shape-detection black threshold."""
        return self.set_value(self.CONFIG_SHAPE_THRESHOLD_BLACK, threshold)

    def set_ir_emitter_startup(self, emitter=True):
        """Configure emitter state after firmware startup."""
        return self.set_value(self.CONFIG_IR_POWER, 1 if emitter else 0)

    def sensors(self):
        """Read the 8 sensor channel values."""
        return self.data(self.VALUES)

    def position(self):
        """Read the line position (-128 to 127, where 0 is center)."""
        return self.data(self.POSITION)

    def derivative(self):
        """Read the position derivative (rate of position change)."""
        return self.data(self.DERIVATIVE)

    def position_derivative(self):
        """Backward-compatible alias for derivative()."""
        return self.derivative()

    def shape(self):
        """Read the line shape as an ASCII character."""
        return self.data(self.SHAPE)

    def position_derivative_shape(self):
        """Read line position, derivative, and shape."""
        return self.data(self.POSITION, self.DERIVATIVE, self.SHAPE)

    def mode_calibrated(self):
        """Set sensor to calibrated mode."""
        return self.mode(self.MODE_CALIBRATED)

    def mode_raw(self):
        """Set sensor to raw mode."""
        return self.mode(self.MODE_RAW)