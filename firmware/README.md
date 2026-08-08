# LMS line sensor firmware

Firmware for an eight-channel reflectance line sensor based on the CH32V203.
The sensor can be controlled through I2C, UART uRemote, or USB CDC uRemote.
A browser dashboard and a Windows/Linux Python client are included.

Current firmware version: **5.5**.

## How to flash firmware on the Line Sensor board

1. Connect the Line Sensor board to your PC using USB.
2. Press the **RESET** button twice in quick succession.
3. A UF2 mass-storage device named **CH32V UF2** should appear in your PC's file
   manager.
4. Select the line-sensor UF2 firmware file and drag it onto the **CH32V UF2**
   drive.
5. Wait until the firmware has been written to the board. The UF2 mass-storage
   device will disappear automatically.
6. If the NeoPixels do not scan, disconnect and reconnect USB power.

## Features

- Eight raw or calibrated reflectance values
- Line position and position derivative
- Shape recognition for straight, T, left, right, and Y intersections
- EEPROM-backed calibration and configuration
- Configurable IR emitter
- Eight sensor NeoPixels plus one indicator NeoPixel
- Automatic LED modes for values, inverted values, and line position
- Unique 12-byte CH32V203 device ID
- I2C slave interface at address `0x33`
- Named uRemote API on UART and native USB CDC
- Browser dashboard for configuration, calibration, visualization, and diagnostics
- Desktop Python uRemote library for Windows and Linux

## Interfaces

| Interface | Settings | Protocol |
|---|---|---|
| I2C | Slave address `0x33` | Numeric byte commands and binary replies |
| UART | 115200 baud | Framed uRemote |
| USB CDC | VID `0xCAFE`, PID `0x4001`, product `Line Sensor uRemote` | Framed uRemote |

UART and USB expose the same named uRemote handlers. USB CDC carries protocol
frames only; it does not emit unsolicited text logs. A normal serial terminal
will therefore not show a readable debug console.

Only one program should open the USB serial port at a time. Disconnect the web
dashboard before using the Python client or another serial application.

## Sensor modes

| Value | Mode | Description |
|---:|---|---|
| `0` | Raw | Uncalibrated sensor values |
| `1` | Calibrated | Values normalized using calibration minima and maxima |
| `2` | Digital | Reserved compatibility mode; currently exposes raw values |
| `3` | Calibrating | Collecting new calibration limits |

## Sensor packet

Normal I2C reads and the uRemote `all` command return a 13-byte packet:

| Byte | Meaning |
|---:|---|
| `0-7` | Eight sensor values in the active mode |
| `8` | Position byte, centered at 128 |
| `9` | Minimum processed sensor value |
| `10` | Maximum processed sensor value |
| `11` | Position derivative, centered at 128 |
| `12` | ASCII shape character |

Position and derivative can be converted to signed dashboard values with:

```text
signed_position = round(position_byte * 256 / 255 - 128)
signed_derivative = derivative_byte - 128
```

Shape values are:

| Character | Meaning |
|---|---|
| Space | No recognized line shape |
| `|` | Straight line |
| `T` | T intersection |
| `<` | Left intersection |
| `>` | Right intersection |
| `Y` | Y intersection |

## LED modes

| Value | Mode | Description |
|---:|---|---|
| `0` | Off | Automatic sensor LEDs off |
| `1` | Normal | LED brightness follows sensor values |
| `2` | Inverted | LED brightness follows inverted sensor values |
| `3` | Position | Indicates the detected line position |

Setting an individual NeoPixel switches the strip to manual control. Sending an
`leds`/`led` command or I2C `CMD_LEDS` returns control to an automatic LED mode.

## EEPROM configuration

The configuration is seven bytes long:

| Index | Field | Range/meaning |
|---:|---|---|
| `0` | Firmware major version | Read-only in the dashboard |
| `1` | Firmware minor version | Read-only in the dashboard |
| `2` | Load calibration at startup | `0` off, `1` on |
| `3` | Calibration duration | Seconds, normally `1-255` |
| `4` | Shape threshold | `0-255` |
| `5` | IR emitter at startup | `0` off, nonzero on |
| `6` | CRC | XOR of bytes `0-5`; generated when saving |

Loading configuration applies the stored emitter setting. Saving configuration
recalculates the CRC.

At power-up, the NeoPixel scan shows the configured startup state:

| Calibration at startup | Emitter at startup | Scan color |
|---|---|---|
| Off | Off | Blue |
| Off | On | Yellow |
| On | Off | Red |
| On | On | Green |

## I2C API

The sensor is an I2C slave at address `0x33`. A write begins with the numeric
command byte followed by any arguments.

Commands that return data use a write-then-read transaction:

1. Write the command and any argument.
2. Read the documented number of bytes.
3. The command-specific reply is consumed by that read.

Later reads return the normal 13-byte sensor packet. Commands without a specific
reply are queued and executed from the main firmware loop. They do not produce
an acknowledgement; a following read returns the sensor packet.

### I2C commands

