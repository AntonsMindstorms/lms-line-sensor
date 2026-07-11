# LMS Line Sensor uRemote API

**Firmware:** uRemote Line Sensor 5.4  
**Transport:** UART using the uRemote RPC protocol  
**UART speed:** 115200 baud  
**Sensor channels:** 8  
**Primary client:** Pybricks hub

This document describes the uRemote commands implemented by the supplied LMS Line Sensor firmware and shows how to call them from Pybricks.

---

## 1. Overview

The firmware runs a uRemote server on `USART1`:

```cpp
USART1Stream SerialA;
uRemote remote(SerialA, handleRemote);
...
SerialA.begin(115200);
```

A Pybricks hub acts as the client and invokes named commands:

```python
result = ur.call("command_name", argument1, argument2)
```

The call is synchronous: the hub sends one request and waits for the corresponding response.

### Required files

Copy the current `uremote.py` library into the Pybricks project. The hub firmware must provide:

```python
from pybricks.iodevices import UARTDevice
```

Create one shared `uRemote` object for the program:

```python
from pybricks.parameters import Port
from uremote import uRemote

ur = uRemote(Port.C, baudrate=115200)
```

> The port is only an example. Use the port to which the sensor UART is connected.

---

## 2. Wiring

Connect the hub UART and sensor UART with crossed transmit and receive lines and a common ground.

| Hub signal | Sensor signal |
|---|---|
| Hub TX | Sensor RX |
| Hub RX | Sensor TX |
| GND | GND |

Typical Powered Up UART pins are:

| Connector pin | Signal |
|---:|---|
| 3 | GND |
| 4 | 3.3 V |
| 5 | Hub TX / sensor RX |
| 6 | Hub RX / sensor TX |

Both UART data lines use 3.3 V logic.

The current uRemote Python library may initialize `UARTDevice` with a nonzero `power_pin`. Only use port power when the sensor board and wiring are designed for it. Otherwise initialize the client with the appropriate safe power setting for the hardware and firmware being used.

---

## 3. Basic Pybricks connection test

```python
from pybricks.parameters import Port
from uremote import uRemote, uRemoteError

ur = uRemote(
    Port.C,
    baudrate=115200,
    wait_recv=1000,
    uart_timeout=1000,
)

try:
    milliseconds = ur.call("ping")
    major, minor = ur.call("version")

    print("Sensor uptime:", milliseconds, "ms")
    print("Firmware: {}.{}".format(major, minor))
except uRemoteError as error:
    print("uRemote error:", error)
```

Expected firmware version for the supplied source:

```text
5.4
```

---

## 4. uRemote wire protocol

Applications normally use `ur.call()` and do not need to construct frames manually.

Each frame has this form:

```text
<total-length> <$MU> <header> <command> [typed arguments...]
```

### Frame fields

| Field | Size | Description |
|---|---:|---|
| `total-length` | 1 byte | Number of bytes after the length byte, including the four-byte preamble |
| preamble | 4 bytes | Fixed byte sequence `<$MU` |
| header | 1 byte | Upper 3 bits contain status; lower 5 bits contain command-name length |
| command | 0–31 bytes | UTF-8 command name |
| arguments | variable | Typed values |

The maximum complete frame length is 255 bytes. Command names are limited to 31 bytes.

### Status values

| Status | Meaning |
|---:|---|
| `0` | Successful request or response |
| `1` | Error response |

### Supported argument types

| Python type | Wire type | Encoding |
|---|---:|---|
| `int` | `N` (`0x4E`) | UTF-8 decimal text |
| `str` | `S` (`0x53`) | UTF-8 text |
| `bool` | `B` (`0x42`) | One byte, `0` or `1` |
| `bytes` | `A` (`0x41`) | Raw byte array |

On success, `ur.call()` returns:

| Response contents | Python result |
|---|---|
| No values | `None` |
| One value | That value directly |
| Multiple values | A tuple |

Byte-array responses are returned as `bytes`.

---

## 5. Operating modes

| Mode | Value | Description |
|---|---:|---|
| Raw | `0` | Returns ADC-derived sensor values |
| Calibrated | `1` | Returns values normalized using stored calibration limits |
| Digital/reserved | `2` | Defined by the companion firmware headers but not used by this implementation |
| Calibrating | `3` | Internal timed calibration mode |

Use raw and calibrated mode through the dedicated commands:

