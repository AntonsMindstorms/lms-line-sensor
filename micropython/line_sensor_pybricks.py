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

    def _then(self, result, *steps):
        for i, step in enumerate(steps):
            if hasattr(result, 'send'):
                return self._finish_async(result, steps[i:])
            result = step(result)
        return result

    async def _finish_async(self, pending, steps):
        result = await pending
        for step in steps:
            result = step(result)
            if hasattr(result, 'send'):
                result = await result
        return result

    def _require_sensor_count(self, values, method_name):
        if len(values) != self.SENSOR_COUNT:
            raise ValueError(method_name + ' needs 8 values')

    def set_calibration(self, minimum, maximum):
        return self._then(self.set_cal_min(minimum), lambda _: self.set_cal_max(maximum))

    def get_configuration(self, as_text=True):
        if not as_text:
            return self.get_config()
        names = ('maj_version', 'min_version', 'load_cal_startup', 'cal_duration', 'shape_threshold_black', 'ir_power', 'crc')
        return self._then(self.get_config(), lambda raw: {name: raw[i] if i < len(raw) else None for i, name in enumerate(names)})

    def set_load_cal_startup(self, calibrated=True):
        return self.set_conf_value(self.CONFIG_LOAD_CAL_STARTUP, 1 if calibrated else 0)

    def set_cal_duration(self, seconds):
        return self.set_conf_value(self.CONFIG_CAL_DURATION, seconds)

    def set_shape_threshold_black(self, threshold):
        return self.set_conf_value(self.CONFIG_SHAPE_THRESHOLD_BLACK, threshold)

    def set_ir_emitter_startup(self, emitter=True):
        return self.set_conf_value(self.CONFIG_IR_POWER, 1 if emitter else 0)

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

def const(value):
    return value
STATUS_OK = const(0)
STATUS_ERR = const(1)
MAX_FRAME = const(255)
MIN_FRAME = const(5)
MAX_CMD_LEN = const(31)
PREAMBLE = b'<$MU'
PREAMBLE_LEN = const(4)
_READ = const(0)
_PAUSE = const(1)
_WRITE = const(2)
_T_BOOL = const(66)
_T_NUM = const(78)
_T_BYTES = const(65)
_T_STR = const(83)
from pybricks.iodevices import UARTDevice
from pybricks.tools import StopWatch, wait, run_task
from pybricks.parameters import Port

class uRemoteError(Exception):
    pass

def _as_values(data):
    if isinstance(data, list):
        return data
    return [] if data is None else [data]

def _unwrap_result(payload):
    values = _as_values(payload)
    if not values:
        return None
    return values[0] if len(values) == 1 else tuple(values)

