# LMS Line Sensor I2C API

Firmware reference: **3.87**  
Default I2C slave address: **`0x33`**  
Test-build address: **`0x34`**  
Sensor channels: **8**

This document describes the I2C protocol implemented by the LMS line-sensor firmware and gives MicroPython examples for an ESP32 acting as the I2C controller.

## 1. Bus setup

The line sensor is an I2C slave. The ESP32 is the I2C controller.

- Use a common ground between the ESP32 and the line sensor.
- Use the logic voltage required by the sensor board. ESP32 GPIO is 3.3 V only.
- SDA and SCL require pull-up resistors if the boards do not already provide them.
- The firmware uses 7-bit I2C address `0x33` unless compiled with `TEST_VERSION`, in which case it uses `0x34`.

Example ESP32 initialization:

```python
from machine import I2C, Pin

# Change the pins to match your ESP32 board and wiring.
i2c = I2C(
    0,
    scl=Pin(4),
    sda=Pin(5),
    freq=100_000,
)

LINE_SENSOR_ADDRESS = 0x33

print("I2C devices:", [hex(address) for address in i2c.scan()])
```

## 2. Transaction model

### Write-only command

Send the command byte followed by any command arguments:

```text
START | address + W | command | argument 0 | argument 1 | ... | STOP
```

MicroPython:

```python
i2c.writeto(LINE_SENSOR_ADDRESS, bytes((command, *arguments)))
```

### Command followed by a response

Send the command and arguments, allow the slave to process them, and then read the documented response length:

```text
START | address + W | command | arguments... | STOP
START | address + R | response bytes...      | STOP
```

MicroPython:

```python
from time import sleep_us

i2c.writeto(LINE_SENSOR_ADDRESS, bytes((command, *arguments)))
sleep_us(300)
response = i2c.readfrom(LINE_SENSOR_ADDRESS, response_length)
```

### Reading measurements

A measurement is read without first sending a command:

```python
frame = i2c.readfrom(LINE_SENSOR_ADDRESS, 13)
```

The returned data depends on the current operating mode:

- Raw mode: raw 8-bit ADC values.
- Calibrated mode: normalized sensor values.
- Calibrating mode: raw values.

## 3. Measurement frame

Every normal measurement read returns 13 bytes.

| Offset | Field | Range or encoding | Description |
|---:|---|---|---|
| 0 | Sensor 0 | `0..255` | Leftmost or first detector, according to board orientation. |
| 1 | Sensor 1 | `0..255` | Detector value. |
| 2 | Sensor 2 | `0..255` | Detector value. |
| 3 | Sensor 3 | `0..255` | Detector value. |
| 4 | Sensor 4 | `0..255` | Detector value. |
| 5 | Sensor 5 | `0..255` | Detector value. |
| 6 | Sensor 6 | `0..255` | Detector value. |
| 7 | Sensor 7 | `0..255` | Rightmost or last detector, according to board orientation. |
| 8 | Position | `0..255` | Signed line position encoded with an offset of 128. |
| 9 | Minimum | `0..255` | Minimum of the eight values used for position calculation. |
| 10 | Maximum | `0..255` | Maximum of the eight values used for position calculation. |
| 11 | Derivative | `0..255` | Smoothed position derivative, centered at 128. |
| 12 | Shape | ASCII byte | Detected line shape. |

### Position encoding

Convert the position byte to a signed value with:

```python
signed_position = frame[8] - 128
```

The practical range is `-127..127`:

- Negative: line toward sensor 0.
- `0`: centered.
- Positive: line toward sensor 7.

The encoded center value is therefore `128`.

When no usable line is detected, the firmware also returns position `128`. Check the shape byte or the minimum/maximum fields to distinguish a centered line from no line.

### Derivative encoding

The derivative is centered at 128:

```python
signed_derivative = frame[11] - 128
```

The value is internally scaled and clipped to `0..255`; it is intended as a relative movement indication rather than a value in a physical unit.

### Shape values

| Byte | Character | Meaning |
|---:|:---:|---|
| `32` | space | No line detected. |
| `124` | `\|` | Straight line or an otherwise unclassified line. |
| `84` | `T` | T junction. |
| `60` | `<` | Left L shape. |
| `62` | `>` | Right L shape. |
| `89` | `Y` | Y junction. |

