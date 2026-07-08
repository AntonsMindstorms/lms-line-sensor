"""MicroPython I2C backend for the LMS line sensor."""

from .base import BaseLineSensor


class LineSensorI2C(BaseLineSensor):
    """LMS Line Sensor via I2C (MicroPython)."""

    CMD_GET_VERSION = 2
    CMD_DEBUG = 3
    CMD_CALIBRATE = 4
    CMD_IS_CALIBRATED = 5
    CMD_LOAD_CAL = 6
    CMD_SAVE_CAL = 7
    CMD_GET_MIN = 8
    CMD_GET_MAX = 9
    CMD_SET_MIN = 10
    CMD_SET_MAX = 11
    CMD_NEOPIXEL = 12
    CMD_LEDS = 13
    CMD_SET_EMITTER = 14
    CMD_GET_VALUE = 15
    CMD_SET_VALUE = 16
    CMD_SHOW_CONFIG = 17
    CMD_LOAD_CONFIG = 18
    CMD_SAVE_CONFIG = 19
    CMD_GPIO_OUT = 20
    CMD_GPIO_IN = 21
    CMD_SERIAL_DISABLE = 22
    CMD_SERIAL_ENABLE = 23
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
        """Retry I2C reads a few times before failing."""
        return self._retry(lambda: self.i2c.readfrom(device_addr, raw_bytes))

    def _read_all(self):
        if self.current_mode < self.MODE_SAVING:
            return list(self.robust_i2c_readfrom(self.device_addr, self.RAW_BYTES))

        if self.current_mode == self.MODE_SAVING:
            if self.ticks_diff(self.ticks_ms(), self.save_start_time + 1500) > 0:
                self.write_command(self.last_mode)
                self.current_mode = self.last_mode
                print("Calibration stored in EEPROM")

        return [0] * self.RAW_BYTES

    def data(self, *indices):
        raw = self._read_all()
        return self._select_indices(raw, indices, invert_values=self.black_line)

    def write_command(self, command):
        """Write a one-byte or multi-byte command to the sensor."""
        if isinstance(command, int):
            payload = bytes([command])
        else:
            payload = bytes(command)
        self._retry(lambda: self.i2c.writeto(self.device_addr, payload))

    def mode_raw(self):
        self.current_mode = self.last_mode = self.MODE_RAW
        self.write_command(self.MODE_RAW)

    def mode_calibrated(self):
        self.current_mode = self.last_mode = self.MODE_CALIBRATED
        self.write_command(self.MODE_CALIBRATED)

    def start_calibration(self):
        print("Starting calibration")
        self.last_mode = self.current_mode
        self.current_mode = self.MODE_CALIBRATING
        self.write_command((self.CMD_LEDS, self.LEDS_OFF))
        self.write_command(self.CMD_CALIBRATE)

    def save_calibration(self):
        print("Stopping calibration and saving new values")
        self.write_command(self.MODE_CALIBRATED)
        self.write_command((self.CMD_LEDS, self.current_leds_mode))
        self.check_line_type()
        self.write_command(self.last_mode)
        self.write_command(self.CMD_SAVE_CAL)
        self.save_start_time = self.ticks_ms()
        self.current_mode = self.MODE_SAVING

    def check_line_type(self):
        """Check if the line is black or white after calibration."""
        values = list(self.robust_i2c_readfrom(self.device_addr, self.SENSOR_COUNT))
        average = sum(values) // len(values)
        self.black_line = average > 128
        print("Line is", "black" if self.black_line else "white")

    def calibrate(self, duration=5):
        self.start_calibration()
        self.sleep(duration)
        self.save_calibration()
        self.sleep(1.5)
        print("Calibration stored in EEPROM")
        self.current_mode = self.last_mode

    def ir_power(self, power):
        self.write_command((self.CMD_SET_EMITTER, 1 if power else 0))

    def leds(self, mode):
        self.current_leds_mode = mode
        self.write_command((self.CMD_LEDS, mode))

    def load_calibration(self):
        self.write_command(self.CMD_LOAD_CAL)

    def neopixel(self, led_nr, r, g, b):
        self.write_command((self.CMD_NEOPIXEL, led_nr, r, g, b))

    def set_neopixel(self, led_nr, r, g, b):
        self.neopixel(led_nr, r, g, b)

    def rgb_mode(self, mode):
        self.leds(mode)

    def led_mode(self, mode):
        self.leds(mode)

    def get_min(self):
        self.write_command(self.CMD_GET_MIN)
        return tuple(self.robust_i2c_readfrom(self.device_addr, self.SENSOR_COUNT))

    def get_max(self):
        self.write_command(self.CMD_GET_MAX)
        return tuple(self.robust_i2c_readfrom(self.device_addr, self.SENSOR_COUNT))

    def get_cal_min(self):
        return self.get_min()

    def get_cal_max(self):
        return self.get_max()

    def set_min(self, values):
        if len(values) != self.SENSOR_COUNT:
            raise ValueError("values must contain 8 items")
        self.write_command(tuple([self.CMD_SET_MIN] + [int(v) & 0xFF for v in values]))

    def set_max(self, values):
        if len(values) != self.SENSOR_COUNT:
            raise ValueError("values must contain 8 items")
        self.write_command(tuple([self.CMD_SET_MAX] + [int(v) & 0xFF for v in values]))

    def set_cal_min(self, values):
        self.set_min(values)

    def set_cal_max(self, values):
        self.set_max(values)

    def set_calibration(self, minimum, maximum):
        self.set_min(minimum)
        self.set_max(maximum)

    def version(self):
        self.write_command(self.CMD_GET_VERSION)
        return tuple(self.robust_i2c_readfrom(self.device_addr, 2))

    def set_debug(self, debug):
        self.write_command((self.CMD_DEBUG, debug))

    def debug(self, level):
        self.set_debug(level)
        return level

    def is_calibrated(self):
        self.write_command(self.CMD_IS_CALIBRATED)
        return bool(self.robust_i2c_readfrom(self.device_addr, 1)[0])

    def get_value(self, index):
        self.write_command((self.CMD_GET_VALUE, index))
        return self.robust_i2c_readfrom(self.device_addr, 1)[0]

    def set_value(self, index, value):
        self.write_command((self.CMD_SET_VALUE, index, value))
        return value

    def get_config_field(self, field):
        return self.get_value(field)

    def set_config_field(self, field, value):
        return self.set_value(field, value)

    def show_config(self):
        self.write_command(self.CMD_SHOW_CONFIG)
        return tuple(self.robust_i2c_readfrom(self.device_addr, self.CONFIG_CRC + 1))

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

    def set_threshold_shape(self, threshold):
        return self.set_shape_threshold_black(threshold)

    def set_ir_emitter_startup(self, emitter=True):
        return self.set_value(self.CONFIG_IR_POWER, 1 if emitter else 0)

    def save_config(self):
        self.write_command(self.CMD_SAVE_CONFIG)

    def load_config(self):
        self.write_command(self.CMD_LOAD_CONFIG)

    def gpio_out(self, pin, value):
        self.write_command((self.CMD_GPIO_OUT, pin, value))

    def gpio_in(self, pin):
        self.write_command((self.CMD_GPIO_IN, pin))
        return self.robust_i2c_readfrom(self.device_addr, 1)[0]

    def serial_disable(self):
        self.write_command(self.CMD_SERIAL_DISABLE)

    def serial_enable(self):
        self.write_command(self.CMD_SERIAL_ENABLE)

    def get_uid(self):
        self.write_command(self.CMD_GET_UID)
        return tuple(self.robust_i2c_readfrom(self.device_addr, 12))

    def uid_hex(self):
        return "".join("%02x" % value for value in self.get_uid())
