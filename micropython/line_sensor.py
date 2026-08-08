"""MicroPython driver for the LMS line sensor.

Single upload file for pyboards and local tests. Three sections:

  BaseLineSensor  — shared constants and high-level API
  LineSensorI2C   — I2C backend (LMS-ESP32 on pyboard)
  LineSensorUR    — uRemote/UART backend (needs separate uremote.py on pyboard;
                    included in the Pybricks bundle instead)

Regenerate the Pybricks bundle after edits:

  python tools/generate_line_sensor_pybricks.py
"""

__all__ = ['BaseLineSensor', 'LineSensorI2C', 'LineSensorUR', '__version__']

__version__ = "0.3.2"

"""Shared API and constants for LMS line sensor drivers."""



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
        self.set_cal_min(minimum)
        return self.set_cal_max(maximum)

    def get_configuration(self, as_text=True):
        """Return config as a dictionary."""
        raw = self.get_config()
        if as_text:
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
        else:
            return raw

    def uid_hex(self):
        """[pybricks:omit] Return CH32V203 UID as a hex string."""
        return "".join("%02x" % byte for byte in self.get_uid())

    def set_load_cal_startup(self, calibrated=True):
        """Configure whether calibration is loaded during firmware startup."""
        return self.set_conf_value(self.CONFIG_LOAD_CAL_STARTUP, 1 if calibrated else 0)

    def set_cal_duration(self, seconds):
        """Set firmware calibration duration in seconds."""
        return self.set_conf_value(self.CONFIG_CAL_DURATION, seconds)

    def set_shape_threshold_black(self, threshold):
        """Set the shape-detection black threshold."""
        return self.set_conf_value(self.CONFIG_SHAPE_THRESHOLD_BLACK, threshold)

    def set_ir_emitter_startup(self, emitter=True):
        """Configure emitter state after firmware startup."""
        return self.set_conf_value(self.CONFIG_IR_POWER, 1 if emitter else 0)

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

"""MicroPython I2C backend for the LMS line sensor."""



