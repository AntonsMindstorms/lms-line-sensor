"""Base API for the standalone Pybricks bundle."""

__version__ = "0.3.0"


class BaseLineSensor:
    RAW_BYTES = 13
    SENSOR_COUNT = 8

    MODE_RAW = 0
    MODE_CALIBRATED = 1

    POSITION = 8
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

    def _decode_index(self, raw, idx):
        if idx == self.VALUES:
            return tuple(raw[: self.SENSOR_COUNT])
        if idx == self.POSITION or idx == self.DERIVATIVE:
            return raw[idx] - 128
        if idx == self.SHAPE:
            return chr(raw[idx])
        return raw[idx]

    def _select_indices(self, raw, indices):
        raw = tuple(raw)
        if not indices:
            return raw
        if len(indices) == 1:
            return self._decode_index(raw, indices[0])

        out = []
        for idx in indices:
            decoded = self._decode_index(raw, idx)
            if idx == self.VALUES:
                out.extend(decoded)
            else:
                out.append(decoded)
        return tuple(out)

    def sensors(self):
        return self.data(self.VALUES)

    def position(self):
        return self.data(self.POSITION)

    def derivative(self):
        return self.data(self.DERIVATIVE)

    def position_derivative(self):
        return self.derivative()

    def shape(self):
        return self.data(self.SHAPE)

    def position_derivative_shape(self):
        return self.data(self.POSITION, self.DERIVATIVE, self.SHAPE)
