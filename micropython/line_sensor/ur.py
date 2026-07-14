"""uRemote transport for the LMS line sensor."""

from .base import BaseLineSensor

try:
    from pybricks.tools import wait
except ImportError:
    from time import sleep
    def wait(ms):
        sleep(ms / 1000)

class LineSensorUR(BaseLineSensor):
    """Connect to the sensor over uRemote.

    Args:
        port (str or Port): port for the uRemote connection. E.g. "A", Port.A, or None.
        settle_ms (int): Milliseconds to wait after sending a command.
        remote_class (class): uRemote client class. Defaults to uRemote.
            Pass a stub class for testing.
    """

    def __init__(self, port, settle_ms=1, remote_class=None):
        from uremote import uRemote, uRemoteError
        self.ur_error = uRemoteError
        if port:
            self.ur = (remote_class or uRemote)(port)
        else:
            self.ur = uRemote()
        self.settle_ms = settle_ms

    def _call(self, command, *args):
        return self.ur.call(command, *args)

    def _call_compat(self, variants, default=None):
        last_error = None
        for command, args in variants:
            try:
                return self._call(command, *args)
            except self.ur_error as exc:
                last_error = exc
        if default is not None:
            return default
        if last_error is not None:
            raise last_error
        raise self.ur_error("No compatible remote command found")

    def ping(self):
        return self._call("ping")

    def add(self, a, b):
        return self._call("add", a, b)

    def echo(self, value):
        return self._call_compat((("print", (value,)), ("echo", (value,))))

    def version(self):
        return self._bytes_tuple(self._call_compat((("get_version", ()),), default=()))

    def debug(self, level):
        return self._call_compat((("debug", (level,)),))

    def mode(self, mode=None):
        if mode is None:
            return self._call_compat((("mode", ()), ("cur_mode", ())), default=None)
        return self._call_compat((("mode", (mode,)),))

    def current_mode(self):
        return self._call_compat((("cur_mode", ()), ("mode", ())), default=None)

    def mode_raw(self):
        return self._call_compat((("mode", (self.MODE_RAW,)), ("set_mode_raw", ())), default=None)

    def mode_calibrated(self):
        return self._call_compat(
            (("mode", (self.MODE_CALIBRATED,)), ("set_mode_cal", ())), default=None
        )

    def read_all(self):
        if self.settle_ms:
            wait(self.settle_ms)
        return self._bytes_tuple(self._call("all"))

    def read_sensors(self):
        return self._bytes_tuple(self._call_compat((("data", ()),), default=()))

    def data(self, *indices):
        raw = self.read_all()
        return self._select_indices(raw, indices)

    def position_byte(self):
        return self._call_compat((("pos", ()),), default=None)

    def shape_byte(self):
        return self._call_compat((("shape", ()),), default=None)

    def pds_raw(self):
        return self._bytes_tuple(self._call_compat((("pds", ()), ("pdr", ())), default=()))

    def pdr_raw(self):
        return self.pds_raw()

    def position_derivative_shape(self):
        raw = self.pds_raw()
        if len(raw) >= 3:
            return (raw[0] - 128, raw[1] - 128, chr(raw[2]))
        return super().position_derivative_shape()

    def blackline(self):
        return bool(self._call_compat((("blackline", ()),), default=0))

    def start_calibration(self, save=False):
        return self._call_compat((("calibrate", (1 if save else 0,)), ("calibrate", ())),)

    def calibrate(self, duration=None, save=True):
        self.leds(self.LEDS_OFF)
        self.start_calibration(save=save)
        if duration is None:
            duration = self.get_value(self.CONFIG_CAL_DURATION)
            if duration is None:
                duration = 5
        wait(1000 * (duration + 1))
        if save:
            try:
                self.save_calibration()
            except self.ur_error:
                pass
        return self.is_calibrated()

    def is_calibrated(self):
        return bool(self._call_compat((("is_calibrated", ()),), default=0))

    def save_calibration(self):
        return self._call_compat((("save_cal", ()), ("save", ())), default=None)

    def load_calibration(self):
        return self._call_compat((("load_cal", ()), ("load", ())), default=None)

    def get_min(self):
        return self._bytes_tuple(self._call_compat((("get_min", ()),), default=()))

    def get_max(self):
        return self._bytes_tuple(self._call_compat((("get_max", ()),), default=()))

    def set_min(self, values):
        if len(values) != self.SENSOR_COUNT:
            raise ValueError("set_min needs 8 values")
        return self._call_compat((("set_min", tuple(values)),), default=None)

    def set_max(self, values):
        if len(values) != self.SENSOR_COUNT:
            raise ValueError("set_max needs 8 values")
        return self._call_compat((("set_max", tuple(values)),), default=None)

    def set_calibration(self, minimum, maximum):
        self.set_min(minimum)
        return self.set_max(maximum)

    def get_value(self, index):
        return self._call_compat((("get_value", (index,)),), default=None)

    def set_value(self, index, value):
        return self._call_compat((("set_value", (index, value)),), default=None)

    def show_config(self):
        return self._bytes_tuple(self._call_compat((("show_config", ()),), default=()))

    def load_config(self):
        return self._call_compat((("load_config", ()),), default=None)

    def save_config(self):
        return self._call_compat((("save_config", ()),), default=None)

    def config(self):
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

    def set_load_cal_startup(self, calibrated=True):
        return self.set_value(self.CONFIG_LOAD_CAL_STARTUP, 1 if calibrated else 0)

    def set_cal_duration(self, seconds):
        return self.set_value(self.CONFIG_CAL_DURATION, seconds)

    def set_shape_threshold_black(self, threshold):
        return self.set_value(self.CONFIG_SHAPE_THRESHOLD_BLACK, threshold)

    def set_ir_emitter_startup(self, emitter=True):
        return self.set_value(self.CONFIG_IR_POWER, 1 if emitter else 0)

    def leds(self, mode):
        return self._call_compat((("led", (mode,)), ("leds", (mode,))), default=None)

    def neopixel(self, led_nr, r, g, b):
        return self._call_compat((("neopixel", (led_nr, r, g, b)),), default=None)

    def ir_power(self, power):
        value = 1 if power else 0
        return self._call_compat(
            (("emitter", (power,)), ("set_emitter", (value,))), default=None
        )

    def get_uid(self):
        return self._bytes_tuple(self._call_compat((("get_uid", ()),), default=()))

    def uid_hex(self):
        return "".join("%02x" % byte for byte in self.get_uid())