## 4. Command summary

All command IDs and arguments are unsigned bytes.

| ID | Name | Request after command byte | Response | Description |
|---:|---|---|---|---|
| 0 | `SET_MODE_RAW` | None | None | Select raw measurement mode. |
| 1 | `SET_MODE_CAL` | None | None | Select calibrated/normalized measurement mode. |
| 2 | `GET_VERSION` | None | 13 bytes | Bytes 0 and 1 contain major and minor firmware versions. Remaining bytes are zero. |
| 3 | `DEBUG` | `level` | None | Set serial log level: `0..4`. |
| 4 | `CALIBRATE` | Optional `save` | None | Start calibration. Nonzero `save` stores calibration after completion. |
| 5 | `IS_CALIBRATED` | None | 13 bytes | Byte 0 is `1` when calibration data is present, otherwise `0`. |
| 6 | `LOAD_CAL` | None | None | Load calibration minimum and maximum values from EEPROM. Deferred to the main loop. |
| 7 | `SAVE_CAL` | None | None | Save current calibration values to EEPROM. Deferred to the main loop. |
| 8 | `GET_MIN` | None | 13 bytes | Bytes 0..7 contain calibration minima. |
| 9 | `GET_MAX` | None | 13 bytes | Bytes 0..7 contain calibration maxima. |
| 10 | `SET_MIN` | Eight values | None | Set the eight calibration minima. |
| 11 | `SET_MAX` | Eight values | None | Set the eight calibration maxima. |
| 12 | `NEOPIXEL` | `index, red, green, blue` | None | Set one NeoPixel immediately. |
| 13 | `LEDS` | `mode` | None | Select automatic LED display mode. |
| 14 | `SET_EMITTER` | `level` | None | Set the optional IR emitter control output low or high. |
| 15 | `GET_VALUE` | `index` | 13 bytes | Byte 0 contains one configuration byte. |
| 16 | `SET_VALUE` | `index, value` | None | Set one configuration byte and schedule the configuration for saving. |
| 17 | `SHOW_CONFIG` | None | None | Print configuration to the sensor's serial console only. |
| 18 | `LOAD_CONFIG` | None | None | Load configuration from EEPROM, or use defaults if invalid. |
| 19 | `SAVE_CONFIG` | None | None | Save configuration to EEPROM. Deferred to the main loop. |
| 20 | `GPIO_OUT` | `logical_pin, value` | None | Configure a test GPIO as output and write it. |
| 21 | `GPIO_IN` | `logical_pin` | 1 byte | Read a test GPIO. Returns `0`, `1`, or `0xFF` for an invalid pin. |
| 22 | `SERIAL_DISABLE` | None | 1 byte | Disable serial output. Response is `1`. |
| 23 | `SERIAL_ENABLE` | None | 1 byte | Enable serial output. Response is `1`. |
| 24 | `GET_UID` | None | 12 bytes | Read the CH32V203 96-bit unique ID in little-endian byte order per 32-bit word. |

## 5. Command details

### 5.1 Operating mode

#### `SET_MODE_RAW` — command 0

```text
Request:  [0]
Response: none
```

The next normal 13-byte read returns raw values.

#### `SET_MODE_CAL` — command 1

```text
Request:  [1]
Response: none
```

The next normal 13-byte read returns normalized values. Valid calibration data should be loaded or generated first.

### 5.2 Firmware and status

#### `GET_VERSION` — command 2

```text
Request:  [2]
Response: [major, minor, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
```

For this source version, the expected result begins with `[3, 87]`.

#### `DEBUG` — command 3

```text
Request:  [3, level]
Response: none
```

| Level | Name |
|---:|---|
| 0 | Error |
| 1 | Warning |
| 2 | Information |
| 3 | Debug |
| 4 | Verbose |

#### `IS_CALIBRATED` — command 5

```text
Request:  [5]
Response: [state, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
```

`state` is `0` or `1`.

This flag becomes true as calibration samples are collected; it is not a reliable indication that the configured calibration duration has finished.