class LineSensorI2C(BaseLineSensor):
    """Control an LMS Line Sensor through its MicroPython I2C interface."""

    CMD_GET_VERSION = 2
    CMD_DEBUG = 3
    CMD_CALIBRATE = 4
    CMD_IS_CALIBRATED = 5
    CMD_LOAD_CAL = 6
    CMD_SAVE_CAL = 7
    CMD_GET_CAL_MIN = 8
    CMD_GET_CAL_MAX = 9
    CMD_SET_CAL_MIN = 10
    CMD_SET_CAL_MAX = 11
    CMD_NEOPIXEL = 12
    CMD_LEDS = 13
    CMD_SET_EMITTER = 14
    CMD_GET_CONF_VALUE = 15
    CMD_SET_CONF_VALUE = 16
    CMD_GET_CONFIG = 17
    CMD_LOAD_CONFIG = 18
    CMD_SAVE_CONFIG = 19
    CMD_UART_TEST = 22
    CMD_GET_UID = 24

    def __init__(
        self,
        i2c_id=1,
        scl_pin=4,
        sda_pin=5,
        device_addr=51,
        mode=None,
        freq=100000,
    ):
        """Initialize I2C, load calibration, and select the requested mode.

        Args:
            i2c_id: MicroPython I2C peripheral number.
            scl_pin: GPIO number used for the I2C clock.
            sda_pin: GPIO number used for I2C data.
            device_addr: Seven-bit sensor address; defaults to ``0x33``.
            mode: Initial sensor mode, or ``None`` for calibrated mode.
            freq: I2C clock frequency in hertz.
        """
        try:
            from machine import I2C, Pin
            from time import sleep, ticks_ms, ticks_diff
        except ImportError:
            raise RuntimeError(
                "LineSensorI2C requires machine and time modules. "
                "Use LineSensorUR for Pybricks."
            )

        self.device_addr = device_addr
        self.i2c = I2C(i2c_id, scl=Pin(scl_pin), sda=Pin(sda_pin), freq=freq)
        self.current_leds_mode = self.LEDS_OFF
        self.save_start_time = 0
        self.current_mode = self.MODE_CALIBRATED if mode is None else mode
        self.last_mode = self.current_mode
        self.black_line = False
        self.sleep = sleep
        self.ticks_ms = ticks_ms
        self.ticks_diff = ticks_diff

        # Preserve the previous "ready after init" behavior.
        self.load_calibration()
        self.mode_calibrated()
        self.check_line_type()
        if mode == self.MODE_RAW:
            self.mode_raw()

    def _retry(self, callback, attempts=4):
        """Run an I2C operation repeatedly and re-raise its last error."""
        last_error = None
        for _ in range(attempts):
            try:
                return callback()
            except Exception as exc:  # noqa: BLE001 - MicroPython compatibility.
                last_error = exc
        if last_error is not None:
            raise last_error
        raise RuntimeError("I2C operation failed")

    def robust_i2c_readfrom(self, device_addr, raw_bytes):
        """Read bytes from an I2C address, retrying transient failures."""
        return self._retry(lambda: self.i2c.readfrom(device_addr, raw_bytes))

    def _read_all(self):
        """Read the complete sensor packet or handle a pending save delay."""
        if self.current_mode < self.MODE_SAVING:
            return list(self.robust_i2c_readfrom(self.device_addr, self.RAW_BYTES))

        if self.current_mode == self.MODE_SAVING:
            if self.ticks_diff(self.ticks_ms(), self.save_start_time + 1500) > 0:
                self.write_command(self.last_mode)
                self.current_mode = self.last_mode
                print("Calibration stored in EEPROM")

        return [0] * self.RAW_BYTES

    def data(self, *indices):
        """Read sensor data and optionally return only selected packet fields."""
        raw = self._read_all()
        return self._select_indices(raw, indices, invert_values=self.black_line)

    def write_command(self, command):
        """Write a numeric command or command-byte sequence to the sensor."""
        if isinstance(command, int):
            payload = bytes([command])
        else:
            payload = bytes(command)
        self._retry(lambda: self.i2c.writeto(self.device_addr, payload))

    def mode_raw(self):
        """Select raw, uncalibrated sensor values."""
        self.current_mode = self.last_mode = self.MODE_RAW
        self.write_command(self.MODE_RAW)

    def mode_calibrated(self):
        """Select normalized values based on the active calibration limits."""
        self.current_mode = self.last_mode = self.MODE_CALIBRATED
        self.write_command(self.MODE_CALIBRATED)

    def start_calibration(self):
        """Start collecting calibration minima and maxima with LEDs off."""
        print("Starting calibration")
        self.last_mode = self.current_mode
        self.current_mode = self.MODE_CALIBRATING
        self.write_command((self.CMD_LEDS, self.LEDS_OFF))
        self.write_command(self.CMD_CALIBRATE)

    def save_calibration(self):
        """Stop calibration, save its limits, and restore the previous modes."""
        print("Stopping calibration and saving new values")
        self.write_command(self.MODE_CALIBRATED)
        self.write_command((self.CMD_LEDS, self.current_leds_mode))
        self.check_line_type()
        self.write_command(self.last_mode)
        self.write_command(self.CMD_SAVE_CAL)
        self.save_start_time = self.ticks_ms()
        self.current_mode = self.MODE_SAVING

    def check_line_type(self):
        """Detect whether the calibrated line is darker or lighter than its field."""
        values = list(self.robust_i2c_readfrom(self.device_addr, self.SENSOR_COUNT))
        average = sum(values) // len(values)
        self.black_line = average > 128
        print("Line is", "black" if self.black_line else "white")

    def calibrate(self, duration=5):
        """Run calibration for a duration in seconds and save the result."""
        self.start_calibration()
        self.sleep(duration)
        self.save_calibration()
        self.sleep(1.5)
        print("Calibration stored in EEPROM")
        self.current_mode = self.last_mode

    def ir_power(self, power):
        """Turn the IR emitter on or off."""
        self.write_command((self.CMD_SET_EMITTER, 1 if power else 0))

    def set_emitter(self, power):
        """Set the IR emitter state; alias for :meth:`ir_power`."""
        self.ir_power(power)

    def leds(self, mode):
        """Select the automatic NeoPixel display mode."""
        self.current_leds_mode = mode
        self.write_command((self.CMD_LEDS, mode))

    def load_calibration(self):
        """Load calibration minima and maxima from sensor EEPROM."""
        self.write_command(self.CMD_LOAD_CAL)

    def neopixel(self, led_nr, r, g, b):
        """Set one NeoPixel to an RGB color."""
        self.write_command((self.CMD_NEOPIXEL, led_nr, r, g, b))

    def set_neopixel(self, led_nr, r, g, b):
        """Set one NeoPixel color; alias for :meth:`neopixel`."""
        self.neopixel(led_nr, r, g, b)

    def rgb_mode(self, mode):
        """Select the LED display mode; alias for :meth:`leds`."""
        self.leds(mode)

    def led_mode(self, mode):
        """Select the LED display mode; alias for :meth:`leds`."""
        self.leds(mode)

    def get_min(self):
        """Return the eight calibration minimum values."""
        self.write_command(self.CMD_GET_CAL_MIN)
        return tuple(self.robust_i2c_readfrom(self.device_addr, self.SENSOR_COUNT))

    def get_max(self):
        """Return the eight calibration maximum values."""
        self.write_command(self.CMD_GET_CAL_MAX)
        return tuple(self.robust_i2c_readfrom(self.device_addr, self.SENSOR_COUNT))

    def get_cal_min(self):
        """Return calibration minima; alias for :meth:`get_min`."""
        return self.get_min()

    def get_cal_max(self):
        """Return calibration maxima; alias for :meth:`get_max`."""
        return self.get_max()

    def set_min(self, values):
        """Set the eight calibration minimum values in sensor memory."""
        if len(values) != self.SENSOR_COUNT:
            raise ValueError("values must contain 8 items")
        self.write_command(tuple([self.CMD_SET_CAL_MIN] + [int(v) & 0xFF for v in values]))

    def set_max(self, values):
        """Set the eight calibration maximum values in sensor memory."""
        if len(values) != self.SENSOR_COUNT:
            raise ValueError("values must contain 8 items")
        self.write_command(tuple([self.CMD_SET_CAL_MAX] + [int(v) & 0xFF for v in values]))

    def set_cal_min(self, values):
        """Set calibration minima; alias for :meth:`set_min`."""
        self.set_min(values)

    def set_cal_max(self, values):
        """Set calibration maxima; alias for :meth:`set_max`."""
        self.set_max(values)

    def set_calibration(self, minimum, maximum):
        """Set all calibration minimum and maximum values."""
        self.set_min(minimum)
        self.set_max(maximum)

    def version(self):
        """Return the firmware version as ``(major, minor)``."""
        self.write_command(self.CMD_GET_VERSION)
        return tuple(self.robust_i2c_readfrom(self.device_addr, 2))

    def set_debug(self, debug):
        """Send the reserved legacy debug command, currently a firmware no-op."""
        self.write_command((self.CMD_DEBUG, debug))

    def debug(self, level):
        """Send the legacy debug level and return the requested value."""
        self.set_debug(level)
        return level

    def is_calibrated(self):
        """Return whether calibration limits are active in sensor memory."""
        self.write_command(self.CMD_IS_CALIBRATED)
        return bool(self.robust_i2c_readfrom(self.device_addr, 1)[0])

    def get_value(self, index):
        """Read one configuration byte by index."""
        self.write_command((self.CMD_GET_CONF_VALUE, index))
        return self.robust_i2c_readfrom(self.device_addr, 1)[0]

    def set_value(self, index, value):
        """Set one configuration byte by index and return the written value."""
        self.write_command((self.CMD_SET_CONF_VALUE, index, value))
        return value

    def get_config_field(self, field):
        """Read one named-index configuration field."""
        return self.get_value(field)

    def set_config_field(self, field, value):
        """Write one named-index configuration field."""
        return self.set_value(field, value)

    def get_config(self):
        """Return all seven raw configuration bytes."""
        self.write_command(self.CMD_GET_CONFIG)
        return tuple(self.robust_i2c_readfrom(self.device_addr, self.CONFIG_CRC + 1))

    def config(self):
        """Return the complete configuration as a field-name dictionary."""
        raw = self.get_config()
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
        """Configure whether calibration is loaded during firmware startup."""
        return self.set_value(self.CONFIG_LOAD_CAL_STARTUP, 1 if calibrated else 0)

    def set_cal_duration(self, seconds):
        """Set the automatic calibration duration in seconds."""
        return self.set_value(self.CONFIG_CAL_DURATION, seconds)

    def set_shape_threshold_black(self, threshold):
        """Set the black threshold used by line-shape detection."""
        return self.set_value(self.CONFIG_SHAPE_THRESHOLD_BLACK, threshold)

    def set_threshold_shape(self, threshold):
        """Set the shape threshold; alias for :meth:`set_shape_threshold_black`."""
        return self.set_shape_threshold_black(threshold)

    def set_ir_emitter_startup(self, emitter=True):
        """Configure whether the IR emitter is enabled after startup."""
        return self.set_value(self.CONFIG_IR_POWER, 1 if emitter else 0)

    def save_config(self):
        """Save the current configuration to sensor EEPROM."""
        self.write_command(self.CMD_SAVE_CONFIG)

    def load_config(self):
        """Load configuration from sensor EEPROM and apply its emitter state."""
        self.write_command(self.CMD_LOAD_CONFIG)

    def uart_test(self):
        """Run the I2C-only UART loopback test and return ``1`` or ``0``."""
        self.write_command(self.CMD_UART_TEST)
        wait(50)
        return self.robust_i2c_readfrom(self.device_addr, 1)[0]

    def get_uid(self):
        """Return the sensor's 12-byte CH32V203 unique identifier."""
        self.write_command(self.CMD_GET_UID)
        return tuple(self.robust_i2c_readfrom(self.device_addr, 12))

    def uid_hex(self):
        """Return the sensor UID as a lowercase hexadecimal string."""
        return "".join("%02x" % value for value in self.get_uid())