```python
ur.call("set_mode_raw")
ur.call("set_mode_cal")
```

The generic `mode` command does not validate the supplied value, so normal clients should only set `0` or `1`.

---

## 6. Sensor data encoding

The firmware maintains a 13-byte measurement record.

| Index | Name | Encoding | Description |
|---:|---|---|---|
| `0` | Sensor 0 | `0..255` | First reflectance channel |
| `1` | Sensor 1 | `0..255` | Reflectance channel |
| `2` | Sensor 2 | `0..255` | Reflectance channel |
| `3` | Sensor 3 | `0..255` | Reflectance channel |
| `4` | Sensor 4 | `0..255` | Reflectance channel |
| `5` | Sensor 5 | `0..255` | Reflectance channel |
| `6` | Sensor 6 | `0..255` | Reflectance channel |
| `7` | Sensor 7 | `0..255` | Last reflectance channel |
| `8` | Position | Offset byte | Signed position is `byte - 128` |
| `9` | Minimum | `0..255` | Minimum of the eight processed channels |
| `10` | Maximum | `0..255` | Maximum of the eight processed channels |
| `11` | Derivative | Offset byte | Signed derivative is `byte - 128` |
| `12` | Shape | ASCII byte | Detected line shape |

### Reflectance direction

The firmware comments define:

```text
white = 255
black = 0
```

Raw values depend on the sensor electronics and surface. Calibrated mode maps each channel using its calibration minimum and maximum.

### Position

Position is transported as an unsigned byte for protocol compatibility:

```python
signed_position = position_byte - 128
```

| Encoded byte | Decoded position | Meaning |
|---:|---:|---|
| `1` | `-127` | Far to one side |
| `128` | `0` | Centered, or neutral when no line is detected |
| `255` | `127` | Far to the other side |

The physical left/right sign depends on sensor orientation.

### Derivative

Derivative also uses an offset of 128:

```python
signed_derivative = derivative_byte - 128
```

A result near zero means little lateral movement. The firmware smooths the result and calculates it over a sample history, so the first readings after startup are normally neutral.

### Shape characters

| Byte | Character | Meaning |
|---:|---:|---|
| `32` | space | No line detected |
| `124` | `|` | Straight line |
| `84` | `T` | T intersection |
| `60` | `<` | Left branch or corner |
| `62` | `>` | Right branch or corner |
| `89` | `Y` | Y intersection |

Decode a shape response with:

```python
shape = chr(shape_byte)
```

---

## 7. Complete command summary

| Command | Arguments | Return value | Description |
|---|---|---|---|
| `ping` | none | uptime in ms | Protocol and connection test |
| `add` | `a`, `b` | `a + b` | Numeric protocol self-test |
| `version` | none | `(major, minor)` | Firmware version |
| `get_version` | none | `(major, minor)` | Alias of `version` |
| `set_mode_raw` | none | mode `0` | Select raw mode |
| `set_mode_cal` | none | mode `1` | Select calibrated mode |
| `mode` | optional mode | active mode | Get or set mode |
| `cur_mode` | none | active mode | Read current mode |
| `debug` | log level | active level | Set USB/debug log level |
| `calibrate` | optional save flag | `1` | Start timed calibration |
| `is_calibrated` | none | `0` or `1` | Calibration-active flag |
| `save` | none | `1` | Save calibration to EEPROM |
| `save_cal` | none | `1` | Alias of `save` |
| `load` | none | `1` | Load calibration from EEPROM |
| `load_cal` | none | `1` | Alias of `load` |
| `data` | none | 8-byte array | Eight sensor channels |
| `pos` | none | position byte | Encoded position only |
| `shape` | none | shape byte | ASCII shape byte only |
| `pds` | none | `(position, derivative, shape)` | Compact control-loop response |
| `pdr` | none | same as `pds` | Compatibility alias |
| `all` | none | 13-byte array | Complete measurement record |
| `get_min` | none | 8-byte array | Calibration minima |
| `get_max` | none | 8-byte array | Calibration maxima |
| `set_min` | 8 numbers or one byte array | `1` | Set calibration minima |
| `set_max` | 8 numbers or one byte array | `1` | Set calibration maxima |
| `get_value` | config index | byte value | Read one configuration byte |
| `set_value` | index, value | `1` | Set and immediately save one configuration byte |
| `show_config` | none | configuration bytes | Return complete configuration structure |
| `load_config` | none | `1` | Load configuration, or restore defaults if invalid |
| `save_config` | none | `1` | Save configuration to EEPROM |
| `set_emitter` | bool or number | `1` | Set IR emitter state |
| `emitter` | bool or number | `1` | Alias of `set_emitter` |
| `leds` | optional mode | active LED mode | Get or set automatic LED display mode |
| `led` | optional mode | active LED mode | Alias of `leds` |
| `neopixel` | index, red, green, blue | `1` | Set one onboard RGB LED |
| `get_uid` | none | 12-byte array | Read CH32V203 unique ID |
| `blackline` | none | `0` or `1` | Return the firmware's black-line flag |
| `print` | numeric value | same value | Numeric echo helper |

