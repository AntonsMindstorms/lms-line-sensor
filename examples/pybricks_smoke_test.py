"""Quick Pybricks smoke test for the LMS line sensor over uRemote.

Upload `micropython/line_sensor_pybricks.py` to your hub first, then run this
script from Pybricks Code. Connect the sensor UART to the hub port below.
"""

from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor, ColorSensor, UltrasonicSensor, ForceSensor
from pybricks.parameters import Button, Color, Direction, Port, Side, Stop
from pybricks.robotics import DriveBase
from pybricks.tools import wait, StopWatch

hub = PrimeHub()

# The bundled driver includes LineSensorUR and the uRemote client in one file.
from line_sensor_pybricks import LineSensorUR

# UART port wired to the sensor (change if yours is on another port).
ls = LineSensorUR(Port.B)

# Basic bring-up: IR on, raw readings, config, and LED mode.
ls.ir_power(True)
ls.mode_raw()
print(ls.get_config())
ls.leds(ls.LEDS_POSITION)

# Low-level uRemote call (same transport as ls.sensors(), etc.).
print(ls.ur.call("get_version"))
print(ls.ur.call("data"))
print(ls.version)

# High-level API: position (-128..127), derivative, and shape character.
for i in range(10):
    print(ls.data(ls.POSITION, ls.DERIVATIVE, ls.SHAPE))

# NeoPixel walk: firmware LED bar is off so we drive pixels directly.
ls.leds(ls.LEDS_OFF)
for i in range(8):
    wait(200)
    ls.neopixel(i, 0, 180, 0)

for i in range(8, -1, -1):
    wait(200)
    ls.neopixel(i, 0, 0, 0)
