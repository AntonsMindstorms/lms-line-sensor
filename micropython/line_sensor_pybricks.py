"""Generated standalone Pybricks driver for the LMS line sensor.

Do not edit by hand. Regenerate with:
`python tools/generate_line_sensor_pybricks.py`
"""

__all__ = ['BaseLineSensor', 'LineSensorUR', 'uRemote', 'uRemoteError', '__version__']

"""Shared API and constants for LMS line sensor drivers."""

class BaseLineSensor:
    """Base class for LMS Line Sensor implementations."""
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
    SHAPE_NONE = ' '
    SHAPE_STRAIGHT = '|'
    SHAPE_T = 'T'
    SHAPE_L_LEFT = '<'
    SHAPE_L_RIGHT = '>'
    SHAPE_Y = 'Y'
    CONFIG_MAJ_VERSION = 0
    CONFIG_MIN_VERSION = 1
    CONFIG_LOAD_CAL_STARTUP = 2
    CONFIG_CAL_DURATION = 3
    CONFIG_SHAPE_THRESHOLD_BLACK = 4
    CONFIG_IR_POWER = 5
    CONFIG_CRC = 6

    def _decode_index(self, raw, idx):
        if idx == self.VALUES:
            return tuple(raw[:self.SENSOR_COUNT])
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
            raise ValueError(method_name + ' needs 8 values')

    def set_calibration(self, minimum, maximum):
        self.set_min(minimum)
        return self.set_max(maximum)

    def get_config(self):
        raw = self.show_config()
        names = ('maj_version', 'min_version', 'load_cal_startup', 'cal_duration', 'shape_threshold_black', 'ir_power', 'crc')
        result = {}
        for (index, name) in enumerate(names):
            result[name] = raw[index] if index < len(raw) else None
        return result

    def set_load_cal_startup(self, calibrated=True):
        return self.set_value(self.CONFIG_LOAD_CAL_STARTUP, 1 if calibrated else 0)

    def set_cal_duration(self, seconds):
        return self.set_value(self.CONFIG_CAL_DURATION, seconds)

    def set_shape_threshold_black(self, threshold):
        return self.set_value(self.CONFIG_SHAPE_THRESHOLD_BLACK, threshold)

    def set_ir_emitter_startup(self, emitter=True):
        return self.set_value(self.CONFIG_IR_POWER, 1 if emitter else 0)

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

    def mode_calibrated(self):
        return self.mode(self.MODE_CALIBRATED)

    def mode_raw(self):
        return self.mode(self.MODE_RAW)

"""Minimal Pybricks-only uRemote client for standalone bundling."""

from pybricks.iodevices import UARTDevice
from pybricks.parameters import Port
from pybricks.tools import StopWatch, wait


def const(value):
    return value


STATUS_OK = const(0)
STATUS_ERR = const(1)
MAX_FRAME = const(255)
MIN_FRAME = const(5)
MAX_CMD_LEN = const(31)
PREAMBLE = b"<$MU"
PREAMBLE_LEN = const(4)

_T_BOOL = const(66)
_T_NUM = const(78)
_T_BYTES = const(65)
_T_STR = const(83)


class uRemoteError(Exception):
    pass


def _unwrap_result(payload):
    if payload is None:
        return None
    if isinstance(payload, list):
        return payload[0] if len(payload) == 1 else tuple(payload)
    return payload