---

## 8. Command reference

### 8.1 `ping`

Returns the firmware `millis()` counter.

```python
uptime_ms = ur.call("ping")
print(uptime_ms)
```

This is the best first command for testing communication.

---

### 8.2 `add`

Adds two numeric arguments.

```python
answer = ur.call("add", 20, 22)
print(answer)  # 42
```

The command reports an error when fewer than two arguments are supplied.

---

### 8.3 `version` / `get_version`

Returns two numeric response fields.

```python
major, minor = ur.call("get_version")
print("{}.{}".format(major, minor))
```

---

### 8.4 `set_mode_raw`

Selects raw sensor data.

```python
mode = ur.call("set_mode_raw")
assert mode == 0
```

---

### 8.5 `set_mode_cal`

Selects calibrated sensor data.

```python
mode = ur.call("set_mode_cal")
assert mode == 1
```

Calibration values should be valid before using this mode.

---

### 8.6 `mode`

Reads or changes the active mode.

```python
current = ur.call("mode")
print(current)

current = ur.call("mode", 1)
print(current)
```

Prefer `set_mode_raw` and `set_mode_cal` for normal operation.

---

### 8.7 `cur_mode`

Returns the active mode without accepting an argument.

```python
current = ur.call("cur_mode")
```

---

### 8.8 `debug`

Sets the firmware debug-log threshold.

| Level | Name |
|---:|---|
| `0` | Error |
| `1` | Warning |
| `2` | Information |
| `3` | Debug |
| `4` | Verbose |

```python
active_level = ur.call("debug", 0)
```

Debug output is written to the firmware's `Serial` interface. The source deliberately avoids writing unframed debug text to the uRemote UART.

---

### 8.9 `calibrate`

Starts calibration and automatically stops after the configured duration.

```python
ur.call("calibrate")
```

Pass a nonzero save flag to save the new limits automatically when calibration stops:

```python
ur.call("calibrate", 1)
```

During calibration:

- The IR emitter is enabled.
- Sensor LED display is turned off.
- Raw minimum and maximum values are collected.
- The blue calibration indicator flashes.
- The previous mode and LED mode are restored when calibration ends.

The duration is read from configuration index `3`.

---

### 8.10 `is_calibrated`

```python
calibrated = bool(ur.call("is_calibrated"))
```

This indicates that calibration limits are active in RAM. It does not prove that the limits cover the full black/white range correctly.

---

### 8.11 `save` / `save_cal`

Stores the current eight minimum and eight maximum calibration values in EEPROM.

```python
ur.call("save_cal")
```

The firmware only writes calibration data when `is_calibrated` is true.

---

### 8.12 `load` / `load_cal`

Loads calibration values from EEPROM and marks the sensor calibrated.

```python
ur.call("load_cal")
```

---

### 8.13 `data`

Returns only the eight current sensor channel bytes.

```python
values = ur.call("data")
print(tuple(values))
```

The returned type is `bytes`. Values come from the currently selected mode.

---

### 8.14 `pos`

Returns one encoded position value.

```python
position = ur.call("pos") - 128
```

---

### 8.15 `shape`

Returns one ASCII shape byte.

```python
shape = chr(ur.call("shape"))
```

---

### 8.16 `pds` / `pdr`

Returns position, derivative, and shape as three numeric response fields.

```python
position_byte, derivative_byte, shape_byte = ur.call("pds")

position = position_byte - 128
derivative = derivative_byte - 128
shape = chr(shape_byte)
```

This is the recommended command for a fast line-following control loop because it transfers only the processed fields required by the controller.

---

### 8.17 `all`

Returns the complete 13-byte measurement record.