### 5.3 Calibration

#### `CALIBRATE` — command 4

```text
Request:  [4]          # calibrate without automatically saving
Request:  [4, 0]       # same behavior
Request:  [4, 1]       # save calibration after completion
Response: none
```

Calibration behavior:

1. The IR emitter is enabled.
2. Current mode and LED mode are remembered.
3. Calibration minima and maxima are reset.
4. Samples are collected for `CONFIG_CAL_DURATION` seconds, default 7 seconds.
5. The previous operating and LED modes are restored.
6. Calibration is saved when the optional argument is nonzero.

Move both the dark line and the light background across every detector during calibration.

#### `LOAD_CAL` — command 6

```text
Request:  [6]
Response: none
```

Loads 8 minimum and 8 maximum bytes from EEPROM and marks the device calibrated.

#### `SAVE_CAL` — command 7

```text
Request:  [7]
Response: none
```

Saves calibration only when the sensor currently considers itself calibrated.

#### `GET_MIN` and `GET_MAX` — commands 8 and 9

```text
Request:  [8]
Response: [min0, min1, min2, min3, min4, min5, min6, min7, 0, 0, 0, 0, 0]

Request:  [9]
Response: [max0, max1, max2, max3, max4, max5, max6, max7, 0, 0, 0, 0, 0]
```

#### `SET_MIN` and `SET_MAX` — commands 10 and 11

```text
Request:  [10, min0, min1, min2, min3, min4, min5, min6, min7]
Response: none

Request:  [11, max0, max1, max2, max3, max4, max5, max6, max7]
Response: none
```

The device is marked calibrated after both arrays have been supplied. These commands do not save the arrays automatically; use `SAVE_CAL` afterward when persistent storage is required.

For every sensor, `maximum` must be greater than `minimum` to avoid invalid normalization arithmetic.

### 5.4 NeoPixels and emitter

#### `NEOPIXEL` — command 12

```text
Request:  [12, index, red, green, blue]
Response: none
```

- `index`: normally `0..8` because the strip contains 9 pixels.
- `red`, `green`, `blue`: `0..255`.
- Pixels 0..7 correspond to the detector display.
- Pixel 8 is used by firmware as the calibration/status indicator and can be overwritten later by the firmware.

#### `LEDS` — command 13

```text
Request:  [13, mode]
Response: none
```

| Mode | Name | Behavior |
|---:|---|---|
| 0 | Off | Clear all NeoPixels. |
| 1 | Normal | Show detector intensity; green in calibrated mode and red in raw mode. |
| 2 | Inverted | Show inverted detector intensity. |
| 3 | Position | Show the calculated position across the detector LEDs. |

#### `SET_EMITTER` — command 14

```text
Request:  [14, level]
Response: none
```

- `0`: emitter control output low.
- Nonzero: emitter control output high.

### 5.5 Configuration

The configuration structure contains seven bytes:

| Index | Name | Default | Description |
|---:|---|---:|---|
| 0 | `MAJ_VERSION` | 3 | Configuration format major version. |
| 1 | `MIN_VERSION` | 87 | Configuration format minor version. |
| 2 | `LOAD_CAL_STARTUP` | 0 | Load saved calibration and enter calibrated mode at startup when set to 1. |
| 3 | `CAL_DURATION` | 7 | Calibration duration in seconds. |
| 4 | `SHAPE_THRESHOLD_BLACK` | 100 | Per-detector threshold used to build the shape mask. |
| 5 | `IR_POWER` | 0 | Emitter level applied during startup. |
| 6 | `CRC` | calculated | XOR checksum over indices 0..5. Managed by the firmware. |

#### `GET_VALUE` — command 15

```text
Request:  [15, index]
Response: [value, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
```

For an out-of-range index, the returned value is `0`.

#### `SET_VALUE` — command 16

```text
Request:  [16, index, value]
Response: none
```

The firmware schedules the configuration for saving after a valid write.

Avoid changing indices 0, 1, or 6. Changing the stored version bytes can make the configuration fail validation, and index 6 is the checksum maintained by firmware.

Changes to `IR_POWER` are stored but are not immediately applied by this command. Send `SET_EMITTER` to change the output immediately, or restart/load as appropriate.

