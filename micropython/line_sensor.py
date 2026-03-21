"""MicroPython driver for the LMS Line Sensor over I2C."""

from machine import I2C, Pin
from time import sleep, ticks_ms, ticks_diff
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
    MODE_SAVING = 2
    MODE_CALIBRATING = 3
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
    VALUES = -1
    VALUES_INVERTED = -2

    SHAPE_NONE = (" ",)
    SHAPE_STRAIGHT = ("|",)
    SHAPE_T = ("T",)
    SHAPE_L_LEFT = ("<",)
    SHAPE_L_RIGHT = (">",)
    SHAPE_Y = "Y"
    POSITION_WEIGHTS = (-127, -91, -54, -18, 18, 54, 91, 127)

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
        self.current_mode = self.last_mode = self.MODE_RAW
        self.current_rgb_mode = self.LEDS_OFF
        self.save_timeout = 0

    def position_and_shape(self):
        """
        Calculate the position locally using the light values, which may be more responsive than the position value from the sensor.
        """
        light_values = self.data(self.VALUES_INVERTED)

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

        if max_light * 4 < total:
            # This is equivalent to saying 
            # "if max light is less than 2 times the average light, 
            # then we are probably not on a line".
            # (avg=total/8, so 2*avg=total/4)
            self.pos_history.append((0, ticks_ms()))
            return 0, 0, " "

        # Calculate weighted sum directly in the -127..127 domain.
        weighted_sum = 0
        total_light = 0
        for i in range(8):
            light = light_values[i]
            adjusted = light - min_light
            weighted_sum += self.POSITION_WEIGHTS[i] * adjusted
            total_light += adjusted

        if total_light == 0:
            self.pos_history.append((0, ticks_ms()))
            return 0, 0, " "

        # This is a sign-safe integer step for: round(weighted_sum/total_light)
        # which keeps position estimates balanced left vs right and is 6x - 10x faster.
        if weighted_sum >= 0:
            pos = (weighted_sum + (total_light // 2)) // total_light
        else:
            pos = -((-weighted_sum + (total_light // 2)) // total_light)

        # Age is about 7ms per item in deque. -2 = 14ms ago.
        der = pos - self.pos_history[-2][0]  

        self.pos_history.append((pos, ticks_ms()))
        return pos, der, "|"

    def data(self, *indices):
        if self.current_mode < 2:
            # Try twice. Sometimes it fails. Firmware TODO.
            try:
                d = list(self.i2c.readfrom(self.device_addr, 13))
            except:
                d = list(self.i2c.readfrom(self.device_addr, 13))
        elif self.current_mode == self.MODE_SAVING: 
            if ticks_diff(ticks_ms(), self.save_timeout+1500) > 0:
                self.write_command(self.last_mode)
                self.current_mode = self.last_mode
                self.write_command(self.current_rgb_mode)
                print("done saving")
            d = [0]*13
        else:
            d = [0]*13

        if not indices:
            return d
        else:
            retval = []
            for idx in indices:
                if idx == self.VALUES:
                    retval += d[0:8]
                if idx == self.VALUES_INVERTED:
                    retval += [255-v for v in d[0:8]]
                else:
                    retval.append(d[idx])
            return retval

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
        self.current_mode = self.MODE_RAW
        self.write_command(self.MODE_RAW)

    def mode_calibrated(self):
        """Set sensor to calibrated mode."""
        self.current_mode = self.MODE_CALIBRATED
        self.write_command(self.MODE_CALIBRATED)

    def start_calibration(self):
        """Start sensor calibration."""
        self.last_mode = self.current_mode
        self.current_mode = self.MODE_CALIBRATING
        self.write_command((self.CMD_LEDS, self.LEDS_OFF))        
        self.write_command(self.CMD_CALIBRATE)

    def calibrate(self, duration=5, save=True):
        self.start_calibration()
        sleep(duration)
        self.stop_calibration(save=save)
        sleep(1)

    def ir_on(self):
        """Turn the IR emitter on."""
        self.write_command((self.CMD_SET_EMITTER, 1))

    def ir_off(self):
        """Turn the IR emitter off."""
        self.write_command((self.CMD_SET_EMITTER, 0))

    def rgb_mode(self, mode):
        """Set the onboard RGB LED mode."""
        self.current_rgb_mode = mode
        self.write_command((self.CMD_LEDS, mode))

    def stop_calibration(self, save=True):
        """Persist calibration values to the sensor EEPROM."""
        if save:
            self.write_command(self.CMD_SAVE_CAL)
            self.save_timeout = ticks_ms()
            self.current_mode = self.MODE_SAVING
        else:
            self.write_command(self.current_mode)
            self.write_command(self.current_rgb_mode)
            

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