```python
record = ur.call("all")

sensors = tuple(record[0:8])
position = record[8] - 128
minimum = record[9]
maximum = record[10]
derivative = record[11] - 128
shape = chr(record[12])
```

---

### 8.18 `get_min` / `get_max`

```python
minimum = tuple(ur.call("get_min"))
maximum = tuple(ur.call("get_max"))
```

Each response contains eight bytes.

---

### 8.19 `set_min` / `set_max`

These commands accept either eight separate numeric arguments:

```python
ur.call("set_min", 10, 11, 12, 13, 14, 15, 16, 17)
ur.call("set_max", 220, 221, 222, 223, 224, 225, 226, 227)
```

or one packed byte array:

```python
minimum = bytes((10, 11, 12, 13, 14, 15, 16, 17))
maximum = bytes((220, 221, 222, 223, 224, 225, 226, 227))

ur.call("set_min", minimum)
ur.call("set_max", maximum)
```

The firmware marks calibration active after both arrays have been supplied. Call `save_cal` to persist them.

---

### 8.20 `get_value`

Reads one byte from the configuration structure.

```python
calibration_seconds = ur.call("get_value", 3)
```

See the configuration table below.

---

### 8.21 `set_value`

Changes one configuration byte and immediately saves the complete configuration to EEPROM.

```python
ur.call("set_value", 3, 7)  # calibration duration = 7 seconds
```

Use valid byte values only. Avoid unnecessary repeated writes because this command writes EEPROM on every successful call.

---

### 8.22 `show_config`

Returns the complete raw configuration structure as a byte array.

```python
raw = ur.call("show_config")
print(tuple(raw))
```

It also invokes the firmware's debug-side configuration print function.

---

### 8.23 `load_config`

Loads configuration from EEPROM. If validation fails, firmware defaults are restored and saved.

```python
ur.call("load_config")
```

The configured emitter state is applied after loading.

---

### 8.24 `save_config`

```python
ur.call("save_config")
```

This is normally unnecessary directly after `set_value`, because `set_value` already saves.

---

### 8.25 `set_emitter` / `emitter`

Controls the IR emitter.

```python
ur.call("emitter", True)
ur.call("emitter", False)
```

Numeric values also work:

```python
ur.call("set_emitter", 1)
```

---

### 8.26 `leds` / `led`

Gets or sets the automatic sensor LED display mode.

| Mode | Value | Description |
|---|---:|---|
| Off | `0` | Clear the LEDs |
| Values | `1` | Display channel intensity |
| Inverted values | `2` | Display inverse channel intensity |
| Position | `3` | Display detected line position |

```python
active_mode = ur.call("leds", 3)
print(active_mode)
```

Read the current mode without changing it:

```python
active_mode = ur.call("leds")
```

The firmware limits physical NeoPixel refreshes to at most 10 Hz.

---

### 8.27 `neopixel`

Sets one RGB LED.

```python
ur.call("neopixel", 0, 20, 0, 0)
```

Valid indices are `0..8`: eight sensor LEDs and one calibration-status LED. RGB values are bytes in the range `0..255`.

An out-of-range index is ignored, but the firmware still returns success.

Automatic LED rendering may overwrite manually selected colors while an automatic LED mode is active. Set LED mode to off before manual control:

```python
ur.call("leds", 0)
ur.call("neopixel", 0, 20, 0, 0)
```

---

### 8.28 `get_uid`

Returns the 12-byte CH32V203 device UID.

```python
uid = ur.call("get_uid")
uid_hex = "".join("{:02X}".format(value) for value in uid)
print(uid_hex)
```

---

### 8.29 `blackline`

Returns the internal black-line detection flag.

```python
black_line = bool(ur.call("blackline"))
```

**Firmware 5.4 caveat:** automatic line-type detection is not run when normal calibration stops because the call is commented out in `stopCalibration()`. The value can therefore remain at its initial value or reflect an earlier loaded calibration. Do not use this command as the sole source of truth unless the firmware behavior is updated or independently verified.

---

### 8.30 `print`

Numeric echo command:

```python
value = ur.call("print", 123)
```

Despite its name, it is not a general remote print function. The firmware converts the first argument to an integer and returns it.

---

## 9. Configuration structure

The configuration consists of seven bytes.

