# Combined uRemote + I2C Line Sensor Firmware

This CH32V203 firmware exposes the same line-sensor state through both interfaces at the same time:

- uRemote frames on USART1 at 115200 baud.
- The legacy numeric Wire slave protocol on I2C address `0x33`.

Both transports operate on the same mode, calibration, configuration, sensor, and LED state. The project is based on `uremote_new`; the I2C command numbers and packet layout come from `firmware/i2c/ch32_line_improved_pio`.

## Hardware And Transport

- Target MCU: CH32V203 line sensor board.
- Sensor count: 8 analog IR sensors.
- LED output: NeoPixel strip on `PB11`, with one extra status pixel.
- IR emitter control: `PB3`.
- Calibration input: `PB1`.
- uRemote transport: UART1 at 115200 baud through `uart1_driver.*`. RX uses
  DMA1 channel 5 with a 512-byte circular buffer so NeoPixel updates do not
  interrupt reception.
- I2C transport: Wire/I2C1 slave address `0x33`, SDA on `PB7`, SCL on `PB6`.

The uRemote UART must not receive plain debug text. All host communication on UART1 should be framed uRemote messages.
TinyUSB is enabled, so Arduino `Serial` is the USB CDC debug interface. The custom DMA-backed `SerialA` stream continues to own USART1 exclusively for uRemote.

## I2C Wire Protocol

Write a numeric command byte, followed by any arguments. For commands that return a value, perform a separate read immediately afterward. A read without a pending command-specific response returns the current 13-byte sensor packet described below.

| Value | Command | Arguments / read response |
| ---: | --- | --- |
| 0 | `CMD_SET_MODE_RAW` | none |
| 1 | `CMD_SET_MODE_CAL` | none |
| 2 | `CMD_GET_VERSION` | read 2 bytes |
| 3 | `CMD_DEBUG` | log level |
| 4 | `CMD_CALIBRATE` | optional save-after flag |
| 5 | `CMD_IS_CALIBRATED` | read 1 byte |
| 6 | `CMD_LOAD_CAL` | none |
| 7 | `CMD_SAVE_CAL` | none |
| 8 | `CMD_GET_CAL_MIN` | read 8 bytes |
| 9 | `CMD_GET_CAL_MAX` | read 8 bytes |
| 10 | `CMD_SET_CAL_MIN` | 8 bytes |
| 11 | `CMD_SET_CAL_MAX` | 8 bytes |
| 12 | `CMD_NEOPIXEL` | index, red, green, blue |
| 13 | `CMD_LEDS` | LED mode |
| 14 | `CMD_SET_EMITTER` | off/on |
| 15 | `CMD_GET_CONF_VALUE` | config index; read 1 byte |
| 16 | `CMD_SET_CONF_VALUE` | config index, value |
| 17 | `CMD_GET_CONFIG` | read 7 bytes |
| 18 | `CMD_LOAD_CONFIG` | none |
| 19 | `CMD_SAVE_CONFIG` | none |
| 20 | `CMD_GPIO_OUT` | unsupported in the combined build |
| 21 | `CMD_GPIO_IN` | read `0xFF` (unsupported) |
| 22 | `CMD_SERIAL_DISABLE` | read `1`; compatibility no-op |
| 23 | `CMD_SERIAL_ENABLE` | read `1`; compatibility no-op |
| 24 | `CMD_GET_UID` | read 12 bytes |

The legacy GPIO test commands used PA9/PA10, which are the uRemote USART pins in this build. They are intentionally not allowed to reconfigure those pins. Likewise, the serial enable/disable commands acknowledge the request but never disable uRemote.

I2C writes are queued and applied in the main loop. I2C reads are served from double-buffered snapshots, so the interrupt handlers never perform EEPROM writes or call `strip.show()`.
uRemote sensor commands read that same published snapshot. The ADC pins remain in analog mode and each reported channel is the median of three conversions to reject isolated high samples.

A direct `CMD_NEOPIXEL` or uRemote `neopixel` command switches the strip to manual control. Manual control includes all nine pixels, including the calibration-status pixel, and remains active until an explicit `CMD_LEDS`/`leds` command selects an automatic LED mode. Per-pixel command bursts are briefly coalesced so an incomplete frame is not displayed.

Changed NeoPixel frames are transmitted twice. This makes a transient WS2812 data-bit error self-correct during the same update instead of leaving a false pixel visible until the next 10 Hz frame.

## Response Data Layout

Sensor arrays returned by `all` contain 13 bytes:

