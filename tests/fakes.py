"""Hardware fakes shared by the test suite.

Nothing here talks to real hardware. The pieces mirror the real stack:

    hub driver --UART wire--> LineSensorURServer --I2C--> FakeLineSensor

* ``Clock``           MicroPython ``ticks_ms``/``sleep_ms`` on a manual clock,
                      so timeout paths run instantly and deterministically.
* ``FakeUART``        One end of a byte wire. It quacks like MicroPython's
                      ``machine.UART``, Pybricks' ``UARTDevice`` and pyserial.
* ``FakeLineSensor``  The sensor firmware on the I2C bus, following the
                      command table in ``firmware/README.md``.
* ``Bench``           Owns the clock, the named UART endpoints and the sensor
                      for one test.
"""

import types

SENSOR_ADDRESS = 0x33

# Firmware command numbers (firmware/README.md, "I2C commands").
CMD_SET_MODE_RAW = 0
CMD_SET_MODE_CAL = 1
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
CMD_BLACKLINE = 23
CMD_GET_UID = 24


class Clock:
    """Manual millisecond clock; sleeping advances it."""

    def __init__(self):
        self.now = 0

    def ticks_ms(self):
        return self.now

    @staticmethod
    def ticks_diff(a, b):
        return a - b

    def sleep_ms(self, milliseconds):
        self.now += milliseconds

    def sleep(self, seconds):
        self.now += int(seconds * 1000)


class FakeUART:
    """One end of a byte wire, usable as UART, UARTDevice or serial port."""

    def __init__(self, name=""):
        self.name = name
        self.peer = None
        self.rx = bytearray()
        self.on_data = None  # called after bytes arrive on this end
        self.baudrate = None
        self.is_open = True
        self.init_kwargs = {}

    # -- MicroPython machine.UART / Pybricks UARTDevice -----------------
    def any(self):
        return len(self.rx)

    def waiting(self):
        return len(self.rx)

    @property
    def in_waiting(self):  # pyserial
        return len(self.rx)

    def read(self, count=None):
        if not self.rx:
            return None
        if count is None:
            count = len(self.rx)
        data = bytes(self.rx[:count])
        del self.rx[:count]
        return data

    def read_all(self):
        return self.read()

    def reset_input_buffer(self):  # pyserial
        self.rx.clear()

    def set_baudrate(self, baudrate):
        self.baudrate = baudrate

    def write(self, data):
        data = bytes(data)
        if self.peer is not None:
            self.peer.rx.extend(data)
            if self.peer.on_data is not None:
                self.peer.on_data()
        return len(data)

    def close(self):
        self.is_open = False

    # -- test helpers ----------------------------------------------------
    def take(self):
        """Return and clear everything received so far."""
        data = bytes(self.rx)
        self.rx.clear()
        return data


