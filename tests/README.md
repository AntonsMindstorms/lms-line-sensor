# Tests

The suite runs on a normal computer with CPython; no hardware is needed.

```bash
git submodule update --init   # uRemote lives in micropython/vendor/uRemote
python -m pip install pytest
python -m pytest
```

## How it works

The drivers import modules that only exist on MicroPython boards and Pybricks
hubs (`machine`, `pybricks.*`, `time.ticks_ms`). `conftest.py` installs fakes
for them, and [`fakes.py`](fakes.py) provides the pieces of a virtual bench:

| Fake | Stands in for |
| --- | --- |
| `FakeLineSensor` | The sensor firmware on the I2C bus, following the command table in [`firmware/README.md`](../firmware/README.md) |
| `FakeUART` | One end of a UART/USB wire (MicroPython `UART`, Pybricks `UARTDevice`, pyserial) |
| `Clock` | A manual clock: sleeping advances it, so timeouts run instantly |

Every test gets a fresh `bench`. The `device` fixture is its simulated sensor.

## What is covered

| File | Subject |
| --- | --- |
| `test_base.py` | Constants and the shared high-level API in `BaseLineSensor` |
| `test_i2c_driver.py` | `LineSensorI2C` against the simulated firmware |
| `test_ur_client.py` | `LineSensorUR`: command names, decoding, calibration flow |
| `test_shared_contract.py` | Both drivers keep the documented common API |
| `test_uremote_protocol.py` | uRemote framing, run against all three implementations (submodule library, bundled Pybricks client, desktop client) |
| `test_async.py` | `LineSensorUR` inside Pybricks `run_task()`: awaitable calls, deferred config read, concurrent tasks |
| `test_bundle_tool.py`, `test_pybricks_bundle.py` | The Pybricks bundle generator and its output |
| `test_ur_server.py` | `LineSensorURServer` commands, validation and wire handling |
| `test_end_to_end.py` | Hub driver → UART → server → I2C → simulated sensor |
| `test_read_line_sensor.py` | The desktop `usb/read_line_sensor.py` script |
| `test_repository.py` | Firmware version, Markdown links, compile warnings, example imports |

## Regenerating the Pybricks bundle

`test_pybricks_bundle.py` fails when `micropython/line_sensor_pybricks.py` is
out of date with `micropython/line_sensor.py`. Regenerate it with:

```bash
python tools/generate_line_sensor_pybricks.py
```