#### `SHOW_CONFIG` — command 17

Prints the configuration to the sensor's serial port. No data is returned over I2C.

#### `LOAD_CONFIG` — command 18

Loads and validates configuration from EEPROM. Invalid data is replaced in RAM with defaults.

#### `SAVE_CONFIG` — command 19

Schedules an EEPROM configuration write in the main loop.

### 5.6 Test GPIO and serial control

Logical GPIO mapping:

| Logical pin | MCU pin |
|---:|---|
| 0 | `PA9` |
| 1 | `PA10` |

#### `GPIO_OUT` — command 20

```text
Request:  [20, logical_pin, value]
Response: none
```

A zero value drives low; a nonzero value drives high.

#### `GPIO_IN` — command 21

```text
Request:  [21, logical_pin]
Response: [value]
```

The input uses the MCU's internal pull-up.

- `0`: low.
- `1`: high.
- `255`: invalid logical pin.

#### `SERIAL_DISABLE` — command 22

```text
Request:  [22]
Response: [1]
```

Disables serial output. This is useful when PA9/PA10 are tested as GPIO and serial activity would interfere.

#### `SERIAL_ENABLE` — command 23

```text
Request:  [23]
Response: [1]
```

Restarts serial output at 115200 baud.

### 5.7 Unique ID

#### `GET_UID` — command 24

```text
Request:  [24]
Response: 12 UID bytes
```

Each 32-bit UID word is serialized least-significant byte first. A convenient display form is a 24-character hexadecimal string.

## 6. ESP32 MicroPython driver

The following small driver covers normal sensor use and all general command patterns.