| Index | Field | Default in firmware 5.4 | Description |
|---:|---|---:|---|
| `0` | Major version | `5` | Configuration compatibility major version |
| `1` | Minor version | `4` | Configuration compatibility minor version |
| `2` | Load calibration at startup | `0` | Load EEPROM calibration and enter calibrated mode when `1` |
| `3` | Calibration duration | firmware `CAL_TIME` | Calibration time in seconds |
| `4` | Shape black threshold | firmware `THRESHOLD_BLACK` | Per-channel threshold used for shape mask |
| `5` | IR power at startup | `0` | Emitter state restored at startup |
| `6` | CRC | calculated | XOR checksum over indices `0..5` |

Read all fields:

```python
config = ur.call("show_config")

print("major:", config[0])
print("minor:", config[1])
print("load calibration:", config[2])
print("calibration duration:", config[3])
print("shape threshold:", config[4])
print("IR startup power:", config[5])
print("CRC:", config[6])
```

Recommended writable indexes are `2..5`. Treat version fields and CRC as firmware-managed values.

### Configure calibrated startup

```python
ur.call("set_value", 2, 1)
```

### Configure calibration duration

```python
ur.call("set_value", 3, 7)
```

### Configure shape threshold

```python
ur.call("set_value", 4, 100)
```

### Enable emitter after startup

```python
ur.call("set_value", 5, 1)
```

---

## 10. Pybricks examples

### 10.1 Read raw sensor values

```python
from pybricks.parameters import Port
from pybricks.tools import wait
from uremote import uRemote

ur = uRemote(Port.C)

ur.call("emitter", True)
ur.call("set_mode_raw")

while True:
    values = ur.call("data")
    print(tuple(values))
    wait(100)
```

---

### 10.2 Load calibration and read processed data

```python
from pybricks.parameters import Port
from pybricks.tools import wait
from uremote import uRemote

ur = uRemote(Port.C)

ur.call("emitter", True)
ur.call("load_cal")
ur.call("set_mode_cal")
ur.call("leds", 3)

while True:
    record = ur.call("all")

    values = tuple(record[:8])
    position = record[8] - 128
    derivative = record[11] - 128
    shape = chr(record[12])

    print(values, position, derivative, shape)
    wait(50)
```

---

### 10.3 Calibrate and save automatically

Move the sensor across both the darkest and brightest surfaces while calibration runs.

```python
from pybricks.parameters import Port
from pybricks.tools import wait
from uremote import uRemote

ur = uRemote(Port.C)

# Store a seven-second duration.
ur.call("set_value", 3, 7)

# Start calibration and request automatic EEPROM save.
ur.call("calibrate", 1)

while ur.call("cur_mode") == 3:
    print("Calibrating...")
    wait(250)

print("Calibrated:", bool(ur.call("is_calibrated")))
ur.call("set_mode_cal")
```

The firmware itself owns the calibration timer. The hub does not need to issue a stop command.

---

### 10.4 Compact position, derivative, and shape loop

```python
from pybricks.parameters import Port
from pybricks.tools import wait
from uremote import uRemote, uRemoteError

ur = uRemote(Port.C, wait_recv=200, uart_timeout=200)

ur.call("emitter", True)
ur.call("load_cal")
ur.call("set_mode_cal")

while True:
    try:
        pos_raw, der_raw, shape_raw = ur.call("pds")

        position = pos_raw - 128
        derivative = der_raw - 128
        shape = chr(shape_raw)

        print(position, derivative, shape)
    except uRemoteError as error:
        print("Sensor communication failed:", error)

    wait(20)
```

---

### 10.5 Simple line follower

This example targets a SPIKE Prime or Robot Inventor style hub. Change ports, motor directions, gains, and speed for the robot.

```python
from pybricks.hubs import PrimeHub
from pybricks.parameters import Direction, Port
from pybricks.pupdevices import Motor
from pybricks.tools import wait
from uremote import uRemote, uRemoteError

hub = PrimeHub()

left_motor = Motor(Port.E, Direction.COUNTERCLOCKWISE)
right_motor = Motor(Port.F)

ur = uRemote(
    Port.C,
    baudrate=115200,
    wait_recv=100,
    uart_timeout=100,
)

BASE_POWER = 35
KP = 0.35
KD = 0.20


def clamp(value, low=-100, high=100):
    if value < low:
        return low
    if value > high:
        return high
    return value


ur.call("emitter", True)
ur.call("load_cal")
ur.call("set_mode_cal")
ur.call("leds", 3)

try:
    while True:
        pos_byte, der_byte, shape_byte = ur.call("pds")

        position = pos_byte - 128
        derivative = der_byte - 128
        shape = chr(shape_byte)

        if shape == " ":
            # Stop when no line is detected.
            left_motor.stop()
            right_motor.stop()
            wait(20)
            continue

        correction = KP * position + KD * derivative

        left_power = clamp(BASE_POWER - correction)
        right_power = clamp(BASE_POWER + correction)

        left_motor.dc(left_power)
        right_motor.dc(right_power)

        wait(10)

except uRemoteError as error:
    left_motor.brake()
    right_motor.brake()
    print("Line sensor error:", error)

except KeyboardInterrupt:
    left_motor.brake()
    right_motor.brake()
```

