"""MicroPython driver for the LMS Line Sensor over I2C."""

from machine import I2C, Pin
from time import sleep, ticks_ms
from collections import deque

__all__ = ["LineSensor"]
__version__ = "0.1.0"


class LineSensor:
    """
    MicroPython class for line following sensor via I2C.

    Reads 11 bytes:
    - Bytes 0-7: Light values from 8 sensors
    - Byte 8: Position
    - Byte 9: Min value
    - Byte 10: Max value
    """

    # Command constants
    MODE_RAW = 0
    MODE_CALIBRATED = 1
    CMD_GET_VERSION = 2
    CMD_DEBUG = 3
    CMD_CALIBRATE = 4
    CMD_IS_CALIBRATED = 5
    CMD_LOAD_CAL = 6  # load calibrated values frpom eeprom
    CMD_SAVE_CAL = 7  # save calibrated values to eeprom
    CMD_GET_MIN = 8
    CMD_GET_MAX = 9
    CMD_SET_MIN = 10
    CMD_SET_MAX = 11
    CMD_NEOPIXEL = 12  # neopixel: lednr, r, g, b, write
    CMD_LEDS = 13
    CMD_SET_EMITTER = 14  # optional for qtr sensors, 1 for on, 0 for zero.
    MAX_CMDS = 15

    # LED Modes
    LEDS_OFF = 0
    LEDS_NORMAL = 1
    LEDS_INVERTED = 2
    LEDS_POSITION = 3
    LEDS_MAX = 4

    POSITION = 8
    MIN = 9
    MAX = 10
    DERIVATIVE = 11
    SHAPE = 12

    SHAPE_NONE = (" ",)
    SHAPE_STRAIGHT = ("|",)
    SHAPE_T = ("T",)
    SHAPE_L_LEFT = ("<",)
    SHAPE_L_RIGHT = (">",)
    SHAPE_Y = "Y"

    def __init__(self, scl_pin=4, sda_pin=5, device_addr=51):
        """
        Initialize the line sensor.

        Args:
            scl_pin: SCL pin number (default 4)
            sda_pin: SDA pin number (default 5)
            device_addr: I2C device address (default 51)
        """
        self.device_addr = device_addr
        self.i2c = I2C(1, scl=Pin(scl_pin), sda=Pin(sda_pin))
        self.pos_history = deque([(0, 0)] * 5, 5)

    def light_values(self, inverted=False):
        """
        Read only the 8 light sensor values.
        """
        if inverted:
            return [255 - v for v in self.i2c.readfrom(self.device_addr, 8)]
        else:
            return list(self.i2c.readfrom(self.device_addr, 8))

    def position_and_shape(self):
        """
        Calculate the position locally using the light values, which may be more responsive than the position value from the sensor.
        """
        light_values = self.light_values(inverted=True)

        # Single pass: calculate min, max, sum
        min_light = light_values[0]
        max_light = light_values[0]
        total = 0
        for light in light_values:
            if light < min_light:
                min_light = light
            if light > max_light:
                max_light = light
            total += light

        average_light = total / 8
        if max_light < average_light * 2:
            self.pos_history.append((0, ticks_ms()))
            return 0, 0, " "

        # Calculate weighted sum
        weighted_sum = 0
        total_light = 0.000001
        for i, light in enumerate(light_values):
            adjusted = light - min_light
            weighted_sum += i * adjusted
            total_light += adjusted

        pos = round(((weighted_sum / total_light) - 3.5) / 7 * 255)
        der = pos - self.pos_history[-2][0]  # Age is about 7ms per item in deque.
        # print(ticks_ms() - self.pos_history[3][1])
        self.pos_history.append((pos, ticks_ms()))
        return pos, der, "|"

    def data(self, *indices):
        try:
            d = list(self.i2c.readfrom(self.device_addr, 13))
        except:
            d = list(self.i2c.readfrom(self.device_addr, 13))
        d[self.POSITION] -= 128
        d[self.DERIVATIVE] -= 128
        if len(indices) == 0:
            return d
        elif len(indices) == 1:
            return d[indices[0]]
        else:
            return [d[i] for i in indices]

    def position(self):
        """
        Read the position value.
        """
        return self.data(self.POSITION)

    def position_derivative(self):
        """
        Read the position derivative value.
        """
        return self.data(self.DERIVATIVE)

    def shape(self):
        """
        Read the shape value.
        """
        return self.data(self.SHAPE)

    def write_command(self, command):
        """
        Write a 1-byte command to the sensor.
        """
        if type(command) is int:
            command = [command]
        self.i2c.writeto(self.device_addr, bytes(command))

    def mode_raw(self):
        """Set sensor to raw mode."""
        self.write_command(self.MODE_RAW)

    def mode_calibrated(self):
        """Set sensor to calibrated mode."""
        self.write_command(self.MODE_CALIBRATED)

    def start_calibration(self):
        """Start sensor calibration."""
        self.write_command(self.CMD_CALIBRATE)

    def ir_on(self):
        """Turn the IR emitter on."""
        self.write_command((self.CMD_SET_EMITTER, 1))

    def ir_off(self):
        """Turn the IR emitter off."""
        self.write_command((self.CMD_SET_EMITTER, 0))

    def rgb_mode(self, mode):
        """Set the onboard RGB LED mode."""
        self.write_command((self.CMD_LEDS, mode))

    def save_calibration(self):
        """Persist calibration values to the sensor EEPROM."""
        self.write_command(self.CMD_SAVE_CAL)

    def load_calibration(self):
        """Load previously saved calibration values from EEPROM."""
        self.write_command(self.CMD_LOAD_CAL)


# Example usage:
if __name__ == "__main__":
    # Initialize sensor
    sensor = LineSensor()

    sensor.ir_on()

    # # # Optionally start calibration
    # sensor.rgb_mode(sensor.LEDS_INVERTED)
    # sensor.start_calibration()
    # sleep(5)
    # sensor.mode_calibrated()

    sensor.load_calibration()
    sensor.mode_calibrated()
    sensor.rgb_mode(sensor.LEDS_POSITION)

    # Read just light values
    for i in range(1000):
        pos = sensor.position()
        der = sensor.position_derivative()
        print("Pos:", pos, der)
        sleep(0.1)