```python
from time import sleep_ms, sleep_us


class LMSLineSensorI2C:
    ADDRESS = 0x33
    FRAME_LENGTH = 13
    SENSOR_COUNT = 8

    CMD_SET_MODE_RAW = 0
    CMD_SET_MODE_CAL = 1
    CMD_GET_VERSION = 2
    CMD_DEBUG = 3
    CMD_CALIBRATE = 4
    CMD_IS_CALIBRATED = 5
    CMD_LOAD_CAL = 6
    CMD_SAVE_CAL = 7
    CMD_GET_MIN = 8
    CMD_GET_MAX = 9
    CMD_SET_MIN = 10
    CMD_SET_MAX = 11
    CMD_NEOPIXEL = 12
    CMD_LEDS = 13
    CMD_SET_EMITTER = 14
    CMD_GET_VALUE = 15
    CMD_SET_VALUE = 16
    CMD_SHOW_CONFIG = 17
    CMD_LOAD_CONFIG = 18
    CMD_SAVE_CONFIG = 19
    CMD_GPIO_OUT = 20
    CMD_GPIO_IN = 21
    CMD_SERIAL_DISABLE = 22
    CMD_SERIAL_ENABLE = 23
    CMD_GET_UID = 24

    LEDS_OFF = 0
    LEDS_NORMAL = 1
    LEDS_INVERTED = 2
    LEDS_POSITION = 3

    CONFIG_MAJ_VERSION = 0
    CONFIG_MIN_VERSION = 1
    CONFIG_LOAD_CAL_STARTUP = 2
    CONFIG_CAL_DURATION = 3
    CONFIG_SHAPE_THRESHOLD_BLACK = 4
    CONFIG_IR_POWER = 5

    def __init__(self, i2c, address=ADDRESS, command_delay_us=300):
        self.i2c = i2c
        self.address = address
        self.command_delay_us = command_delay_us

    @staticmethod
    def _byte(value):
        value = int(value)
        if not 0 <= value <= 255:
            raise ValueError("byte value must be in range 0..255")
        return value

    def write_command(self, command, *arguments):
        packet = bytes(
            [self._byte(command)]
            + [self._byte(value) for value in arguments]
        )
        self.i2c.writeto(self.address, packet)

    def query(self, command, response_length, *arguments):
        self.write_command(command, *arguments)
        sleep_us(self.command_delay_us)
        return self.i2c.readfrom(self.address, response_length)

    def read_frame(self):
        data = self.i2c.readfrom(self.address, self.FRAME_LENGTH)
        if len(data) != self.FRAME_LENGTH:
            raise OSError("expected a 13-byte sensor frame")

        return {
            "sensors": tuple(data[0:8]),
            "position_byte": data[8],
            "position": data[8] - 128,
            "minimum": data[9],
            "maximum": data[10],
            "derivative_byte": data[11],
            "derivative": data[11] - 128,
            "shape_byte": data[12],
            "shape": chr(data[12]),
            "line_detected": data[12] != ord(" "),
            "raw": data,
        }

    def set_raw_mode(self):
        self.write_command(self.CMD_SET_MODE_RAW)

    def set_calibrated_mode(self):
        self.write_command(self.CMD_SET_MODE_CAL)

    def get_version(self):
        data = self.query(self.CMD_GET_VERSION, self.FRAME_LENGTH)
        return data[0], data[1]

    def is_calibrated(self):
        return bool(self.query(
            self.CMD_IS_CALIBRATED,
            self.FRAME_LENGTH,
        )[0])

    def calibrate(self, save=False):
        self.write_command(self.CMD_CALIBRATE, 1 if save else 0)

    def load_calibration(self):
        self.write_command(self.CMD_LOAD_CAL)

    def save_calibration(self):
        self.write_command(self.CMD_SAVE_CAL)

    def get_calibration_minimum(self):
        return tuple(self.query(
            self.CMD_GET_MIN,
            self.FRAME_LENGTH,
        )[0:8])

    def get_calibration_maximum(self):
        return tuple(self.query(
            self.CMD_GET_MAX,
            self.FRAME_LENGTH,
        )[0:8])

    def set_calibration_minimum(self, values):
        values = tuple(values)
        if len(values) != self.SENSOR_COUNT:
            raise ValueError("exactly eight minimum values are required")
        self.write_command(self.CMD_SET_MIN, *values)

    def set_calibration_maximum(self, values):
        values = tuple(values)
        if len(values) != self.SENSOR_COUNT:
            raise ValueError("exactly eight maximum values are required")
        self.write_command(self.CMD_SET_MAX, *values)

    def set_led_mode(self, mode):
        if mode not in range(4):
            raise ValueError("LED mode must be 0..3")
        self.write_command(self.CMD_LEDS, mode)

    def set_neopixel(self, index, red, green, blue):
        self.write_command(
            self.CMD_NEOPIXEL,
            index,
            red,
            green,
            blue,
        )

    def set_emitter(self, enabled):
        self.write_command(self.CMD_SET_EMITTER, 1 if enabled else 0)

    def get_config(self, index):
        return self.query(
            self.CMD_GET_VALUE,
            self.FRAME_LENGTH,
            index,
        )[0]

    def set_config(self, index, value):
        self.write_command(self.CMD_SET_VALUE, index, value)

    def gpio_write(self, logical_pin, value):
        self.write_command(
            self.CMD_GPIO_OUT,
            logical_pin,
            1 if value else 0,
        )

    def gpio_read(self, logical_pin):
        value = self.query(self.CMD_GPIO_IN, 1, logical_pin)[0]
        if value == 0xFF:
            raise ValueError("invalid logical GPIO pin")
        return value

    def disable_serial(self):
        return self.query(self.CMD_SERIAL_DISABLE, 1)[0] == 1

    def enable_serial(self):
        return self.query(self.CMD_SERIAL_ENABLE, 1)[0] == 1

    def get_uid(self):
        return self.query(self.CMD_GET_UID, 12)

    def get_uid_hex(self):
        return "".join("{:02x}".format(value) for value in self.get_uid())
```

## 7. Usage examples

### 7.1 Read raw detector values

```python
from machine import I2C, Pin
from time import sleep_ms

# Paste/import LMSLineSensorI2C before running this example.
i2c = I2C(0, scl=Pin(4), sda=Pin(5), freq=100_000)
sensor = LMSLineSensorI2C(i2c)

sensor.set_raw_mode()
sensor.set_led_mode(sensor.LEDS_NORMAL)

while True:
    frame = sensor.read_frame()
    print(
        "values=", frame["sensors"],
        "position=", frame["position"],
        "shape=", repr(frame["shape"]),
    )
    sleep_ms(50)
```

