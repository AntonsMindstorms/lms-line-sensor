"""uRemote-to-I2C bridge for the LMS 8-channel line sensor.

Run this module on an LMS-ESP32 when the wiring is:

    Pybricks hub -- UART/uRemote --> LMS-ESP32 -- I2C/Qwiic --> line sensor

The Pybricks side can use the same ``LineSensorUR`` client that is used when
connecting the line sensor directly to a hub. The bridge exposes the native
line-sensor uRemote command names and forwards them to ``LineSensorI2C``.

Required files on the LMS-ESP32:

* ``line_sensor.py`` from the lms-line-sensor repository
* ``uremote.py`` from the uRemote repository
* this file

The current uRemote implementation resolves server functions in ``__main__``.
This bridge first dispatches its native line-sensor commands locally and then
falls back to functions defined in the main program. This allows one uRemote
connection to expose both the sensor API and application-specific commands.
Line-sensor commands take priority when an application function has the same
name.
"""

import __main__

try:
    from time import ticks_add, ticks_diff, ticks_ms, sleep_ms
except ImportError:  # CPython fallback for tests and documentation builds.
    import time as _time

    def ticks_ms():
        return int(_time.monotonic() * 1000)

    def ticks_add(value, delta):
        return value + delta

    def ticks_diff(value, reference):
        return value - reference

    def sleep_ms(milliseconds):
        _time.sleep(milliseconds / 1000.0)

from line_sensor import LineSensorI2C
from uremote import STATUS_ERR, STATUS_OK, uRemote

__version__ = "0.4.0"


