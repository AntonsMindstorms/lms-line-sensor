# MicroPython code

## `line_sensor.py`

This is the generic library for the line sensor. It supports both the I2C and uRemote protocols.

Install this library on the LMS-ESP32 when connecting the LMS Line Sensor via I2C.

Use the following example to test the sensor:

```python

from line_sensor import LineSensorI2C

line = LineSensorI2C()

# Start calibrating the sensor.
# The blue LED flashes during calibration.
# Move the sensor back and forth over a black line.
line.calibrate()
line.set_emitter(True)
line.leds(1)

while True:
   print(line.sensors())

```



## `line_sensor_pybricks.py`



This is the library to use with Pybricks.
Download this library into your Pybricks environment. Do not edit it directly, because it is generated from `line\_sensor.py`.
The following example can be run on a Pybricks hub. It assumes that the line sensor has already been calibrated.

```python

from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor, ColorSensor, UltrasonicSensor, ForceSensor
from pybricks.parameters import Button, Color, Direction, Port, Side, Stop
from pybricks.robotics import DriveBase
from pybricks.tools import wait, StopWatch

hub = PrimeHub()
from line_sensor_pybricks import LineSensorUR

line = LineSensorUR(Port.C)

ur = line.ur


line.ir_power(True)
line.load_calibration()
line.mode_calibrated()

while True:

   vals = line.read\_all()
   print(vals\[:8], vals\[8], chr(vals\[12]))
```



## `line_sensor_i2c_uremote_bridge.py`



This is a library that runs on the LMS-ESP32 and acts as a bridge between Pybricks/uRemote and the line sensor.

The connection is:

```text

Pybricks hub -- UART/uRemote --> LMS-ESP32 -- I2C/Qwiic --> Line Sensor

```

On the Pybricks side, you can use the same `LineSensorUR` client that is used when connecting the line sensor directly to a hub.

The bridge exposes the native line-sensor uRemote command names and forwards them to `LineSensorI2C`.

It also allows you to define additional functions on the LMS-ESP32 that can be called remotely from Pybricks.

Below are example programs for both the LMS-ESP32 and Pybricks.



### On the LMS-ESP32



```python

from line_sensor_i2c_uremote_bridge import LineSensorI2CuRemoteBridge

from uremote import uRemote
b = LineSensorI2CuRemoteBridge()

def multiply(a, b):
    return a \* b

while True:
    b.process()
```

In this example, the `multiply()` function can be called remotely, just like the line sensor's built-in uRemote commands.



### On Pybricks



```python

from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor, ColorSensor, UltrasonicSensor, ForceSensor
from pybricks.parameters import Button, Color, Direction, Port, Side, Stop
from pybricks.robotics import DriveBase
from pybricks.tools import wait, StopWatch

hub = PrimeHub()

from line_sensor_pybricks import LineSensorUR

line = LineSensorUR(Port.C)

# define uRemote for other remote functions
ur = line.ur

line.ir_power(True)
line.load_calibration()
line.mode_calibrated()

i = 0
while True:
   i += 1
   if i > 1000:
       i = 0
   vals = line.read\_all()
   print(vals\[:8], vals\[8], chr(vals\[12]))
   # Call the remote function on the LMS-ESP32.
   print(ur.call('multiply', i, 4 \* i))
```



