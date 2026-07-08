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
    def _first(value, default=None):
        if value is None:
            return default
        if isinstance(value, (list, tuple)):
            return value[0] if value else default
        if isinstance(value, (bytes, bytearray)):
            return value[0] if value else default
        return value

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

    def data(self, *indices):
        """Implemented in subclasses."""
        raise RuntimeError("Subclasses must implement data().")

    def mode_raw(self):
        raise RuntimeError("Subclasses must implement mode_raw().")

    def mode_calibrated(self):
        raise RuntimeError("Subclasses must implement mode_calibrated().")

    def calibrate(self, duration=5):
        raise RuntimeError("Subclasses must implement calibrate().")

    def load_calibration(self):
        raise RuntimeError("Subclasses must implement load_calibration().")

    def save_calibration(self):
        raise RuntimeError("Subclasses must implement save_calibration().")

    def ir_power(self, power):
        raise RuntimeError("Subclasses must implement ir_power().")

    def leds(self, mode):
        raise RuntimeError("Subclasses must implement leds().")

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
