# LMS-ESP32 uRemote server (I2C line sensor)

Pybricks hub talks uRemote to an LMS-ESP32; the ESP32 talks I2C/Qwiic to the line sensor.

```text
Pybricks hub -- UART/uRemote --> LMS-ESP32 -- I2C/Qwiic --> Line Sensor
```

Use this when the sensor is on Qwiic and you still want the same `LineSensorUR` client API on the hub. For a direct hub↔sensor UART cable, see [`../spike-direct/`](../spike-direct/) instead.

## Files

| File | Runs on | Purpose |
| --- | --- | --- |
| [`esp32_main.py`](esp32_main.py) | LMS-ESP32 | `LineSensorURServer` loop (+ optional custom remote functions) |
| [`hub_main.py`](hub_main.py) | Pybricks hub | `LineSensorUR` client |
| [`line_sensor_ur_server.py`](../../micropython/line_sensor_ur_server.py) | LMS-ESP32 | Server module (copy onto the board) |
| [`line_sensor.py`](../../micropython/line_sensor.py) | LMS-ESP32 | I2C driver (often pre-installed) |
| [`line_sensor_pybricks.py`](../../micropython/line_sensor_pybricks.py) | Hub | Client bundle |

`uremote` is frozen on current LMS-ESP32 firmware — do not copy `uremote.py` to the ESP32.

## Setup

### LMS-ESP32

1. Wire the line sensor to the ESP32 Qwiic/I2C port (defaults: SCL pin 4, SDA pin 5, address `0x33`).
2. Wire the hub UART to the ESP32 UART used by uRemote (LMS-ESP32 defaults).
3. With [ViperIDE](https://viper-ide.org/), copy `line_sensor.py` (if needed) and `line_sensor_ur_server.py`.
4. Run [`esp32_main.py`](esp32_main.py) (or save it as `main.py`).

### Pybricks hub

1. Upload [`line_sensor_pybricks.py`](../../micropython/line_sensor_pybricks.py).
2. Run [`hub_main.py`](hub_main.py). Change `Port.B` if your cable is on another port.

## Notes

- Hub and ESP32 must agree on baud rate **115200**.
- Custom functions defined in the ESP32 main program (for example `multiply`) are callable with `line.ur.call("multiply", …)` as long as they do not collide with native sensor command names.
- For a full RoboCup-style follower that uses PUPRemote instead of this server, see [`../spike-robocup/`](../spike-robocup/).
