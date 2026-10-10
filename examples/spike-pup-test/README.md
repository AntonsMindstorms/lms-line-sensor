# Simple line test

A SPIKE Prime hub reads line position, derivative and shape from an LMS-ESP32
that talks to the line sensor over I2C, using PUPRemote between hub and ESP32.

## Setup

* Connect the line sensor module to the LMS-ESP32 with the Qwiic cable.
* Connect the LMS-ESP32 to the SPIKE Prime hub on port A.

## Load the programs

### LMS-ESP32

1. Open <https://viper-ide.org/> and connect to the LMS-ESP32.
2. Create a new program `line_sensor.py` and paste the contents of
   [`micropython/line_sensor.py`](../../micropython/line_sensor.py). Save it.
3. Create a new program `main.py` and paste the contents of
   [`line_esp32_main.py`](line_esp32_main.py). Save it.

### Pybricks

1. Open <https://code.pybricks.com>.
2. Create a new program named `line_sensor_pybricks.py` and paste the contents of
   [`micropython/line_sensor_pybricks.py`](../../micropython/line_sensor_pybricks.py).
3. Create a new program named `line_pybricks` and paste the contents of
   [`line_pybricks.py`](line_pybricks.py).

## Running

1. Reset the LMS-ESP32 so that `main.py` starts.
2. Run `line_pybricks.py` on the hub.
3. A countdown is shown on the hub display.
4. Press the left button to calibrate the line sensor.