If the robot steers away from the line, reverse the sign of `KP` and `KD`, swap the motor corrections, or reverse the sensor orientation.

---

### 10.6 Detect intersections

```python
from pybricks.parameters import Port
from pybricks.tools import wait
from uremote import uRemote

ur = uRemote(Port.C)
ur.call("load_cal")
ur.call("set_mode_cal")

while True:
    _, _, shape_byte = ur.call("pds")
    shape = chr(shape_byte)

    if shape == "T":
        print("T intersection")
    elif shape == "<":
        print("Left branch")
    elif shape == ">":
        print("Right branch")
    elif shape == "Y":
        print("Y intersection")
    elif shape == " ":
        print("No line")

    wait(50)
```

---

### 10.7 Read and change configuration

```python
from pybricks.parameters import Port
from uremote import uRemote

ur = uRemote(Port.C)

raw = ur.call("show_config")
print("Before:", tuple(raw))

# Load calibration automatically at boot.
ur.call("set_value", 2, 1)

# Use a six-second calibration period.
ur.call("set_value", 3, 6)

# Enable the IR emitter at boot.
ur.call("set_value", 5, 1)

raw = ur.call("show_config")
print("After:", tuple(raw))
```

---

### 10.8 Read the device UID

```python
from pybricks.parameters import Port
from uremote import uRemote

ur = uRemote(Port.C)
uid = ur.call("get_uid")

print(":".join("{:02X}".format(value) for value in uid))
```

---

## 11. Reusable Pybricks wrapper

The following compact class converts position and derivative to signed values and shape to a character.

```python
from pybricks.tools import wait
from uremote import uRemote


class LineSensorUR:
    SENSOR_COUNT = 8
    RAW_BYTES = 13

    MODE_RAW = 0
    MODE_CALIBRATED = 1
    MODE_CALIBRATING = 3

    LEDS_OFF = 0
    LEDS_VALUES = 1
    LEDS_VALUES_INVERTED = 2
    LEDS_POSITION = 3

    CONFIG_LOAD_CAL_STARTUP = 2
    CONFIG_CAL_DURATION = 3
    CONFIG_SHAPE_THRESHOLD_BLACK = 4
    CONFIG_IR_POWER = 5

    def __init__(
        self,
        port,
        baudrate=115200,
        wait_recv=1000,
        uart_timeout=1000,
    ):
        self.ur = uRemote(
            port,
            baudrate=baudrate,
            wait_recv=wait_recv,
            uart_timeout=uart_timeout,
        )

    def ping(self):
        return self.ur.call("ping")

    def version(self):
        return self.ur.call("version")

    def mode(self):
        return self.ur.call("cur_mode")

    def mode_raw(self):
        return self.ur.call("set_mode_raw")

    def mode_calibrated(self):
        return self.ur.call("set_mode_cal")

    def sensors(self):
        return tuple(self.ur.call("data"))

    def read_all(self):
        return tuple(self.ur.call("all"))

    def position(self):
        return self.ur.call("pos") - 128

    def shape(self):
        return chr(self.ur.call("shape"))

    def position_derivative_shape(self):
        position, derivative, shape = self.ur.call("pds")
        return position - 128, derivative - 128, chr(shape)

    def start_calibration(self, save=False):
        return self.ur.call("calibrate", 1 if save else 0)

    def calibrate(self, save=True):
        self.start_calibration(save=save)
        while self.mode() == self.MODE_CALIBRATING:
            wait(100)
        return self.is_calibrated()

    def is_calibrated(self):
        return bool(self.ur.call("is_calibrated"))

    def save_calibration(self):
        return self.ur.call("save_cal")

    def load_calibration(self):
        return self.ur.call("load_cal")

    def get_min(self):
        return tuple(self.ur.call("get_min"))

    def get_max(self):
        return tuple(self.ur.call("get_max"))

    def set_min(self, values):
        values = bytes(values)
        if len(values) != self.SENSOR_COUNT:
            raise ValueError("minimum must contain 8 values")
        return self.ur.call("set_min", values)

    def set_max(self, values):
        values = bytes(values)
        if len(values) != self.SENSOR_COUNT:
            raise ValueError("maximum must contain 8 values")
        return self.ur.call("set_max", values)

    def get_config(self):
        raw = tuple(self.ur.call("show_config"))
        return {
            "major_version": raw[0],
            "minor_version": raw[1],
            "load_cal_startup": raw[2],
            "cal_duration": raw[3],
            "shape_threshold_black": raw[4],
            "ir_power": raw[5],
            "crc": raw[6],
        }

    def get_value(self, index):
        return self.ur.call("get_value", index)

    def set_value(self, index, value):
        return self.ur.call("set_value", index, value)

    def ir_power(self, enabled):
        return self.ur.call("emitter", bool(enabled))

    def leds(self, mode=None):
        if mode is None:
            return self.ur.call("leds")
        return self.ur.call("leds", mode)

    def neopixel(self, index, red, green, blue):
        return self.ur.call("neopixel", index, red, green, blue)

    def uid(self):
        return bytes(self.ur.call("get_uid"))

    def uid_hex(self):
        return "".join("{:02X}".format(value) for value in self.uid())
```

