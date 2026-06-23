# SPIKE Prime RoboCup Line Follower (LMS-ESP32 + Pybricks)

![Line Sensor 1.0 with LMS-ESP32 and SPIKE Prime](https://www.antonsmindstorms.com/wp-content/uploads/2026/06/20260623_125209-1280x721.jpg)

Full walkthrough: [8-Channel Line Follower on SPIKE Prime: LMS-ESP32 + Pybricks](https://www.antonsmindstorms.com/2026/06/23/line-sensor-lms-esp32-spike-prime-pybricks/)

This example runs a PD line follower on SPIKE Prime with Pybricks. The 8-channel line sensor connects to an LMS-ESP32 board over Qwiic; the board bridges I2C to the hub with [PUPRemote](https://docs.pybricks.com/en/latest/pupremote/index.html). The sensor publishes position, derivative, and track shape every loop; the hub steers two motors and handles calibration.

Tested on RoboCup tiles — sharp turns and junction shapes stress-test the onboard shape detection.

## Files

| File | Runs on | Purpose |
| ---- | ------- | ------- |
| [`lms_esp32_main.py`](lms_esp32_main.py) | LMS-ESP32 | Read the line sensor over I2C and expose `lines` + `calib` via PUPRemote. Save as `main.py` on the board. |
| [`line_follower_pybricks.py`](line_follower_pybricks.py) | SPIKE Prime | PD line follower with countdown, follow, and calibrate modes. |

## Hardware

- SPIKE Prime hub with Pybricks firmware
- Differential-drive robot (motors on ports **E** and **F** in the example)
- LMS-ESP32 board flashed with MicroPython
- 8-channel line tracking sensor
- Qwiic cable (sensor → LMS-ESP32)
- LPUP flat cable (LMS-ESP32 → SPIKE port **C**)

## Setup

### LMS-ESP32

Copy to the board with [ViperIDE](https://viper-ide.org/):

1. [`pupremote.py`](https://docs.pybricks.com/en/latest/pupremote/index.html) — PUPRemote sensor library
2. [`line_sensor.py`](../../micropython/line_sensor.py) — line sensor driver from this repo
3. [`lms_esp32_main.py`](lms_esp32_main.py) — save as `main.py`

Run `main.py`. The board powers the IR LEDs, loads saved calibration from flash, and streams line data to the hub.

### SPIKE Prime

Copy to the hub:

1. [`pupremote_hub.py`](https://docs.pybricks.com/en/latest/pupremote/index.html) — PUPRemote hub library
2. [`line_follower_pybricks.py`](line_follower_pybricks.py)

## Usage

1. **Countdown** — three seconds on the hub display before driving.
2. **Follow** — read `pos`, `der`, and `shape`; steer with a PD controller.
3. **Calibrate** — press the **left** hub button. Move the sensor over black and white surfaces during the flashing `+` / `x` countdown, then let it save.

On the hub, one PUPRemote call returns everything needed for steering:

```python
pos, der, shape = pr.call('lines')
```

Tune `FACTOR`, `KP`, `KD`, and `D_BRAKE` in `line_follower_pybricks.py`. Start with `FACTOR = 1` and increase in steps of `0.1` once tracking is stable. For tuning theory, see [The Surprising PID Line Follower Guide](https://www.antonsmindstorms.com/2026/04/22/pid-line-follower-ev3-spike-prime-v2/).

## PUPRemote channel

Both sides must use the same format:

```python
pr.add_channel('lines', 'bbB')  # position (signed byte), derivative (signed byte), shape (byte)
pr.add_command('calib', from_hub_fmt='b')
```

Shape values are ASCII characters: `|` straight, `<` / `>` turns, `Y` split, `T` junction, or space when no line is detected.