class LineSensorI2CuRemoteBridge:
    """Expose the native line-sensor uRemote API through an I2C sensor.

    Args:
        sensor: Optional existing ``LineSensorI2C`` instance.
        remote: Optional existing ``uRemote`` server instance.
        i2c_id: MicroPython I2C controller number.
        scl_pin: LMS-ESP32 I2C clock pin.
        sda_pin: LMS-ESP32 I2C data pin.
        device_addr: Line-sensor I2C address. Default is ``0x33``.
        i2c_freq: I2C clock rate.
        uart_id: LMS-ESP32 UART number used by uRemote.
        baudrate: uRemote UART speed. Native line-sensor uRemote uses 115200.
        wait_recv: Overall uRemote receive timeout in milliseconds.
        uart_timeout: UART read timeout in milliseconds.
        rx: Optional UART RX pin override.
        tx: Optional UART TX pin override.
        calibration_grace_ms: Small delay added before ``cur_mode`` changes
            from calibrating back to the previous mode.
    """

    MODE_RAW = 0
    MODE_CALIBRATED = 1
    MODE_SAVING = 2
    MODE_CALIBRATING = 3

    SENSOR_COUNT = 8
    FRAME_SIZE = 13
    POSITION_INDEX = 8
    DERIVATIVE_INDEX = 11
    SHAPE_INDEX = 12
    CONFIG_SIZE = 7
    UID_SIZE = 12

    def __init__(
        self,
        sensor=None,
        remote=None,
        i2c_id=1,
        scl_pin=4,
        sda_pin=5,
        device_addr=0x33,
        i2c_freq=100000,
        uart_id=1,
        baudrate=115200,
        wait_recv=1000,
        uart_timeout=1000,
        rx=None,
        tx=None,
        calibration_grace_ms=50,
    ):
        if sensor is None:
            sensor = LineSensorI2C(
                i2c_id=i2c_id,
                scl_pin=scl_pin,
                sda_pin=sda_pin,
                device_addr=device_addr,
                freq=i2c_freq,
            )
        self.sensor = sensor

        if remote is None:
            remote_args = {
                "baudrate": baudrate,
                "wait_recv": wait_recv,
                "uart_timeout": uart_timeout,
            }
            # Do not pass None explicitly: uRemote then keeps the LMS-ESP32
            # defaults imported from lms_esp32.py.
            if rx is not None:
                remote_args["rx"] = rx
            if tx is not None:
                remote_args["tx"] = tx
            remote = uRemote(uart_id, **remote_args)
        self.remote = remote

        current_mode = getattr(sensor, "current_mode", self.MODE_CALIBRATED)
        if current_mode not in (self.MODE_RAW, self.MODE_CALIBRATED):
            current_mode = self.MODE_CALIBRATED
        self._mode = current_mode
        self._previous_mode = current_mode

        self._led_mode = getattr(sensor, "current_leds_mode", 0)
        self._previous_led_mode = self._led_mode
        try:
            self._emitter_state = 1 if sensor.get_value(sensor.CONFIG_IR_POWER) else 0
        except Exception:
            self._emitter_state = 0

        self._last_uart_command = "-"
        self._last_uart_parameters = ""
        self._last_uart_timestamp = 0
        self._last_i2c_command = "-"
        self._last_i2c_parameters = ""
        self._last_i2c_timestamp = 0

        self._calibrating = False
        self._calibration_deadline = 0
        self._calibration_grace_ms = max(0, int(calibration_grace_ms))

        self._handlers = {
            "ping": self.ping,
            "version": self.version,
            "get_version": self.version,
            "set_mode_raw": self.set_mode_raw,
            "set_mode_cal": self.set_mode_cal,
            "mode": self.mode,
            "cur_mode": self.cur_mode,
            "debug": self.debug,
            "debug_status": self.debug,
            "last_commands": self.last_commands,
            "calibrate": self.calibrate,
            "is_calibrated": self.is_calibrated,
            "save": self.save_cal,
            "save_cal": self.save_cal,
            "load": self.load_cal,
            "load_cal": self.load_cal,
            "data": self.data,
            "pos": self.pos,
            "shape": self.shape,
            "pds": self.pds,
            "pdr": self.pds,
            "all": self.all,
            "get_cal_min": self.get_cal_min,
            "get_cal_max": self.get_cal_max,
            "set_cal_min": self.set_cal_min,
            "set_cal_max": self.set_cal_max,
            "get_conf_value": self.get_conf_value,
            "set_conf_value": self.set_conf_value,
            "get_config": self.get_config,
            "load_config": self.load_config,
            "save_config": self.save_config,
            "set_emitter": self.set_emitter,
            "emitter": self.set_emitter,
            "leds": self.leds,
            "led": self.leds,
            "neopixel": self.neopixel,
            "get_uid": self.get_uid,
            "blackline": self.blackline,
            "print": self.print_value,
        }

    @staticmethod
    def _u8(value, name="value"):
        value = int(value)
        if value < 0 or value > 255:
            raise ValueError(name + " must be in range 0..255")
        return value

    def _eight_values(self, values, command_name):
        if len(values) == 1 and isinstance(values[0], (bytes, bytearray, list, tuple)):
            values = values[0]
        if len(values) != self.SENSOR_COUNT:
            raise ValueError(command_name + " needs 8 values")
        return tuple(self._u8(value, command_name) for value in values)

    def _read_frame(self):
        """Read one native 13-byte measurement frame directly over I2C."""
        raw = self.sensor.robust_i2c_readfrom(
            self.sensor.device_addr,
            getattr(self.sensor, "RAW_BYTES", self.FRAME_SIZE),
        )
        if len(raw) != self.FRAME_SIZE:
            raise OSError("line sensor returned {} bytes, expected 13".format(len(raw)))
        return bytes(raw)

    @staticmethod
    def _format_arguments(arguments):
        """Format parameters like the firmware's last_commands response."""
        formatted = []
        for value in arguments:
            if isinstance(value, (bytes, bytearray)):
                value = "[" + "".join("{:02X}".format(item) for item in value) + "]"
            elif isinstance(value, bool):
                value = "true" if value else "false"
            else:
                value = str(value)
            formatted.append(value)
        return ", ".join(formatted)[:64]

    def _record_uart(self, command, arguments):
        if command in ("debug", "debug_status", "last_commands"):
            return
        self._last_uart_command = command
        self._last_uart_parameters = self._format_arguments(arguments)
        self._last_uart_timestamp = ticks_ms()

    def _record_i2c(self, command, *arguments):
        self._last_i2c_command = command
        self._last_i2c_parameters = self._format_arguments(arguments)
        self._last_i2c_timestamp = ticks_ms()

    def _find_handler(self, command):
        """Find a sensor handler or an application function in main.py."""
        handler = self._handlers.get(command)
        if handler is not None:
            return handler

        handler = getattr(__main__, command, None)
        return handler if callable(handler) else None

    def _set_mode(self, new_mode):
        new_mode = int(new_mode)
        if new_mode == self.MODE_RAW:
            self._record_i2c("set_mode_raw")
            self.sensor.mode_raw()
        elif new_mode == self.MODE_CALIBRATED:
            self._record_i2c("set_mode_cal")
            self.sensor.mode_calibrated()
        else:
            # Native clients normally use only 0 and 1. Passing other values
            # to the I2C device would collide with I2C command identifiers.
            raise ValueError("mode must be 0 (raw) or 1 (calibrated)")

        self._calibrating = False
        self._mode = new_mode
        self._previous_mode = new_mode
        return new_mode

    def _service_state(self):
        if not self._calibrating:
            return
        if ticks_diff(ticks_ms(), self._calibration_deadline) < 0:
            return

        # The sensor firmware owns the calibration timer and restores its
        # previous mode and LED mode. Mirror that state locally for cur_mode().
        self._calibrating = False
        self._mode = self._previous_mode
        self._led_mode = self._previous_led_mode

        if hasattr(self.sensor, "current_mode"):
            self.sensor.current_mode = self._mode
        if hasattr(self.sensor, "last_mode"):
            self.sensor.last_mode = self._mode
        if hasattr(self.sensor, "current_leds_mode"):
            self.sensor.current_leds_mode = self._led_mode

        # LineSensorI2C uses this cached flag when interpreting line polarity.
        # Failure to refresh it must not break the UART service.
        try:
            self.sensor.check_line_type()
        except Exception:
            pass

    def dispatch(self, command, *arguments):
        """Execute one bridge command without using the UART transport."""
        self._service_state()
        self._record_uart(command, arguments)
        handler = self._find_handler(command)
        if handler is None:
            raise ValueError(command + "() function not found remotely")
        return handler(*arguments)

    def process(self):
        """Handle at most one uRemote request; call repeatedly in the main loop.

        Returns ``True`` when a request was handled and ``False`` when no UART
        request was waiting.
        """
        self._service_state()
        if not self.remote._waiting():
            return False

        status, command, data = self.remote._recv_command()
        if status != STATUS_OK or not command:
            return False

        if not isinstance(data, list):
            data = [data]

        self._record_uart(command, data)
        handler = self._find_handler(command)
        if handler is None:
            self.remote._send_command(
                command,
                command + "() function not found remotely",
                status=STATUS_ERR,
            )
            return True

        try:
            response = handler(*data)
        except Exception as error:
            self.remote._send_command(
                command,
                command + ": " + str(error),
                status=STATUS_ERR,
            )
            return True

        if response is None:
            response = ()
        elif not isinstance(response, tuple):
            response = (response,)

        self.remote._send_command(command, *response, status=STATUS_OK)
        self._service_state()
        return True

    def run_forever(self, idle_ms=0):
        """Run the bridge service loop forever."""
        idle_ms = max(0, int(idle_ms))
        while True:
            self.process()
            if idle_ms:
                sleep_ms(idle_ms)

    # ------------------------------------------------------------------
    # Native line-sensor uRemote command handlers.
    # ------------------------------------------------------------------

    def ping(self):
        return ticks_ms()

    def version(self):
        self._record_i2c("get_version")
        major, minor = self.sensor.version()
        return int(major), int(minor)

    def set_mode_raw(self):
        return self._set_mode(self.MODE_RAW)

    def set_mode_cal(self):
        return self._set_mode(self.MODE_CALIBRATED)

    def mode(self, new_mode=None):
        self._service_state()
        if new_mode is None:
            return self._mode
        return self._set_mode(new_mode)

    def cur_mode(self):
        self._service_state()
        return self._mode

    def debug(self, *_ignored):
        """Return the same six status values as firmware debug_status."""
        self._service_state()
        return (
            ticks_ms(),
            self._mode,
            1 if self.sensor.is_calibrated() else 0,
            self._emitter_state,
            self._led_mode,
            0,  # The bridge cannot read the firmware's I2C queue counter.
        )

    def last_commands(self):
        """Return the latest bridged UART and I2C commands and parameters."""
        return (
            self._last_uart_command,
            self._last_uart_parameters,
            self._last_uart_timestamp,
            self._last_i2c_command,
            self._last_i2c_parameters,
            self._last_i2c_timestamp,
        )

    def calibrate(self, save=0):
        save = 1 if save else 0

        if self._mode in (self.MODE_RAW, self.MODE_CALIBRATED):
            self._previous_mode = self._mode
        self._previous_led_mode = self._led_mode

        self._record_i2c("get_conf_value", self.sensor.CONFIG_CAL_DURATION)
        duration = int(self.sensor.get_value(self.sensor.CONFIG_CAL_DURATION))
        if duration < 0:
            duration = 0

        # Current I2C firmware accepts the same optional save flag as the
        # native uRemote firmware and performs the timed routine itself.
        self._record_i2c("calibrate", save)
        self.sensor.write_command((self.sensor.CMD_CALIBRATE, save))

        self._calibrating = True
        self._mode = self.MODE_CALIBRATING
        if hasattr(self.sensor, "current_mode"):
            self.sensor.current_mode = self.MODE_CALIBRATING

        delay = (duration * 1000) + self._calibration_grace_ms
        self._calibration_deadline = ticks_add(ticks_ms(), delay)
        return 1

    def is_calibrated(self):
        self._record_i2c("is_calibrated")
        return 1 if self.sensor.is_calibrated() else 0

    def save_cal(self):
        # Use the simple I2C command. LineSensorI2C.save_calibration() is a
        # higher-level helper intended for its older blocking calibration flow.
        self._record_i2c("save_cal")
        self.sensor.write_command(self.sensor.CMD_SAVE_CAL)
        return 1

    def load_cal(self):
        self._record_i2c("load_cal")
        self.sensor.load_calibration()
        return 1

    def data(self):
        return self._read_frame()[: self.SENSOR_COUNT]

    def pos(self):
        return self._read_frame()[self.POSITION_INDEX]

    def shape(self):
        return self._read_frame()[self.SHAPE_INDEX]

    def pds(self):
        frame = self._read_frame()
        return (
            frame[self.POSITION_INDEX],
            frame[self.DERIVATIVE_INDEX],
            frame[self.SHAPE_INDEX],
        )

    def all(self):
        return self._read_frame()

    def get_cal_min(self):
        self._record_i2c("get_cal_min")
        return bytes(self.sensor.get_cal_min())

    def get_cal_max(self):
        self._record_i2c("get_cal_max")
        return bytes(self.sensor.get_cal_max())

    def set_cal_min(self, *values):
        values = self._eight_values(values, "set_cal_min")
        self._record_i2c("set_cal_min", *values)
        self.sensor.set_cal_min(values)
        return 1

    def set_cal_max(self, *values):
        values = self._eight_values(values, "set_cal_max")
        self._record_i2c("set_cal_max", *values)
        self.sensor.set_cal_max(values)
        return 1

    def get_conf_value(self, index):
        index = int(index)
        if index < 0 or index >= self.CONFIG_SIZE:
            raise ValueError("config index must be in range 0..6")
        self._record_i2c("get_conf_value", index)
        return int(self.sensor.get_value(index))

    def set_conf_value(self, index, value):
        index = int(index)
        if index < 0 or index >= self.CONFIG_SIZE:
            raise ValueError("config index must be in range 0..6")
        value = self._u8(value, "config value")
        self._record_i2c("set_conf_value", index, value)
        self.sensor.set_value(index, value)
        return 1

    def get_config(self):
        self._record_i2c("get_config")
        raw = bytes(self.sensor.get_config())
        if len(raw) != self.CONFIG_SIZE:
            raise OSError(
                "line sensor returned {} config bytes, expected {}".format(
                    len(raw),
                    self.CONFIG_SIZE,
                )
            )
        return bytes(raw)

    def load_config(self):
        self._record_i2c("load_config")
        self.sensor.load_config()
        return 1

    def save_config(self):
        self._record_i2c("save_config")
        self.sensor.save_config()
        return 1

    def set_emitter(self, enabled):
        enabled = 1 if enabled else 0
        self._record_i2c("set_emitter", enabled)
        self.sensor.set_emitter(enabled)
        self._emitter_state = enabled
        return 1

    def leds(self, new_mode=None):
        if new_mode is None:
            return self._led_mode
        new_mode = self._u8(new_mode, "LED mode")
        if new_mode > 3:
            raise ValueError("LED mode must be in range 0..3")
        self._record_i2c("leds", new_mode)
        self.sensor.leds(new_mode)
        self._led_mode = new_mode
        return new_mode

    def neopixel(self, index, red, green, blue):
        index = self._u8(index, "NeoPixel index")
        if index >= self.SENSOR_COUNT + 1:
            raise ValueError("NeoPixel index must be in range 0..8")
        red = self._u8(red, "red")
        green = self._u8(green, "green")
        blue = self._u8(blue, "blue")
        self._record_i2c("neopixel", index, red, green, blue)
        self.sensor.neopixel(index, red, green, blue)
        return 1

    def get_uid(self):
        self._record_i2c("get_uid")
        raw = bytes(self.sensor.get_uid())
        if len(raw) != self.UID_SIZE:
            raise OSError(
                "line sensor returned {} UID bytes, expected {}".format(
                    len(raw),
                    self.UID_SIZE,
                )
            )
        return bytes(raw)

    def blackline(self):
        return 1 if getattr(self.sensor, "black_line", False) else 0

    @staticmethod
    def print_value(value):
        return value