class uRemote:

    def __init__(self, port_or_uart=1, baudrate=115200, wait_recv=1000, uart_timeout=1000, power_pin=2):
        self.byte_timeout = 10
        self.wait_recv = wait_recv
        self._last_rx_error = None
        self._async_busy = False
        self._watch = StopWatch()
        if isinstance(port_or_uart, str):
            port_or_uart = eval('Port.' + port_or_uart)
        self.uart = UARTDevice(port_or_uart, timeout=uart_timeout, power_pin=power_pin)
        self.uart.set_baudrate(baudrate)
        self.uart.read_all()
        self._ticks = self._watch.time
        self._elapsed = lambda start: self._watch.time() - start
        self._pause = wait
        self._waiting = self.uart.waiting
        self._drain = self.uart.read_all

    def _fail_rx(self, error):
        self.flush()
        self._last_rx_error = 'Read error: ' + error
        return b''

    def flush(self):
        while self._waiting():
            self._drain()

    def _packet(self, payload):
        frame = PREAMBLE + payload
        if len(frame) > MAX_FRAME:
            raise uRemoteError('frame too large')
        return bytes([len(frame)]) + frame

    def _recv_steps(self):
        self._last_rx_error = None
        start = self._ticks()
        while self._elapsed(start) < self.wait_recv and (not self._waiting()):
            yield _PAUSE
        if not self._waiting():
            return self._fail_rx('No data. Is remote script running?')
        length = (yield _READ)
        if length is None or length < MIN_FRAME or length > MAX_FRAME:
            return self._fail_rx('No length byte. Is remote script running?' if length is None else 'Invalid frame length')
        payload = bytearray()
        total_start = byte_start = self._ticks()
        pre = 0
        while len(payload) < length:
            if self._elapsed(total_start) > self.wait_recv:
                return self._fail_rx('Incomplete frame.')
            if self._waiting():
                b = (yield _READ)
                if b is None:
                    return self._fail_rx('Incomplete frame.')
                payload.append(b)
                if pre < PREAMBLE_LEN:
                    if b != PREAMBLE[pre]:
                        return self._fail_rx('Preamble mismatch.')
                    pre += 1
                byte_start = self._ticks()
            elif self._elapsed(byte_start) > self.byte_timeout:
                return self._fail_rx('Inter-byte timeout.')
            else:
                yield _PAUSE
        return bytes(payload[PREAMBLE_LEN:])

    def _encode(self, status, cmd, *argv):
        n = len(cmd)
        if n > MAX_CMD_LEN:
            raise uRemoteError('command name too long')
        out = bytes([status << 5 | n]) + bytes(cmd, 'utf-8')
        for arg in argv:
            if type(arg) == bool:
                out += bytes([_T_BOOL, 1, 1 if arg else 0])
            elif type(arg) == int:
                s = str(arg)
                out += bytes([_T_NUM, len(s)]) + bytes(s, 'utf-8')
            elif type(arg) == bytes:
                out += bytes([_T_BYTES, len(arg)]) + arg
            elif type(arg) == str:
                out += bytes([_T_STR, len(arg)]) + bytes(arg, 'utf-8')
            else:
                raise TypeError('unsupported type')
        return out

    def _decode(self, encoded):
        hdr = encoded[0]
        status, n = (hdr >> 5, hdr & 31)
        cmd = str(encoded[1:1 + n], 'utf-8')
        decoded, p = ([], 1 + n)
        while p < len(encoded):
            t, ln = (encoded[p], encoded[p + 1])
            p += 2
            chunk = encoded[p:p + ln]
            p += ln
            if t == _T_NUM:
                decoded.append(int(chunk))
            elif t == _T_BYTES:
                decoded.append(chunk)
            elif t == _T_STR:
                decoded.append(str(chunk, 'utf-8'))
            elif t == _T_BOOL:
                decoded.append(bool(chunk[0]))
            else:
                raise ValueError('unknown type ' + str(t))
        if len(decoded) == 1:
            decoded = decoded[0]
        return (status, cmd, decoded)

    def _decode_command(self, b):
        if not b:
            return (STATUS_ERR, '', self._last_rx_error or 'no bytes received')
        try:
            return self._decode(b)
        except (ValueError, IndexError, UnicodeError) as e:
            self.flush()
            return (STATUS_ERR, '', 'decode error: ' + str(e))

    def _exchange_steps(self, cmd, data):
        yield (_WRITE, self._packet(self._encode(STATUS_OK, cmd, *data)))
        b = (yield from self._recv_steps())
        return self._decode_command(b)

    def _call_steps(self, cmd, data):
        self.flush()
        reply = (yield from self._exchange_steps(cmd, data))
        return self._finish_call(cmd, *reply)

    def _drive_sync(self, steps):
        try:
            op = next(steps)
            while True:
                if op == _READ:
                    b = self.uart.read(1)
                    op = steps.send(b[0] if b else None)
                elif op == _PAUSE:
                    self._pause(1)
                    op = steps.send(None)
                else:
                    self.uart.write(op[1])
                    op = steps.send(None)
        except StopIteration as e:
            return e.args[0] if e.args else None

    async def _drive_async(self, steps):
        while self._async_busy:
            await wait(0)
        self._async_busy = True
        try:
            op = next(steps)
            while True:
                if op == _READ:
                    b = await self.uart.read(1)
                    op = steps.send(b[0] if b else None)
                elif op == _PAUSE:
                    await wait(0)
                    op = steps.send(None)
                else:
                    await self.uart.write(op[1])
                    op = steps.send(None)
        except StopIteration as e:
            return e.args[0] if e.args else None
        finally:
            self._async_busy = False

    def _drive(self, steps):
        if run_task():
            return self._drive_async(steps)
        return self._drive_sync(steps)

    def _finish_call(self, cmd, status, reply_cmd, payload):
        if status != STATUS_OK or not reply_cmd:
            raise uRemoteError(payload if isinstance(payload, str) else str(payload))
        if reply_cmd != cmd:
            self.flush()
            raise uRemoteError('unexpected reply: ' + reply_cmd)
        return _unwrap_result(payload)

    def exchange(self, cmd, *data):
        return self._drive(self._exchange_steps(cmd, data))

    def call(self, cmd, *data):
        return self._drive(self._call_steps(cmd, data))

    async def call_async(self, cmd, *data):
        return await self._drive_async(self._call_steps(cmd, data))

