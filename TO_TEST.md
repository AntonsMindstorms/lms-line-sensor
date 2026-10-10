# Hardware checks still to do

The automated tests (`python -m pytest`) use a simulated sensor, so they cannot
prove how the real firmware, the frozen LMS-ESP32 `uremote` or a Pybricks hub
behave. These checks cover what they cannot. Tick them off as you go.

Already verified on hardware: `examples/ev3-robocup/p_controller_line_mower.py`
(`LineSensorI2C` with firmware 5.6).

## 1. Hub → LMS-ESP32 → I2C sensor

`examples/lms-esp32-ur-server/` — highest priority. `LineSensorURServer`
subclasses the frozen `uremote` in the LMS-ESP32 firmware and uses its internal
methods (`_waiting`, `_recv_command`, `_send_command`). The tests only ran it
against the vendored uRemote 1.3.

- [ ] `hub_main.py` against `esp32_main.py` reads position, shape and sensors.
- [ ] `blackline`, `leds` and `get_config` round-trip from the hub.
- [ ] A deliberate error (for example `leds(9)`) raises on the hub and the
      server keeps running.
- [ ] Read cycle time is in the range quoted in the README (about 14 ms).

## 2. Calibration over I2C

Affects `examples/spike-pup-test/`, `examples/spike-robocup/` and
`LineSensorI2C.calibrate()`. The I2C driver no longer switches the NeoPixels off
before calibrating and no longer restores the previous mode and LED mode
afterwards. `LineSensorUR.calibrate()` still switches them off.

- [ ] Calibrate with the example; the values look sane afterwards.
- [ ] Do the NeoPixels light up during calibration, and do they change the
      readings? If so, restore `leds(LEDS_OFF)` before `start_calibration()`.
- [ ] LED mode and sensor mode are as expected after calibrating.
- [ ] Power-cycle, run `load_calibration()`: the saved values are still there.
      (The examples call `start_calibration()` without `save` and then
      `save_calibration()` after about 5 s; this relies on the firmware keeping
      the limits once its own timer has expired.)

## 3. Line polarity (firmware 5.6)

The old library auto-detected polarity; that code is gone. Black line is the
power-up default and the setting is not stored in EEPROM.

- [ ] `blackline(False)` flips readings on a white line; `blackline(True)`
      flips them back.
- [ ] After a power cycle the sensor is back in black-line mode.
- [ ] MicroBlocks (`microblocks/LMS Line Sensor.ubl`): it has its own
      `line sensor invert` block and does not send the new command 23. Try a
      white line and check the result still makes sense with 5.6.

## 4. Pybricks bundle on a SPIKE hub

`micropython/line_sensor_pybricks.py` changed (`blackline`, `set_conf_value`,
`__version__`) and has not run on a real hub since.

- [ ] `examples/spike-direct/` runs (sensor on the hub UART).
- [ ] `examples/pybricks_smoke_test.py` passes.
- [ ] `sensor.set_cal_duration(7)` works (it used to raise `AttributeError`),
      and `get_configuration()` shows the new value.
- [ ] `from line_sensor_pybricks import *` imports without error.

## 5. Quick checks

- [ ] `python usb/read_line_sensor.py` works (the folder moved from
      `desktop_python_library/`).
- [ ] The web dashboard connects to a 5.6 sensor.
- [ ] Remaining examples run once: `ev3-robocup/pd_controller_line_mower.py`,
      `spike-pup-test/`, `spike-robocup/`.

## Known, not blocking

- `pyproject.toml` lists `line_sensor` as a package although it is a single
  module, so `python -m build` is probably broken. Only matters for a PyPI
  release.
- `LineSensorUR.version` is a string attribute (`"5.6"`) while
  `LineSensorI2C.version()` is a method returning `(5, 6)`.
- The MCU `uremote` encoders count characters, not bytes, for string
  arguments; non-ASCII text would produce a bad frame.
- `usb/read_line_sensor.py` shows position as `round(raw * 256/255 - 128)`; the
  library uses `raw - 128`.
- The server's `debug` command reports the emitter's startup config bit, not
  its live state (I2C has no readback).