| Index | Meaning |
| --- | --- |
| 0-7 | Sensor values |
| 8 | Line position, 0-255, centered around 128 |
| 9 | Minimum value from the processed set |
| 10 | Maximum value from the processed set |
| 11 | Moving derivative, centered around 128 |
| 12 | Detected shape code |

Shape codes are returned as byte values:

| Shape | Code |
| --- | --- |
| No line | space, `32` |
| Straight | `|`, `124` |
| T junction | `T`, `84` |
| Left branch | `<`, `60` |
| Right branch | `>`, `62` |
| Y junction | `Y`, `89` |

## Command Naming

The I2C command enum maps to uRemote command names like this:

| I2C Command | uRemote Command | Notes |
| --- | --- | --- |
| `CMD_SET_MODE_RAW` | `set_mode_raw` | Switches output processing to raw sensor mode. |
| `CMD_SET_MODE_CAL` | `set_mode_cal` | Switches output processing to calibrated mode. |
| `CMD_GET_VERSION` | `get_version` | Returns major and minor firmware version. Alias: `version`. |
| `CMD_DEBUG` | `debug` | Sets USB CDC log level from 0 (errors) to 4 (verbose). Levels 3 and 4 emit a status line once per second; level 4 also emits sensor values. |
| `CMD_CALIBRATE` | `calibrate` | Starts calibration. Optional argument saves calibration afterward when nonzero. |
| `CMD_IS_CALIBRATED` | `is_calibrated` | Returns `1` when calibration data is active. |
| `CMD_LOAD_CAL` | `load_cal` | Loads calibration min/max from EEPROM. Alias: `load`. |
| `CMD_SAVE_CAL` | `save_cal` | Saves calibration min/max to EEPROM. Alias: `save`. |
| `CMD_GET_CAL_MIN` | `get_cal_min` | Returns 8 calibration minimum bytes. |
| `CMD_GET_CAL_MAX` | `get_cal_max` | Returns 8 calibration maximum bytes. |
| `CMD_SET_CAL_MIN` | `set_cal_min` | Sets 8 calibration minimum bytes. |
| `CMD_SET_CAL_MAX` | `set_cal_max` | Sets 8 calibration maximum bytes. |
| `CMD_NEOPIXEL` | `neopixel` | Sets one NeoPixel: index, red, green, blue. |
| `CMD_LEDS` | `leds` | Sets LED display mode. Alias: `led`. |
| `CMD_SET_EMITTER` | `set_emitter` | Turns IR emitter off/on. Alias: `emitter`. |
| `CMD_GET_CONF_VALUE` | `get_conf_value` | Reads a byte from the config struct by index. |
| `CMD_SET_CONF_VALUE` | `set_conf_value` | Writes a byte to the config struct by index and saves config. |
| `CMD_GET_CONFIG` | `get_config` | Returns all 7 raw config bytes. |
| `CMD_LOAD_CONFIG` | `load_config` | Loads config from EEPROM, falling back to defaults when invalid. |
| `CMD_SAVE_CONFIG` | `save_config` | Saves the current config to EEPROM. |
| `CMD_GET_UID` | `get_uid` | Returns 12 CH32V203 UID bytes. |

## USB CDC Debug Levels

Use the I2C `CMD_DEBUG` command or uRemote `debug(level)` command to select
USB CDC logging verbosity. The firmware starts at level 3 after reset:

| Level | Name | Output |
| ---: | --- | --- |
| 0 | Error | EEPROM commit failures and other critical faults. |
| 1 | Warning | Errors plus rejected arguments, invalid configuration data, unsupported operations, and I2C queue overflow. |
| 2 | Information | Warnings plus firmware/configuration summary, mode changes, calibration lifecycle, EEPROM operations, emitter changes, and LED-mode changes. |
| 3 | Debug | Information plus a live 5 Hz two-line dashboard. The first line contains the position track, active signal levels, mode, calibration state, emitter/LED state, derivative, min/max, and shape. The second line contains three-character-wide raw and normalized numeric values. |
| 4 | Verbose | Debug plus separate raw and normalized signal levels and rate-limited command tracing. |

Changing the level emits an unfiltered `[CONTROL]` confirmation. NeoPixel
commands are omitted from command tracing to avoid flooding USB CDC during
frame updates. The live status uses ANSI carriage-return/clear-line sequences
and UTF-8 block characters (`▁▂▃▄▅▆▇█`), so the terminal must support ANSI
escapes and UTF-8. The cursor is hidden while the dashboard is active and
restored before ordinary log messages or when selecting level 0, 1, or 2.
All logging occurs outside the I2C interrupt callbacks.

Example level-3 dashboard:

```text
[DEBUG]     42s CAL         pos=128 [────────█────────] sig=▁▂▄▇█▅▂▁ d=129 min=12 max=244 shape=|(124) cal=1 ir=1 led=NORMAL
raw :  12  18  45 180 232  91  20   8 | norm:   0   7  42 190 255  89  10   0
```

Enable it through uRemote:

```python
remote.call("debug", 3)
```

For I2C, write `CMD_DEBUG` followed by the level byte, for example `[3, 3]`
for level 3. Select level 2 or lower to stop the live dashboard while retaining
event messages appropriate to that level.

## Additional uRemote Convenience Commands

These commands are uRemote-specific conveniences and are kept for compatibility with earlier uRemote clients:

| Command | Arguments | Response | Description |
| --- | --- | --- | --- |
| `ping` | none | milliseconds | Returns `millis()`. |
| `add` | `a, b` | sum | Simple protocol test. |
| `mode` | optional mode number | current mode | Gets or sets the numeric mode. |
| `data` | none | 8 bytes | Returns current raw or calibrated sensor bytes. |
| `pos` | none | position byte | Returns current line position. |
| `shape` | none | shape byte | Returns current detected shape. |
| `pds` | none | position, derivative, shape | Compact line-tracking tuple. Derivative uses the same moving-average derivative calculation as the i2c firmware. |
| `pdr` | none | position, derivative, shape | Compatibility alias for `pds`. |

Derivative values use the same moving-average derivative calculation as the i2c firmware. A stable line is near 128; negative movement is below center and positive movement is above center.
| `all` | none | 13 bytes | Returns full current sensor/result buffer. |
| `cur_mode` | none | current mode | Returns the active mode. |
| `blackline` | none | 0 | Legacy compatibility command. Automatic line-type detection and inversion are disabled. |
| `print` | value | value | Echo helper for testing. |

## Modes

| Value | Name | Meaning |
| --- | --- | --- |
| 0 | `MODE_RAW` | Raw sensor values are reported and used for position. |
| 1 | `MODE_CAL` | Calibrated/normalized values are reported directly and used for position. |
| 2 | `MODE_DIG` | Reserved, not currently used. |
| 3 | `MODE_CALIBRATING` | Calibration is running. |

## LED Modes

| Value | Name | Meaning |
| --- | --- | --- |
| 0 | `LEDS_OFF` | Clears the NeoPixels. |
| 1 | `LEDS_NORMAL` | Shows sensor intensity. Raw mode is red, calibrated mode is green. |
| 2 | `LEDS_INVERTED` | Shows inverted intensity. |
| 3 | `LEDS_POSITION` | Shows the detected line position on the strip. |

## Config Bytes

`get_conf_value` and `set_conf_value` access the config struct by byte index:

| Index | Name | Meaning |
| --- | --- | --- |
| 0 | `CONFIG_MAJ_VERSION` | Stored major version. |
| 1 | `CONFIG_MIN_VERSION` | Stored minor version. |
| 2 | `CONFIG_LOAD_CAL_STARTUP` | Load calibration during startup when `1`. |
| 3 | `CONFIG_CAL_DURATION` | Calibration duration in seconds. |
| 4 | `CONFIG_SHAPE_THRESHOLD_BLACK` | Threshold used by shape detection. |
| 5 | `CONFIG_IR_POWER` | Startup IR emitter state. |
| 6 | `crc` | XOR checksum over config bytes 0-5. |

`set_conf_value` writes the new value and saves the config immediately.
Both commands reject indices outside `0..6`; `set_conf_value` also rejects
values outside the byte range `0..255`.


## Example Python Usage

The exact Python call style depends on the host-side uRemote library, but usage is intentionally command-name based:

```python
from uremote import uRemote

remote = uRemote("COM7", baudrate=115200)

print(remote.call("get_version"))
remote.call("set_mode_cal")
print(remote.call("all"))

remote.call("calibrate", 1)   # calibrate and save afterward
print(remote.call("is_calibrated"))

remote.call("set_conf_value", 4, 100)  # shape threshold
print(remote.call("get_conf_value", 4))
print(remote.call("get_config"))

print(remote.call("get_uid"))
```

## Notes For Maintainers

- Keep `lib/uRemote` protocol code unchanged unless the wire protocol itself is being changed.
- Keep `uart1_driver.*` unchanged unless the hardware UART implementation needs work.
- Add application commands in `LineSensor.ino` through `handleRemote()`.
- When adding an I2C-style command, keep the uRemote name lower-case and remove the `CMD_` prefix.
- Keep UART1 limited to framed uRemote traffic; send debug text through USB CDC `Serial`.