Usage:

```python
from pybricks.parameters import Port
from pybricks.tools import wait

sensor = LineSensorUR(Port.C)

print("Firmware:", sensor.version())
print("UID:", sensor.uid_hex())

sensor.ir_power(True)
sensor.load_calibration()
sensor.mode_calibrated()
sensor.leds(sensor.LEDS_POSITION)

while True:
    position, derivative, shape = sensor.position_derivative_shape()
    print(position, derivative, shape)
    wait(20)
```

---

## 12. Error handling

`ur.call()` raises `uRemoteError` for remote-handler errors and transport errors.

```python
from uremote import uRemoteError

try:
    result = ur.call("pds")
except uRemoteError as error:
    print("uRemote failure:", error)
```

Typical causes include:

- Sensor firmware is not running.
- TX and RX are not crossed.
- No common ground.
- Baud rates differ.
- The selected hub port is wrong.
- The hub firmware does not provide `UARTDevice`.
- A partial or corrupt frame was received.
- The requested command does not exist.
- An argument count or configuration index is invalid.

For low-latency control loops, use a shorter receive timeout and stop the motors on communication failure.

---

## 13. Performance recommendations

1. Use `pds` instead of `all` when only position, derivative, and shape are required.
2. Create one `uRemote` instance and reuse it.
3. Do not create a new UART object inside the control loop.
4. Avoid EEPROM-writing commands such as `set_value` and `save_cal` in high-frequency loops.
5. Do not update NeoPixels faster than the firmware's 100 ms LED flush interval.
6. Keep the uRemote UART free of unframed logging data.
7. Use calibrated mode only after loading or producing valid calibration limits.
8. Stop actuators safely when `uRemoteError` is raised.

---

## 14. Firmware-specific observations

- Firmware version is `5.4`.
- The uRemote UART is `SerialA` at 115200 baud.
- Debug logging uses a separate `Serial` interface.
- `all` and `data` return a byte array; `pds` returns three numeric values.
- Calibration ends automatically using the configured duration.
- `set_value` immediately writes configuration to EEPROM.
- The LED renderer limits `strip.show()` calls to 10 Hz.
- Manual NeoPixel values may be replaced by automatic LED rendering.
- `mode` accepts values without range validation.
- `blackline` may be stale because line-type detection is disabled at normal calibration completion in this source.
- `set_min` and `set_max` support both packed bytes and eight separate values.

---

## 15. References

- Supplied source: `LineSensor(1).ino`, LMS Line Sensor uRemote firmware 5.4.
- uRemote project: <https://github.com/AntonsMindstorms/uRemote>
- LMS Line Sensor project: <https://github.com/AntonsMindstorms/lms-line-sensor>
- Pybricks `UARTDevice`: <https://docs.pybricks.com/en/stable/iodevices/uartdevice.html>
