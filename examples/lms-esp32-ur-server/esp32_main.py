"""LMS-ESP32: serve an I2C line sensor over uRemote.

Copy micropython/line_sensor.py (if needed) and
micropython/line_sensor_ur_server.py onto the board, then run this file.
uremote is frozen on current LMS-ESP32 firmware.
"""

from line_sensor_ur_server import LineSensorURServer

ls = LineSensorURServer()


def multiply(a, b):
    """Example app command callable from the hub via ur.call('multiply', ...)."""
    return a * b


while True:
    ls.process()