| Value | Command | Write bytes after command | Read reply / behavior |
|---:|---|---|---|
| `0` | `CMD_SET_MODE_RAW` | None | Select raw mode; no command reply |
| `1` | `CMD_SET_MODE_CAL` | None | Select calibrated mode; no command reply |
| `2` | `CMD_GET_VERSION` | None | 2 bytes: major, minor |
| `3` | `CMD_DEBUG` | Optional legacy level | Reserved no-op; no command reply |
| `4` | `CMD_CALIBRATE` | Optional save flag | Start calibration; no command reply |
| `5` | `CMD_IS_CALIBRATED` | None | 1 byte: `0` or `1` |
| `6` | `CMD_LOAD_CAL` | None | Load calibration; no command reply |
| `7` | `CMD_SAVE_CAL` | None | Save calibration; no command reply |
| `8` | `CMD_GET_CAL_MIN` | None | 8 minimum bytes |
| `9` | `CMD_GET_CAL_MAX` | None | 8 maximum bytes |
| `10` | `CMD_SET_CAL_MIN` | 8 minimum bytes | Update minima; no command reply |
| `11` | `CMD_SET_CAL_MAX` | 8 maximum bytes | Update maxima; no command reply |
| `12` | `CMD_NEOPIXEL` | Index, red, green, blue | Set pixel `0-8`; no command reply |
| `13` | `CMD_LEDS` | LED mode `0-3` | Select automatic LED mode; no command reply |
| `14` | `CMD_SET_EMITTER` | Off/on byte | Set IR emitter; no command reply |
| `15` | `CMD_GET_CONF_VALUE` | Config index | 1 configuration byte; invalid index returns `0` |
| `16` | `CMD_SET_CONF_VALUE` | Index, value | Change byte and save config; no command reply |
| `17` | `CMD_GET_CONFIG` | None | 7 configuration bytes |
| `18` | `CMD_LOAD_CONFIG` | None | Load config and apply emitter; no command reply |
| `19` | `CMD_SAVE_CONFIG` | None | Save config; no command reply |
| `20` | Legacy | None | Do not use |
| `21` | Legacy | None | Do not use |
| `22` | `CMD_UART_TEST` | None | I2C-only UART TX/RX loopback result: `1` pass, `0` fail |
| `24` | `CMD_GET_UID` | None | 12 UID bytes |

Command value `23` is unassigned. The former serial enable/disable commands are
not available because UART remains dedicated to uRemote.

### I2C example

This MicroPython example selects calibrated mode and reads the live packet:

```python
from machine import I2C, Pin

ADDRESS = 0x33
i2c = I2C(1, scl=Pin(4), sda=Pin(5), freq=100_000)

i2c.writeto(ADDRESS, bytes([1]))       # CMD_SET_MODE_CAL
packet = i2c.readfrom(ADDRESS, 13)
values = tuple(packet[:8])
position = packet[8] - 128
print(values, position)
```

Reading a command-specific response:

```python
i2c.writeto(ADDRESS, bytes([2]))       # CMD_GET_VERSION
major, minor = i2c.readfrom(ADDRESS, 2)
```

## uRemote API

uRemote is available on UART and USB CDC. Both transports provide the same
commands and behavior.

### uRemote commands

| Command | Arguments | Successful response / behavior |
|---|---|---|
| `ping` | None | Uptime in milliseconds |
| `version`, `get_version` | None | Major and minor version |
| `set_mode_raw` | None | Select raw mode; returns mode `0` |
| `set_mode_cal` | None | Select calibrated mode; returns mode `1` |
| `mode` | Optional mode `0-3` | Get or set active mode |
| `debug`, `debug_status` | Arguments ignored | Uptime, mode, calibrated, emitter, LED mode, I2C overflow count |
| `last_commands` | None | Last UART command/parameters/time and last I2C command/parameters/time |
| `calibrate` | Optional save flag | Start calibration; returns `1` |
| `is_calibrated` | None | Calibration-active flag |
| `save`, `save_cal` | None | Save calibration; returns `1` |
| `load`, `load_cal` | None | Load calibration; returns `1` or an invalid-calibration error |
| `neopixel` | Index, red, green, blue | Set pixel `0-8`; returns `1` |
| `print` | Numeric value | Return the numeric value |
| `data` | None | Byte array containing eight sensor values |
| `pos` | None | Position byte `0-255` |
| `shape` | None | ASCII shape byte |
| `pds`, `pdr` | None | Position, derivative, shape as three values |
| `all` | None | Complete 13-byte sensor packet |
| `get_cal_min` | None | Byte array containing eight calibration minima |
| `get_cal_max` | None | Byte array containing eight calibration maxima |
| `set_cal_min` | Eight values or one byte array | Set minima; returns `1` |
| `set_cal_max` | Eight values or one byte array | Set maxima; returns `1` |
| `get_conf_value` | Config index | One configuration byte |
| `set_conf_value` | Index, value | Change byte, save config, return `1` |
| `get_config` | None | Seven-byte configuration array |
| `load_config` | None | Load config, apply emitter, return `1` |
| `save_config` | None | Save config; returns `1` |
| `get_uid` | None | 12-byte UID array |
| `cur_mode` | None | Current mode |
| `blackline` | None | Legacy black-line flag; polarity detection is disabled |
| `set_emitter`, `emitter` | Off/on value | Set emitter; returns `1` |
| `leds`, `led` | Optional LED mode `0-3` | Get or set automatic LED mode |