class uRemote:
    """Pybricks UART RPC client."""

    def __init__(
        self, port_or_uart=1, baudrate=115200, wait_recv=1000, uart_timeout=1000, power_pin=2
    ):
        self.byte_timeout = 10
        self.wait_recv = wait_recv
        self._last_rx_error = None
        self._watch = StopWatch()
        if isinstance(port_or_uart, str):
            port_or_uart = getattr(Port, port_or_uart)
        self.uart = UARTDevice(port_or_uart, timeout=uart_timeout, power_pin=power_pin)
        self.uart.set_baudrate(baudrate)
        self.uart.read_all()

    def _ticks(self):
        return self._watch.time()

    def _elapsed(self, start):
        return self._watch.time() - start

    def _waiting(self):
        return self.uart.waiting()

    def _read_byte(self):
        data = self.uart.read(1)
        return data[0] if data else None

    def flush(self):
        while self._waiting():
            self.uart.read_all()

    def _fail_rx(self, error):
        self.flush()
        self._last_rx_error = "Read error: " + error
        return b""

    def _send_bytes(self, payload):
        frame = PREAMBLE + payload
        if len(frame) > MAX_FRAME:
            raise uRemoteError("frame too large")
        self.uart.write(bytes([len(frame)]) + frame)

    def _recv_bytes(self):
        self._last_rx_error = None
        start = self._ticks()
        while self._elapsed(start) < self.wait_recv and not self._waiting():
            wait(1)
        if not self._waiting():
            return self._fail_rx("No data. Is remote script running?")

        length = self._read_byte()
        if length is None or length < MIN_FRAME or length > MAX_FRAME:
            if length is None:
                return self._fail_rx("No length byte. Is remote script running?")
            return self._fail_rx("Invalid frame length")

        payload = bytearray()
        total_start = self._ticks()
        byte_start = total_start
        preamble_index = 0
        while len(payload) < length:
            if self._elapsed(total_start) > self.wait_recv:
                return self._fail_rx("Incomplete frame.")
            if self._waiting():
                value = self._read_byte()
                if value is None:
                    return self._fail_rx("Incomplete frame.")
                payload.append(value)
                if preamble_index < PREAMBLE_LEN:
                    if value != PREAMBLE[preamble_index]:
                        return self._fail_rx("Preamble mismatch.")
                    preamble_index += 1
                byte_start = self._ticks()
            elif self._elapsed(byte_start) > self.byte_timeout:
                return self._fail_rx("Inter-byte timeout.")
            else:
                wait(1)
        return bytes(payload[PREAMBLE_LEN:])

    def _encode(self, status, cmd, *argv):
        name_len = len(cmd)
        if name_len > MAX_CMD_LEN:
            raise uRemoteError("command name too long")
        out = bytes([(status << 5) | name_len]) + bytes(cmd, "utf-8")
        for arg in argv:
            if type(arg) == bool:
                out += bytes([_T_BOOL, 1, 1 if arg else 0])
            elif type(arg) == int:
                raw = str(arg)
                out += bytes([_T_NUM, len(raw)]) + bytes(raw, "utf-8")
            elif type(arg) == bytes:
                out += bytes([_T_BYTES, len(arg)]) + arg
            elif type(arg) == str:
                out += bytes([_T_STR, len(arg)]) + bytes(arg, "utf-8")
            else:
                raise TypeError("unsupported type")
        return out

    def _decode(self, encoded):
        header = encoded[0]
        status = header >> 5
        name_len = header & 0x1F
        cmd = str(encoded[1 : 1 + name_len], "utf-8")
        decoded = []
        pos = 1 + name_len
        while pos < len(encoded):
            item_type = encoded[pos]
            item_len = encoded[pos + 1]
            pos += 2
            chunk = encoded[pos : pos + item_len]
            pos += item_len
            if item_type == _T_NUM:
                decoded.append(int(chunk))
            elif item_type == _T_BYTES:
                decoded.append(chunk)
            elif item_type == _T_STR:
                decoded.append(str(chunk, "utf-8"))
            elif item_type == _T_BOOL:
                decoded.append(bool(chunk[0]))
            else:
                raise ValueError("unknown type " + str(item_type))
        if len(decoded) == 1:
            decoded = decoded[0]
        return status, cmd, decoded

    def call(self, cmd, *data):
        self._send_bytes(self._encode(STATUS_OK, cmd, *data))
        reply = self._recv_bytes()
        if not reply:
            raise uRemoteError(self._last_rx_error or "no bytes received")
        try:
            status, reply_cmd, payload = self._decode(reply)
        except (ValueError, IndexError, UnicodeError) as exc:
            self.flush()
            raise uRemoteError("decode error: " + str(exc))
        if status != STATUS_OK or not reply_cmd:
            raise uRemoteError(payload if isinstance(payload, str) else str(payload))
        if reply_cmd != cmd:
            raise uRemoteError("unexpected reply: " + reply_cmd)
        return _unwrap_result(payload)

"""uRemote transport for the LMS line sensor."""

class LineSensorUR(BaseLineSensor):
    """LMS Line Sensor using the Pybricks uRemote transport on UART."""

    def __init__(self, port=None, settle_ms=1):
        self.ur = uRemote(port) if port else uRemote()
        self.settle_ms = settle_ms
        config = self.show_config()
        self.version = '{}.{}'.format(config[self.CONFIG_MAJ_VERSION], config[self.CONFIG_MIN_VERSION])
        self.cal_duration = config[self.CONFIG_CAL_DURATION]

    def mode(self, mode=None):
        if mode is None:
            return self.ur.call('mode')
        return self.ur.call('mode', mode)

    def read_all(self):
        if self.settle_ms:
            wait(self.settle_ms)
        return self._bytes_tuple(self.ur.call('all'))

    def data(self, *indices):
        raw = self.read_all()
        return self._select_indices(raw, indices)

    def start_calibration(self, save=False):
        return self.ur.call('calibrate', 1 if save else 0)

    def calibrate(self, duration=None, save=True):
        self.leds(self.LEDS_OFF)
        self.start_calibration(save=save)
        if duration is None:
            duration = self.cal_duration
        wait(1000 * (duration + 1))
        return self.is_calibrated()

    def is_calibrated(self):
        return bool(self.ur.call('is_calibrated') or 0)

    def save_calibration(self):
        return self.ur.call('save_cal')

    def load_calibration(self):
        return self.ur.call('load_cal')

    def get_min(self):
        return self._bytes_tuple(self.ur.call('get_min'))

    def get_max(self):
        return self._bytes_tuple(self.ur.call('get_max'))

    def set_min(self, values):
        self._require_sensor_count(values, 'set_min')
        return self.ur.call('set_min', *values)

    def set_max(self, values):
        self._require_sensor_count(values, 'set_max')
        return self.ur.call('set_max', *values)

    def show_config(self):
        return self._bytes_tuple(self.ur.call('show_config'))

    def load_config(self):
        return self.ur.call('load_config')

    def save_config(self):
        return self.ur.call('save_config')

    def leds(self, mode):
        return self.ur.call('leds', mode)

    def neopixel(self, led_nr, r, g, b):
        return self.ur.call('neopixel', led_nr, r, g, b)

    def ir_power(self, power):
        return self.ur.call('set_emitter', 1 if power else 0)

    def get_uid(self):
        return self._bytes_tuple(self.ur.call('get_uid'))
