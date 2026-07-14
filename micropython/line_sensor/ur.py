"""uRemote transport for the LMS line sensor."""

from .base import BaseLineSensor

try:
    from pybricks.tools import wait
except ImportError:
    from time import sleep

    def wait(ms):
        sleep(ms / 1000)


class LineSensorUR(BaseLineSensor):
    """LMS Line Sensor using the Pybricks uRemote transport on UART."""

    def __init__(self, port=None, settle_ms=1, remote_class=None):
        """Connect to the sensor over uRemote.

        Args:
            port (str or Port): port for the uRemote connection. E.g. "A", Port.A, or None.
            settle_ms (int): Milliseconds to wait after sending a command.
            remote_class (class): uRemote client class. Defaults to uRemote.
                Pass a stub class for testing.
        """
        from uremote import uRemote, uRemoteError

        self.ur_error = uRemoteError
        remote = remote_class or uRemote
        self.ur = remote(port) if port else remote()
        self.settle_ms = settle_ms
        config = self.show_config()
        self.version = "{}.{}".format(config[self.CONFIG_MAJ_VERSION], config[self.CONFIG_MIN_VERSION])
        self.cal_duration = config[self.CONFIG_CAL_DURATION]

    def ping(self):
        """[pybricks:omit] Return the firmware millisecond counter."""
        return self.ur.call("ping")

    def add(self, a, b):
        """[pybricks:omit] Protocol self-test that returns a + b."""
        return self.ur.call("add", a, b)

    def echo(self, value):
        """[pybricks:omit] Echo a value through the firmware print helper."""
        return self.ur.call("print", value)

    def version(self):
        """[pybricks:omit] Return firmware version as (major, minor)."""
        return self._bytes_tuple(self.ur.call("get_version"))

    def debug(self, level):
        """[pybricks:omit] Set firmware debug log level and return the active level."""
        return self.ur.call("debug", level)

    def mode(self, mode=None):
        """Get or set numeric mode."""
        if mode is None:
            return self.ur.call("mode")
        return self.ur.call("mode", mode)

    def current_mode(self):
        """[pybricks:omit] Return the active firmware mode."""
        return self.ur.call("cur_mode")

    def mode_raw(self):
        """[pybricks:omit] Set sensor to raw mode."""
        return self.ur.call("set_mode_raw")

    def mode_calibrated(self):
        """[pybricks:omit] Set sensor to calibrated mode."""
        return self.ur.call("set_mode_cal")

    def read_all(self):
        """Read all 13 sensor/result bytes from firmware."""
        if self.settle_ms:
            wait(self.settle_ms)
        return self._bytes_tuple(self.ur.call("all"))

    def read_sensors(self):
        """[pybricks:omit] Read only the 8 sensor bytes from firmware."""
        return self._bytes_tuple(self.ur.call("data"))

    def data(self, *indices):
        """Read sensor data with optional index-based filtering."""
        raw = self.read_all()
        return self._select_indices(raw, indices)

    def position_byte(self):
        """[pybricks:omit] Read raw position byte, 0..255, centered around 128."""
        return self.ur.call("pos")

    def shape_byte(self):
        """[pybricks:omit] Read raw shape byte."""
        return self.ur.call("shape")

    def pds_raw(self):
        """[pybricks:omit] Read raw position, derivative, shape bytes."""
        return self._bytes_tuple(self.ur.call("pds"))

    def pdr_raw(self):
        """[pybricks:omit] Compatibility alias for pds_raw()."""
        return self._bytes_tuple(self.ur.call("pdr"))

    def blackline(self):
        """[pybricks:omit] Return True when firmware reports black-line mode."""
        return bool(self.ur.call("blackline") or 0)

    def start_calibration(self, save=False):
        """Start calibration. Pass save=True to store calibration when firmware stops."""
        return self.ur.call("calibrate", 1 if save else 0)

    def calibrate(self, duration=None, save=True):
        """Start calibration, wait, and optionally save."""
        self.leds(self.LEDS_OFF)
        self.start_calibration(save=save)
        if duration is None:
            duration = self.cal_duration
        wait(1000 * (duration + 1))
        return self.is_calibrated()

    def is_calibrated(self):
        """Return True when calibration data is active."""
        return bool(self.ur.call("is_calibrated") or 0)

    def save_calibration(self):
        """Save calibration values to EEPROM."""
        return self.ur.call("save_cal")

    def load_calibration(self):
        """Load calibration values from EEPROM."""
        return self.ur.call("load_cal")

    def get_min(self):
        """Return the 8 calibration minimum bytes."""
        return self._bytes_tuple(self.ur.call("get_min"))

    def get_max(self):
        """Return the 8 calibration maximum bytes."""
        return self._bytes_tuple(self.ur.call("get_max"))

    def set_min(self, values):
        """Set the 8 calibration minimum bytes."""
        self._require_sensor_count(values, "set_min")
        return self.ur.call("set_min", *values)

    def set_max(self, values):
        """Set the 8 calibration maximum bytes."""
        self._require_sensor_count(values, "set_max")
        return self.ur.call("set_max", *values)

    def get_value(self, index):
        """[pybricks:omit] Read one config byte by index."""
        return self.ur.call("get_value", index)

    def set_value(self, index, value):
        """[pybricks:omit] Write one config byte by index and save config."""
        return self.ur.call("set_value", index, value)

    def show_config(self):
        """Return raw config bytes."""
        return self._bytes_tuple(self.ur.call("show_config"))

    def load_config(self):
        """Load config from EEPROM, using firmware defaults if invalid."""
        return self.ur.call("load_config")

    def save_config(self):
        """Save current config to EEPROM."""
        return self.ur.call("save_config")

    def leds(self, mode):
        """Set LED display mode and return active LED mode."""
        return self.ur.call("leds", mode)

    def neopixel(self, led_nr, r, g, b):
        """Set one NeoPixel color."""
        return self.ur.call("neopixel", led_nr, r, g, b)

    def ir_power(self, power):
        """Set the IR emitter off/on."""
        return self.ur.call("set_emitter", 1 if power else 0)

    def get_uid(self):
        """Return 12 CH32V203 UID bytes."""
        return self._bytes_tuple(self.ur.call("get_uid"))