"""uRemote transport for the LMS line sensor."""


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
        config = self.get_config()
        self.version = "{}.{}".format(config[self.CONFIG_MAJ_VERSION], config[self.CONFIG_MIN_VERSION])
        self.cal_duration = config[self.CONFIG_CAL_DURATION]

    def ping(self):
        """[pybricks:omit] Return the firmware millisecond counter."""
        return self.ur.call("ping")

    def get_version(self):
        """[pybricks:omit] Return firmware version as (major, minor)."""
        version = self.ur.call("get_version")
        return "{}.{}".format(version[0], version[1])

    def debug(self):
        """[pybricks:omit] Get debug values ( Uptime, mode, calibrated, emitter, LED mode, I2C overflow count)"""
        return self.ur.call("debug")

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

    def get_cal_min(self):
        """Return the 8 calibration minimum bytes."""
        return self._bytes_tuple(self.ur.call("get_cal_min"))

    def get_cal_max(self):
        """Return the 8 calibration maximum bytes."""
        return self._bytes_tuple(self.ur.call("get_cal_max"))

    def set_cal_min(self, values):
        """Set the 8 calibration minimum bytes."""
        self._require_sensor_count(values, "set_cal_min")
        return self.ur.call("set_cal_min", *values)

    def set_cal_max(self, values):
        """Set the 8 calibration maximum bytes."""
        self._require_sensor_count(values, "set_cal_max")
        return self.ur.call("set_cal_max", *values)

    def get_conf_value(self, index):
        """[pybricks:omit] Read one config byte by index."""
        return self.ur.call("get_conf_value", index)

    def set_conf_value(self, index, value):
        """[pybricks:omit] Write one config byte by index and save config."""
        return self.ur.call("set_conf_value", index, value)

    def get_config(self):
        """Return raw config bytes."""
        return self._bytes_tuple(self.ur.call("get_config"))

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

    def set_emitter(self, power):
        """Set the IR emitter off/on."""
        return self.ir_power(power)
    
    def get_uid(self):
        """Return 12 CH32V203 UID bytes."""
        return self._bytes_tuple(self.ur.call("get_uid"))
