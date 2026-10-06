"""Pybricks hub: talk to LineSensorURServer on an LMS-ESP32.

Upload micropython/line_sensor_pybricks.py first. Wire hub UART to the ESP32
uRemote port (change Port.B if needed).
"""

from pybricks.hubs import PrimeHub
from pybricks.parameters import Port
from pybricks.tools import wait

from line_sensor_pybricks import LineSensorUR

hub = PrimeHub()
line = LineSensorUR(Port.B)
ur = line.ur

line.ir_power(True)
line.load_calibration()
line.mode_calibrated()

i = 0
while True:
    i += 1
    if i > 1000:
        i = 0
    print(line.position(), line.derivative(), line.shape())
    print(ur.call("multiply", i, 4 * i))
    wait(50)