### 7.2 Calibrate, save, and use normalized values

```python
from machine import I2C, Pin
from time import sleep_ms

CALIBRATION_SECONDS = 7

i2c = I2C(0, scl=Pin(4), sda=Pin(5), freq=100_000)
sensor = LMSLineSensorI2C(i2c)

# Move the line/background across all eight detectors during this period.
sensor.calibrate(save=True)
sleep_ms((CALIBRATION_SECONDS * 1000) + 250)

sensor.set_calibrated_mode()
sensor.set_led_mode(sensor.LEDS_POSITION)

while True:
    frame = sensor.read_frame()

    if frame["line_detected"]:
        print(
            "position=", frame["position"],
            "derivative=", frame["derivative"],
            "shape=", frame["shape"],
        )
    else:
        print("line not detected")

    sleep_ms(20)
```

Read the configured duration instead of assuming the default:

```python
seconds = sensor.get_config(sensor.CONFIG_CAL_DURATION)
sensor.calibrate(save=True)
sleep_ms((seconds * 1000) + 250)
```

### 7.3 Load saved calibration at startup

```python
sensor.load_calibration()
sleep_ms(20)  # Allow the deferred EEPROM operation to run.
sensor.set_calibrated_mode()

print("calibrated:", sensor.is_calibrated())
print("minimum:", sensor.get_calibration_minimum())
print("maximum:", sensor.get_calibration_maximum())
```

To make this automatic on future boots:

```python
sensor.set_config(sensor.CONFIG_LOAD_CAL_STARTUP, 1)
```

`SET_VALUE` already schedules the updated configuration for saving.

### 7.4 Change shape threshold

```python
old_threshold = sensor.get_config(sensor.CONFIG_SHAPE_THRESHOLD_BLACK)
print("old shape threshold:", old_threshold)

sensor.set_config(sensor.CONFIG_SHAPE_THRESHOLD_BLACK, 110)
print("new shape threshold:", sensor.get_config(
    sensor.CONFIG_SHAPE_THRESHOLD_BLACK
))
```

### 7.5 Set an individual NeoPixel

```python
# Set detector pixel 0 to dim blue.
sensor.set_neopixel(0, 0, 0, 20)
```

Automatic LED modes can overwrite manually set colors on later firmware loop iterations.

### 7.6 Read the device UID

```python
print("UID:", sensor.get_uid_hex())
```

### 7.7 Simple proportional line follower value

This example calculates a steering correction only. Motor control is application-specific.

```python
KP = 0.8

frame = sensor.read_frame()

if frame["line_detected"]:
    steering = int(KP * frame["position"])
    steering = max(-100, min(100, steering))
    print("steering:", steering)
else:
    print("stop or search for the line")
```

## 8. Firmware 3.87 implementation notes

### Two response mechanisms are present

Commands `21` through `24` prepare `replyBuf` and return that data from `RequestEvent()`. This is the conventional and reliable write-command-then-read mechanism.

Commands `2`, `5`, `8`, `9`, and `15` call `Wire.write()` directly from `ReceiveEvent()` and intend to return a padded 13-byte response. Whether that works exactly as intended can depend on the CH32 Arduino `Wire` implementation. On I2C slave implementations that require all transmitted data to be supplied from the request callback, the subsequent read may return the current 13-byte measurement frame instead.

A robust firmware cleanup would make every query command fill `replyBuf`, set `replyLen`, and set `replyPending`, just as `GET_UID` and `GPIO_IN` already do.

### EEPROM commands are asynchronous

`LOAD_CAL`, `SAVE_CAL`, `SET_VALUE`, and `SAVE_CONFIG` schedule work that is performed by the main loop. Do not issue dependent commands back-to-back without a small delay.

### Calibration completion

`IS_CALIBRATED` reports that usable calibration values exist; it does not report that the timed calibration procedure has ended. Wait for the configured calibration duration before selecting calibrated mode or starting normal operation.

### No acknowledgement for most writes

Most write-only commands have no explicit success response. The controller must validate state through a related read, where one exists.