"""uRemote transport for the LMS line sensor."""

class LineSensorUR(BaseLineSensor):
    """LMS Line Sensor using the Pybricks uRemote transport on UART."""

    def __init__(self, port=None, settle_ms=1, remote_class=None):
        self.ur_error = uRemoteError
        remote = remote_class or uRemote
        self.ur = remote(port) if port else remote()
        self.settle_ms = settle_ms
        self.version = self.cal_duration = None
        self.get_config()

    def _wait(self, ms):
        pending = wait(ms) if ms else None
        return None if pending is None else self._finish_async(pending, ())

    def _call_bytes(self, cmd, *args):
        return self._then(self.ur.call(cmd, *args), self._bytes_tuple)

    def _call_bool(self, cmd, *args):
        return self._then(self.ur.call(cmd, *args), lambda value: bool(value or 0))

    def mode(self, mode=None):
        if mode is None:
            return self.ur.call('mode')
        return self.ur.call('mode', mode)

    def read_all(self):
        return self._then(self._wait(self.settle_ms), lambda _: self._call_bytes('all'))

    def data(self, *indices):
        return self._then(self.read_all(), lambda raw: self._select_indices(raw, indices))

    def blackline(self, black=None):
        if black is None:
            return self._call_bool('blackline')
        return self._call_bool('blackline', bool(black))

    def start_calibration(self, save=False):
        return self.ur.call('calibrate', 1 if save else 0)

    def calibrate(self, duration=None, save=True):
        return self._then(self.leds(self.LEDS_OFF), lambda _: self.start_calibration(save=save), lambda _: self.get_config() if duration is None and self.cal_duration is None else None, lambda _: self._wait(1000 * ((self.cal_duration if duration is None else duration) + 1)), lambda _: self.is_calibrated())

    def is_calibrated(self):
        return self._call_bool('is_calibrated')

    def save_calibration(self):
        return self.ur.call('save_cal')

    def load_calibration(self):
        return self.ur.call('load_cal')

    def get_cal_min(self):
        return self._call_bytes('get_cal_min')

    def get_cal_max(self):
        return self._call_bytes('get_cal_max')

    def set_cal_min(self, values):
        self._require_sensor_count(values, 'set_cal_min')
        return self.ur.call('set_cal_min', *values)

    def set_cal_max(self, values):
        self._require_sensor_count(values, 'set_cal_max')
        return self.ur.call('set_cal_max', *values)

    def get_config(self):
        return self._then(self._call_bytes('get_config'), self._remember_config)

    def _remember_config(self, config):
        self.version = '{}.{}'.format(config[self.CONFIG_MAJ_VERSION], config[self.CONFIG_MIN_VERSION])
        self.cal_duration = config[self.CONFIG_CAL_DURATION]
        return config

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

    def set_emitter(self, power):
        return self.ir_power(power)

    def get_uid(self):
        return self._call_bytes('get_uid')