class FakeLineSensor:
    """Sensor firmware as seen over I2C (``writeto`` / ``readfrom``).

    Commands act immediately. Commands with a reply stage it for the next
    ``readfrom``; every other read returns the normal 13-byte packet.
    """

    FIRMWARE_VERSION = (5, 6)
    UID = bytes(range(0xA0, 0xAC))

    def __init__(self, address=SENSOR_ADDRESS):
        self.address = address
        self.log = []  # (command, args) for every command written
        self.reply = None
        self.read_failures = 0
        self.write_failures = 0

        self.mode = CMD_SET_MODE_CAL
        self.black_line = True
        self.emitter = False
        self.leds_mode = 0
        self.neopixels = {}
        self.calibrating = False
        self.calibrate_save = False
        self.calibrated = False
        self.cal_min = [0] * 8
        self.cal_max = [255] * 8
        self.stored_cal = ([0] * 8, [255] * 8)
        self.uart_test_result = 1

        major, minor = self.FIRMWARE_VERSION
        self.config = [major, minor, 1, 5, 128, 1, 0]
        self.config[6] = self._crc()

        # Readings *before* firmware polarity handling.
        self.values = [10, 20, 30, 40, 50, 60, 70, 80]
        self.position_byte = 128
        self.minimum = 10
        self.maximum = 80
        self.derivative_byte = 128
        self.shape = " "

    # -- readings ----------------------------------------------------------
    def _crc(self):
        crc = 0
        for value in self.config[:6]:
            crc ^= value
        return crc

    def set_reading(self, values=None, position=None, derivative=None, shape=None):
        """Set what the sensor reports; position/derivative are signed."""
        if values is not None:
            assert len(values) == 8
            self.values = list(values)
        if position is not None:
            self.position_byte = position + 128
        if derivative is not None:
            self.derivative_byte = derivative + 128
        if shape is not None:
            self.shape = shape

    def packet(self):
        """The 13-byte sensor packet, with line polarity applied."""
        values = self.values if self.black_line else [255 - v for v in self.values]
        return bytes(
            values
            + [
                self.position_byte,
                self.minimum,
                self.maximum,
                self.derivative_byte,
                ord(self.shape),
            ]
        )

    # -- calibration -------------------------------------------------------
    def finish_calibration(self):
        """Simulate the firmware calibration timer expiring."""
        assert self.calibrating, "calibration was not started"
        self.calibrating = False
        self.calibrated = True
        if self.calibrate_save:
            self.stored_cal = (list(self.cal_min), list(self.cal_max))

    # -- I2C bus -------------------------------------------------------------
    def writeto(self, address, payload):
        if address != self.address:
            raise OSError(19, "ENODEV")
        if self.write_failures:
            self.write_failures -= 1
            raise OSError(5, "EIO")
        payload = bytes(payload)
        command, args = payload[0], payload[1:]
        self.log.append((command, args))
        self.reply = None
        self._execute(command, args)
        return len(payload)

    def readfrom(self, address, count):
        if address != self.address:
            raise OSError(19, "ENODEV")
        if self.read_failures:
            self.read_failures -= 1
            raise OSError(5, "EIO")
        if self.reply is not None:
            data, self.reply = self.reply, None
        else:
            data = self.packet()
        return bytes(data[:count])

    def commands(self, *numbers):
        """Logged commands, optionally filtered to the given numbers."""
        if not numbers:
            return list(self.log)
        return [entry for entry in self.log if entry[0] in numbers]

    def _execute(self, command, args):
        if command in (CMD_SET_MODE_RAW, CMD_SET_MODE_CAL):
            self.mode = command
        elif command == CMD_GET_VERSION:
            self.reply = bytes(self.FIRMWARE_VERSION)
        elif command == CMD_CALIBRATE:
            self.calibrating = True
            self.calibrate_save = bool(args and args[0])
            self.mode = 3
        elif command == CMD_IS_CALIBRATED:
            self.reply = bytes([1 if self.calibrated else 0])
        elif command == CMD_LOAD_CAL:
            self.cal_min, self.cal_max = (list(x) for x in self.stored_cal)
            self.calibrated = True
        elif command == CMD_SAVE_CAL:
            self.stored_cal = (list(self.cal_min), list(self.cal_max))
        elif command == CMD_GET_CAL_MIN:
            self.reply = bytes(self.cal_min)
        elif command == CMD_GET_CAL_MAX:
            self.reply = bytes(self.cal_max)
        elif command == CMD_SET_CAL_MIN:
            self.cal_min = list(args[:8])
        elif command == CMD_SET_CAL_MAX:
            self.cal_max = list(args[:8])
        elif command == CMD_NEOPIXEL:
            index, red, green, blue = args[:4]
            self.neopixels[index] = (red, green, blue)
        elif command == CMD_LEDS:
            self.leds_mode = args[0]
        elif command == CMD_SET_EMITTER:
            self.emitter = bool(args[0])
        elif command == CMD_GET_CONF_VALUE:
            index = args[0]
            self.reply = bytes([self.config[index] if index < 7 else 0])
        elif command == CMD_SET_CONF_VALUE:
            index, value = args[:2]
            if index < 7:
                self.config[index] = value
                self.config[6] = self._crc()
        elif command == CMD_GET_CONFIG:
            self.reply = bytes(self.config)
        elif command == CMD_LOAD_CONFIG:
            self.emitter = bool(self.config[5])
        elif command == CMD_UART_TEST:
            self.reply = bytes([self.uart_test_result])
        elif command == CMD_BLACKLINE:
            self.black_line = bool(args[0])
        elif command == CMD_GET_UID:
            self.reply = self.UID
        # CMD_DEBUG and the legacy commands 20/21 are accepted and ignored.