The `debug` command does not configure a debug level. It is an alias of
`debug_status` and returns explicit diagnostic information.

For a comparison with the command names used by the external LMS line-sensor
MicroPython driver, see
[`../UREMOTE_COMMAND_COMPARISON.md`](../UREMOTE_COMMAND_COMPARISON.md).

## Python USB client

The [`library`](library/) directory contains a desktop adaptation of
`uremote.py`, a port-selection helper, and a live-reading example for Windows
and Linux.

```text
cd library
python -m pip install -r requirements.txt
python read_line_sensor.py
```

The example lists detected serial/USB ports and asks which one to open. A port
can also be provided explicitly:

```text
python read_line_sensor.py --port COM5 --mode raw
python read_line_sensor.py --port /dev/ttyACM0 --mode calibrated
```

Basic library use:

```python
from uremote import URemote, select_serial_port

with URemote(select_serial_port()) as sensor:
    packet = sensor.call("all")
    print(list(packet[:8]))
```

## USB web dashboard

The [`web`](web/) directory contains a dependency-free HTML, CSS, and JavaScript
dashboard. It implements uRemote directly over the browser Web Serial API.

The dashboard provides:

- USB device connection and UID display
- Raw/calibrated mode and emitter control
- Live numeric values and bar graphs for all eight sensors
- Signed position display and shape indication
- Calibration start, load, save, minima, and maxima
- EEPROM configuration editing
- LED mode and per-pixel NeoPixel tests
- Live emitter, sensor-mode, and LED-mode status
- On-demand command and runtime diagnostics
- Light and dark themes

Sensor data is requested every 250 ms. Runtime status is refreshed approximately
once per second while connected.

### Start the dashboard

Web Serial requires a secure browser context. Localhost is accepted, so serve
the directory instead of opening `index.html` directly:

```text
cd web
python -m http.server 8000
```

Then:

1. Open `http://localhost:8000` in Chrome or Edge.
2. Select **Connect USB**.
3. Choose **Line Sensor uRemote** in the browser's serial-port picker.

Firefox and Safari do not currently provide the required Web Serial API.

### Debug through the dashboard

Because the USB port contains framed uRemote traffic, use the dashboard rather
than a text terminal for diagnostics:

1. Connect the sensor and confirm that the connection indicator is online.
2. Check the status strip for emitter, raw/calibrated mode, and LED mode.
3. Open **On-demand diagnostics / Command trace**.
4. Select **Refresh** to call `debug_status` and `last_commands`.

The diagnostic panel shows:

- Firmware uptime
- I2C request-queue overflow count
- Most recent UART uRemote command and its parameters
- Most recent I2C command and its parameters

USB dashboard requests are deliberately excluded from the command trace, so
polling by the page does not overwrite the UART or I2C information being
investigated. The `debug`, `debug_status`, and `last_commands` queries also do
not replace the recorded UART command.

Connection and command failures appear as dashboard notifications. For browser
or JavaScript errors, open Chrome/Edge Developer Tools and inspect the Console.

## uRemote frame encoding

Applications normally use the supplied Python library or web dashboard and do
not need to encode frames directly. The wire format is documented here for
implementing another uRemote client.

Each frame is encoded as:

```text
<frame_length> <$MU <status_and_command_length> <command> [<type> <length> <data> ...]
```

- The first byte counts all bytes after itself.
- The upper three header bits contain reply status.
- The lower five header bits contain the command-name length, maximum 31 bytes.
- Status `0` means success; nonzero status means an error reply.
- Argument types are `A` byte array, `B` boolean, `N` ASCII number, and `S` UTF-8 string.
- Successful replies repeat the request command name.

## UART loopback test

`CMD_UART_TEST` is an I2C-only production test and has no corresponding uRemote
command. Before running it, connect UART TX (PA9) to UART RX (PA10) with a test
wire. The firmware:

1. Discards pending UART RX data.
2. Sends a small valid uRemote `test` frame on UART TX.
3. Waits up to 50 ms for the looped-back frame on UART RX.
4. Compares every received byte with the transmitted frame.

The test is executed from the main loop rather than the I2C interrupt handler.
After writing command `22`, wait at least 100 ms and then read one byte:

```python
from time import sleep_ms

i2c.writeto(ADDRESS, bytes([22]))       # CMD_UART_TEST
sleep_ms(100)
passed = i2c.readfrom(ADDRESS, 1)[0] == 1
print("UART loopback:", "PASS" if passed else "FAIL")
```

A missing jumper, mismatched byte, incomplete frame, or timeout returns `0`.
