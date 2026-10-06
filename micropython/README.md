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
line.ir_power(True)
line.leds(1)

while True:
   print(line.sensors())
```

## `line_sensor_pybricks.py`

This is the library to use with Pybricks.
Download this library into your Pybricks environment. Do not edit it directly, because it is generated from `line_sensor.py`.
The following example can be run on a Pybricks hub. It assumes that the line sensor has already been calibrated.

```python
from pybricks.hubs import PrimeHub
from pybricks.parameters import Port
from pybricks.tools import wait

hub = PrimeHub()
from line_sensor_pybricks import LineSensorUR

line = LineSensorUR(Port.C)

line.ir_power(True)
line.load_calibration()
line.mode_calibrated()

while True:
   vals = line.read_all()
   print(vals[:8], vals[8], chr(vals[12]))
   wait(100)
```

Inside `run_task()` / `multitask()`, every `LineSensorUR` method returns an
awaitable instead, so write `await line.read_all()`. The library detects this by
itself; there are no separate async methods.

## `line_sensor_ur_server.py`

This is a uRemote server that runs on the LMS-ESP32. It subclasses the frozen `uRemote` library and serves an I2C-connected line sensor.

The connection is:

```text
Pybricks hub -- UART/uRemote --> LMS-ESP32 -- I2C/Qwiic --> Line Sensor
```

On the Pybricks side, use the same `LineSensorUR` client as when connecting the line sensor directly to a hub.

The server exposes the native line-sensor uRemote command names and forwards them to `LineSensorI2C`. You can also define additional functions in your main program and call them remotely from Pybricks.

### On the LMS-ESP32

```python
from line_sensor_ur_server import LineSensorURServer

ls = LineSensorURServer()

def multiply(a, b):
    return a * b

while True:
    ls.process()
```

In this example, `multiply()` can be called remotely, just like the line sensor's built-in uRemote commands.

### On Pybricks

```python
from pybricks.hubs import PrimeHub
from pybricks.parameters import Port
from pybricks.tools import wait

hub = PrimeHub()

from line_sensor_pybricks import LineSensorUR

line = LineSensorUR(Port.C)
ur = line.ur

line.ir_power(True)
line.load_calibration()
line.mode_calibrated()

i = 0
while True:
   i += 1
   if i > 1000:
       i = 0
   vals = line.read_all()
   print(vals[:8], vals[8], chr(vals[12]))
   # Call the remote function on the LMS-ESP32.
   print(ur.call('multiply', i, 4 * i))
   wait(50)
```
