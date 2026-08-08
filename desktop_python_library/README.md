# Python USB uRemote library

This directory contains a desktop Python adaptation of the
[AntonsMindstorms `uremote.py`](https://github.com/AntonsMindstorms/uRemote/blob/main/library/uremote.py)
library. It retains the upstream uRemote protocol and `call()` API while using
`pyserial` to communicate with the line sensor's USB serial port on Windows or
Linux.

## Install

Python 3.9 or newer is recommended. From this directory, install the only
dependency:

```text
python -m pip install -r requirements.txt
```

Close the web dashboard and any serial terminal first. Only one application can
normally open the sensor's USB serial port at a time.

On Linux, if opening `/dev/ttyACM*` or `/dev/ttyUSB*` is denied, add your user to
the distribution's serial-port group (commonly `dialout`) and then sign out and
back in.

## Run the example

```text
python read_line_sensor.py
```

The example displays all detected serial/USB ports and asks which one to use.
It then prints the eight sensor values, scaled line position, minimum, maximum,
and detected shape every 250 ms.

You can also supply a port directly:

```text
python read_line_sensor.py --port COM5 --mode raw
python read_line_sensor.py --port /dev/ttyACM0 --mode calibrated
```

## Use the library

```python
from uremote import URemote, select_serial_port

port = select_serial_port()
with URemote(port) as sensor:
    packet = sensor.call("all")
    values = list(packet[:8])
    print(values)
```

`call()` follows the original library convention: no returned values become
`None`, one value is returned directly, and multiple values are returned as a
tuple. Transport errors, invalid replies, and remote command errors raise
`uRemoteError`.

