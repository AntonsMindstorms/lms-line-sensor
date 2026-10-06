<div align="center">
<img alt="lms line sensor logo" src="https://raw.githubusercontent.com/antonsmindstorms/lms-line-sensor/master/docs/lms-line-sensor.png" width="200">

# LMS Line Sensor

Drivers, firmware, and tools for the [LMS Line Sensor](https://www.antonsmindstorms.com/product/8-channel-line-sensor-for-lego-spike-and-mindstorms/) — an 8-channel reflectance board for LEGO SPIKE, Robot Inventor, Technic, and EV3 with Pybricks, MicroPython, or MicroBlocks.

</div>

## 1. Flash the sensor (firmware 5.6)

Current UF2: [`firmware/firmware_ch32_line_i2c_ur_v5.6.uf2`](firmware/firmware_ch32_line_i2c_ur_v5.6.uf2)

1. Connect the line sensor to your PC with USB.
2. Press **RESET** twice quickly until a **CH32V UF2** drive appears.
3. Drag the UF2 onto that drive and wait for it to disappear.
4. If the NeoPixels do not scan, unplug and replug USB.

Full hardware notes: [`firmware/README.md`](firmware/README.md).

## 2. Pick a connection path

| Goal | Path | Start here |
| --- | --- | --- |
| Configure / calibrate / watch values on a PC | USB → web dashboard | [linesensor.antonsmindstorms.com](https://linesensor.antonsmindstorms.com) or [`web/`](web/) |
| Script the sensor from a PC | USB → desktop Python | [`usb/`](usb/) |
| Hub wired straight to the sensor | UART uRemote → Pybricks | [`examples/spike-direct/`](examples/spike-direct/) |
| Sensor on Qwiic, hub talks to LMS-ESP32 | Hub → `LineSensorUR` → LMS-ESP32 `LineSensorURServer` → I2C | [`examples/lms-esp32-ur-server/`](examples/lms-esp32-ur-server/) |
| MicroPython on LMS-ESP32 only (no hub RPC) | I2C → `LineSensorI2C` | [`micropython/`](micropython/) |
| Blocks programming | MicroBlocks library | [`microblocks/`](microblocks/) |

### Approximate read timing (8 sensor values)

Measured cycle times for reading eight channels (indicative; wiring and hub load vary):

| Setup | ~cycle |
| --- | --- |
| LMS-ESP32 I2C @ 400 kHz | 1.3 ms |
| USB → PC (uRemote) | 1.5 ms |
| LMS-ESP32 I2C @ 100 kHz | 2.3 ms |
| EV3 UART (direct) | 4 ms (`sensors()` ~5.2 ms; that call reads 13 bytes) |
| SPIKE Prime UART (direct) | 8.2 ms |
| EV3 I2C | 10 ms |
| Prime ← LMS-ESP32 `LineSensorURServer` (uRemote) ← I2C | 14 ms |

**PUPRemote note:** Prime ← PUPRemote ← LMS-ESP32 I2C can look like ~2.5 ms per hub poll, while the ESP32 side takes ~5 ms to push a new sample. The hub therefore often re-reads the same values before they update.

Most of the I2C vs uRemote gap is framing overhead: uRemote sends about 33 bytes on the wire for 13 payload bytes; plain I2C and a PUPRemote `8B` channel do not add that framing.

## Installation

### Web dashboard

Open [linesensor.antonsmindstorms.com](https://linesensor.antonsmindstorms.com) in Chrome or Edge (Web Serial). Close any other app using the USB serial port first. See [`web/README.md`](web/README.md).

### USB desktop Python

```bash
cd usb
python -m pip install -r requirements.txt
python read_line_sensor.py
```

### Pybricks (direct UART or via LMS-ESP32)

Upload [`micropython/line_sensor_pybricks.py`](micropython/line_sensor_pybricks.py) into your Pybricks project.

### MicroPython on LMS-ESP32

On current LMS-ESP32 firmware the line sensor driver is often pre-installed. Otherwise install with [ViperIDE](https://viper-ide.org/):

1. Open ViperIDE → package manager → custom package.
2. Paste `https://github.com/antonsmindstorms/lms-line-sensor.git` and install.

For hub ↔ ESP32 ↔ I2C sensor, also copy [`micropython/line_sensor_ur_server.py`](micropython/line_sensor_ur_server.py) (`uremote` is frozen on current LMS-ESP32 firmware).

### MicroBlocks

Open the [MicroBlocks editor](https://microblocks.fun/run/microblocks.html) and drag [`microblocks/LMS Line Sensor.ubl`](microblocks/LMS%20Line%20Sensor.ubl) into the window.

## Quick start

### MicroPython via I2C (LMS-ESP32)

```python
from time import sleep
from line_sensor import LineSensorI2C

sensor = LineSensorI2C(scl_pin=4, sda_pin=5, device_addr=51)

sensor.ir_power(True)
sensor.load_calibration()
sensor.mode_calibrated()

while True:
    print(sensor.position(), sensor.derivative(), sensor.shape())
    sleep(0.1)
```

### Pybricks via uRemote (direct UART or `LineSensorURServer`)

```python
from pybricks.parameters import Port
from line_sensor_pybricks import LineSensorUR

sensor = LineSensorUR(Port.B)

sensor.ir_power(True)
sensor.load_calibration()
sensor.mode_calibrated()

while True:
    print(sensor.position(), sensor.derivative(), sensor.shape())
```

Inside `run_task()` / `multitask()` the same methods are awaitable. Put
`await` in front of every sensor call; nothing else changes:

```python
from pybricks.tools import multitask, run_task, wait

async def follow():
    while True:
        print(await sensor.position())
        await wait(10)

run_task(multitask(follow(), other_task()))
```

### MicroBlocks

Shape is an ASCII character:

```text
SHAPE_NONE     = ' '
SHAPE_STRAIGHT = '|'
SHAPE_T        = 'T'
SHAPE_L_LEFT   = '<'
SHAPE_L_RIGHT  = '>'
SHAPE_Y        = 'Y'
```

![Microblocks example](docs/line-sensor-microblocks.png)

## API overview

`LineSensorI2C` and `LineSensorUR` share one high-level API. Prefer these names in new code:

| Method | Meaning |
| --- | --- |
| `position()` | Line position (−128…127, 0 = center) |
| `derivative()` | Position derivative |
| `shape()` | Shape as an ASCII character |
| `sensors()` | Eight raw or calibrated values |
| `position_derivative_shape()` | `(position, derivative, shape)` |
| `data(*indices)` | Full packet or selected fields |
| `mode_raw()` / `mode_calibrated()` | Acquisition mode |
| `calibrate(duration=5)` | Calibrate and save to EEPROM |
| `ir_power(True/False)` | IR emitter |
| `leds(mode)` | Automatic NeoPixel mode |
| `save_calibration()` / `load_calibration()` | EEPROM calibration |

Aliases kept for compatibility (same behavior): `set_emitter` → `ir_power`, `rgb_mode` / `led_mode` → `leds`, `get_cal_min` / `get_cal_max` → `get_min` / `get_max`, and similar `set_cal_*` / `set_neopixel` forms.

`LineSensorI2C` also has `check_line_type()`, `start_calibration()`, and fine-grained calibration helpers.

`LineSensorURServer` (LMS-ESP32) subclasses frozen `uRemote` and exposes the native uRemote command names over UART while talking to the sensor on I2C.

## More examples

- [`examples/spike-direct/`](examples/spike-direct/) — SPIKE hub, direct UART
- [`examples/lms-esp32-ur-server/`](examples/lms-esp32-ur-server/) — hub + LMS-ESP32 + I2C sensor
- [`examples/spike-robocup/`](examples/spike-robocup/) — SPIKE + LMS-ESP32 with PUPRemote
- [`examples/ev3-robocup/`](examples/ev3-robocup/) — EV3 + LMS-ESP32
- [`examples/pybricks_smoke_test.py`](examples/pybricks_smoke_test.py) — quick UART bring-up

## Documentation

- Published docs: [docs.antonsmindstorms.com … lms-line-sensor](https://docs.antonsmindstorms.com/en/latest/Software/lms-line-sensor/docs/index.html)
- Firmware / registers / packets: [`firmware/README.md`](firmware/README.md) (canonical)
- Sphinx sources: [`docs/`](docs/)

```bash
sphinx-build -b html docs docs/_build/html
```

## Development notes

- Main MicroPython source: `micropython/line_sensor.py`
- Pybricks bundle: `tools/generate_line_sensor_pybricks.py` → `micropython/line_sensor_pybricks.py`
- uRemote is a git submodule at `micropython/vendor/uRemote`. Clone with
  `git clone --recurse-submodules`, or run `git submodule update --init` in an
  existing checkout. The bundle generator trims the Pybricks client from it.
- LMS-ESP32 uRemote server: `micropython/line_sensor_ur_server.py`
- Sphinx mocks the MicroPython `machine` module for desktop builds
- PyPI publish: bump version in `micropython/line_sensor.py` and `package.json`, then `rm -rf ./dist && python -m build && twine upload dist/*`