class FakeI2CBus:
    """``machine.I2C`` stand-in that forwards to a FakeLineSensor."""

    def __init__(self, sensor, i2c_id, scl, sda, freq):
        self.sensor = sensor
        self.i2c_id = i2c_id
        self.scl = scl
        self.sda = sda
        self.freq = freq

    def writeto(self, address, payload):
        return self.sensor.writeto(address, payload)

    def readfrom(self, address, count):
        return self.sensor.readfrom(address, count)


class Bench:
    """Everything one test needs: clock, wires and a simulated sensor."""

    current = None

    def __init__(self):
        self.clock = Clock()
        self.sensor = FakeLineSensor()
        self.endpoints = {}
        self.i2c_buses = []

    # -- wires ----------------------------------------------------------
    def endpoint(self, name):
        if name not in self.endpoints:
            self.endpoints[name] = FakeUART(name)
        return self.endpoints[name]

    def link(self, name_a, name_b):
        a, b = self.endpoint(name_a), self.endpoint(name_b)
        a.peer, b.peer = b, a
        return a, b

    # -- machine module ---------------------------------------------------
    def make_i2c(self, i2c_id=0, scl=None, sda=None, freq=400000):
        bus = FakeI2CBus(self.sensor, i2c_id, scl, sda, freq)
        self.i2c_buses.append(bus)
        return bus

    def make_uart(self, uart_id, **kwargs):
        uart = self.endpoint("uart%s" % uart_id)
        uart.init_kwargs = kwargs
        return uart

    def make_uart_device(self, port, timeout=None, power_pin=None):
        uart = self.endpoint("port%s" % port)
        uart.init_kwargs = {"timeout": timeout, "power_pin": power_pin}
        return uart


def build_machine_module():
    """A ``machine`` module that creates fakes on the current Bench."""
    module = types.ModuleType("machine")
    module.Pin = lambda number, *args, **kwargs: number
    module.I2C = lambda i2c_id=0, **kwargs: Bench.current.make_i2c(
        i2c_id,
        kwargs.get("scl"),
        kwargs.get("sda"),
        kwargs.get("freq", 400000),
    )
    module.UART = lambda uart_id, **kwargs: Bench.current.make_uart(uart_id, **kwargs)
    return module


def build_pybricks_modules():
    """Fake ``pybricks`` package: UARTDevice, Port, StopWatch, wait, run_task."""
    package = types.ModuleType("pybricks")
    package.__path__ = []

    iodevices = types.ModuleType("pybricks.iodevices")
    iodevices.UARTDevice = lambda port, timeout=1000, power_pin=None: (
        Bench.current.make_uart_device(port, timeout, power_pin)
    )

    parameters = types.ModuleType("pybricks.parameters")

    class Port:
        A = "A"
        B = "B"
        C = "C"
        D = "D"
        E = "E"
        F = "F"

    parameters.Port = Port

    tools = types.ModuleType("pybricks.tools")

    class StopWatch:
        def time(self):
            return Bench.current.clock.now

    tools.StopWatch = StopWatch
    tools.wait = lambda milliseconds: Bench.current.clock.sleep_ms(milliseconds)
    tools.run_task = lambda: False

    package.iodevices = iodevices
    package.parameters = parameters
    package.tools = tools
    return {
        "pybricks": package,
        "pybricks.iodevices": iodevices,
        "pybricks.parameters": parameters,
        "pybricks.tools": tools,
    }


# -- protocol reference ----------------------------------------------------
# An independent, minimal encoder used to build and check wire frames, so the
# implementations under test are not validated against themselves.

PREAMBLE = b"<$MU"


def encode_payload(status, command, *arguments):
    name = command.encode("utf-8")
    out = bytes([(status << 5) | len(name)]) + name
    for argument in arguments:
        if isinstance(argument, bool):
            out += bytes([ord("B"), 1, int(argument)])
        elif isinstance(argument, int):
            text = str(argument).encode()
            out += bytes([ord("N"), len(text)]) + text
        elif isinstance(argument, (bytes, bytearray)):
            out += bytes([ord("A"), len(argument)]) + bytes(argument)
        elif isinstance(argument, str):
            text = argument.encode("utf-8")
            out += bytes([ord("S"), len(text)]) + text
        else:
            raise TypeError(type(argument))
    return out


def frame(status, command, *arguments):
    """A complete wire frame: length byte, preamble, payload."""
    body = PREAMBLE + encode_payload(status, command, *arguments)
    return bytes([len(body)]) + body
