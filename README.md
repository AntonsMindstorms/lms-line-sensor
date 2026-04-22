<div align="center">
<img alt="lms line sensor logo" src="https://raw.githubusercontent.com/antonsmindstorms/lms-line-sensor/master/docs/lms-line-sensor.png" width="200">

# LMS Line Sensor

`lms-line-sensor` is a MicroPython and Pybricks driver for the [LMS Line Sensor](https://www.antonsmindstorms.com/product/8-channel-line-sensor-for-lego-spike-and-mindstorms/) board. It provides two implementations: `LineSensorI2C` for direct I2C access on MicroPython devices, and `LineSensorUR` for remote access via Pybricks/uRemote. Both expose a unified API.

</div>

## Features

- Reads 8 light sensor channels in a single transfer.
- Exposes position, derivative, and line shape via normalized API.
- Supports raw and calibrated sensor modes.
- Calibration management with EEPROM persistence.
- IR emitter and RGB LED control.
- Aimed at ESP32 ([LMS-ESP32](https://www.antonsmindstorms.com/product/powerful-lms-esp32-board-for-spike-and-mindstorms/))

## Installation

### MicroPython on LMS-ESP32

On the newest LMS-ESP32 firmware, the line sensor driver is pre-installed.

If you are on older firmware, install it with vipe-ide:

1. Open vipe-ide.
2. Open the package manager.
3. Choose custom package.
4. Paste the Git repository link: `https://github.com/antonsmindstorms/lms-line-sensor.git`.
5. Install to the board.

### Pybricks Installation

Upload both `line_sensor.py` and `uremote.py` into your Pybricks project/environment.

### MicroBlocks Installation

Open a [microblocks editor](https://microblocks.fun/run/microblocks.html) and drag [LMS Line Sensor](<microblocks/LMS Line Sensor.ubl>) into the browser window.

PyPI/pip installation is not part of the normal deployment flow for this project.

## Quick Start

### MicroPython via I2C

```python
from time import sleep
from line_sensor import LineSensorI2C

sensor = LineSensorI2C(scl_pin=4, sda_pin=5, device_addr=51)

sensor.ir_power(True)
sensor.load_calibration()
sensor.mode_calibrated()

while True:
    position = sensor.position()
    derivative = sensor.derivative()
    pds = sensor.position_derivative_shape()
    print(position, derivative)
    print(pds)
    sleep(0.1)
```

### Pybricks via uRemote

```python
from line_sensor import LineSensorUR

sensor = LineSensorUR(port=1)

sensor.ir_power(True)
sensor.load_calibration()
sensor.mode_calibrated()

while True:
    position = sensor.position()
    derivative = sensor.derivative()
    pds = sensor.position_derivative_shape()
    print(position, derivative)
    print(pds)
```

### MicroBlocks

Here's a simple program that reads the line shape and distance from center.
Shape is an ASCII character in the shape of the line:

```ascii
SHAPE_NONE     = ' ',
SHAPE_STRAIGHT = '|',
SHAPE_T        = 'T',
SHAPE_L_LEFT   = '<',
SHAPE_L_RIGHT  = '>',
SHAPE_Y        = 'Y'
```

![Microblocks example](docs/line-sensor-microblocks.png)

## API Overview

Both `LineSensorI2C` and `LineSensorUR` expose the same core API:

- `position()` returns the current line position (-128 to 127, where 0 is center).
- `derivative()` returns the derivative of the line position.
- `shape()` returns the sensor-reported shape as an ASCII character.
- `sensors()` returns the 8 raw or calibrated sensor values.
- `position_derivative_shape()` returns a tuple of (position, derivative, shape).
- `data(*indices)` returns the full 13-byte response or selected entries by index constant.
- `mode_raw()` switches to raw reading mode.
- `mode_calibrated()` switches to calibrated reading mode.
- `calibrate(duration=5)` calibrates the sensor and saves calibration to EEPROM.
- `ir_power(True/False)` controls the IR emitter.
- `leds(mode)` changes the LED display mode.
- `save_calibration()` stores calibration data in EEPROM.
- `load_calibration()` loads calibration data from EEPROM.

### I2C-Specific Features

`LineSensorI2C` also provides:

- `position_derivative_shape()` returns a tuple of (position, derivative, shape).
- `check_line_type()` auto-detects black vs white line for value inversion.
- `start_calibration()` and `save_calibration()` for fine-grained calibration control.

## Documentation

You can read [the documentation on our API docs site](https://docs.antonsmindstorms.com/en/latest/Software/lms-line-sensor/docs/index.html) or build the Sphinx documentation from source in [docs](docs/). Build them with:

```bash
sphinx-build -b html docs docs/_build/html
```

## Development Notes

- Source module: `micropython/line_sensor.py`
- API docs entry point: `docs/index.rst`
- The Sphinx configuration mocks the MicroPython `machine` module so docs can be built on desktop Python.
- Submit update to PyPI:
  - Update version in [line sensor.py](micropython/line_sensor.py)
  - Update version in [package.json](package.json)
  - Activate venv
  - `rm -rf ./dist && python -m build && twine upload dist/*`
