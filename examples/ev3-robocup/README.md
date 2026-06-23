# EV3 RoboCup Line Follower (LMS-ESP32 + Pybricks)

![PID line follower on LEGO EV3 with 8-channel line sensor](https://www.antonsmindstorms.com/wp-content/uploads/2026/04/20260422_164321_1-1280x720.jpg)

Full walkthrough: [PID Line Followers Made Surprisingly Simple for LEGO EV3 and SPIKE Prime](https://www.antonsmindstorms.com/2026/04/22/pid-line-follower-ev3-spike-prime/)

These examples run P and PD line followers on LEGO MINDSTORMS EV3 with Pybricks. The 8-channel line sensor connects to an LMS-ESP32 board over Qwiic; the board bridges I2C to the hub with [uRemote](https://github.com/AntonsMindstorms/uRemote). The sensor publishes position, derivative, and track shape every loop; the hub steers two drive motors.

Start with the P controller to feel how proportional steering works, then switch to the PD script to see sharper cornering on RoboCup tiles — the same progression described in the blog post.

## Files

| File | Runs on | Purpose |
| ---- | ------- | ------- |
| [`p_controller_line_mower.py`](p_controller_line_mower.py) | EV3 | P-only line follower — good first step for tuning `KP`. |
| [`pd_controller_line_mower.py`](pd_controller_line_mower.py) | EV3 | PD line follower — adds derivative for faster reactions on sharp turns. |

## Hardware

- EV3 brick with Pybricks firmware
- [EV3 Core Line Mower](https://www.antonsmindstorms.com/product/ev3-core-line-mower/) model (or similar differential-drive robot with motors on ports **B** and **C**)
- LMS-ESP32 board with current MicroPython firmware
- 8-channel line tracking sensor (v1.0)
- Qwiic cable (sensor → LMS-ESP32)
- LPUP flat cable (LMS-ESP32 → EV3 port **S1**)

## Setup

### LMS-ESP32

On the newest LMS-ESP32 firmware, the line sensor driver and [uRemote](https://github.com/AntonsMindstorms/uRemote) server are pre-installed. Flash or update the board with [ViperIDE](https://viper-ide.org/) if needed.

Power the board, connect the sensor, and run the default `main.py`. The board powers the IR LEDs, loads saved calibration from EEPROM, and streams line data to the hub.

### EV3

Copy to the hub:

1. [`uremote.py`](https://github.com/AntonsMindstorms/uRemote/blob/main/library/uremote.py) — [uRemote](https://github.com/AntonsMindstorms/uRemote) hub library
2. [`line_sensor.py`](../../micropython/line_sensor.py) — line sensor driver from this repo
3. [`p_controller_line_mower.py`](p_controller_line_mower.py) or [`pd_controller_line_mower.py`](pd_controller_line_mower.py)

Calibrate once before driving:

```python
ls.calibrate(duration=5)
```

Or load a previously saved calibration:

```python
ls.load_calibration()
ls.ir_power(True)
ls.mode_calibrated()
```

## Usage

Both scripts follow the same loop:

1. Read `pos` and `shape` (P) or `pos`, `der`, and `shape` (PD).
2. Stop both motors when no line is detected (`shape` is a space).
3. Otherwise steer with `KP` (and `KD` in the PD script) and drive forward at `BASE_DC`.

P controller:

```python
pos, shape = ls.data(ls.POSITION, ls.SHAPE)
steer = pos * KP
```

PD controller:

```python
pos, der, shape = ls.data(ls.POSITION, ls.DERIVATIVE, ls.SHAPE)
steer = pos * KP + der * KD
```

Tune `KP`, `KD`, and `BASE_DC` in the script you are running. Start with P only — raise `KP` until the robot tracks well but does not oscillate — then try PD and add a small `KD`. For tuning theory and videos of P vs PD on 90° corners, see the [blog post](https://www.antonsmindstorms.com/2026/04/22/pid-line-follower-ev3-spike-prime/).

Shape values are ASCII characters: `|` straight, `<` / `>` turns, `Y` split, `T` junction, or space when no line is detected.
