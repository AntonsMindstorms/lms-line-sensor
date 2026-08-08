LMS Line Sensor uRemote API
===========================

| Firmware reference: **5.5**
| UART speed: **115200 baud**
| USB product: **Line Sensor uRemote**

Transports
----------

The same named uRemote API is available through:

- UART at 115200 baud.
- Native USB CDC with VID ``0xCAFE`` and PID ``0x4001``.

Both transports carry framed uRemote traffic only. They do not provide an
unframed text console. Use ``debug_status`` and ``last_commands`` for explicit
diagnostics.

Only one application should open the USB serial port at a time.

Calling commands from Python
----------------------------

The desktop library is in the project's ``library`` directory:

.. code-block:: python

   from uremote import URemote, select_serial_port

   with URemote(select_serial_port()) as sensor:
       packet = sensor.call("all")
       print(list(packet[:8]))

``call()`` returns ``None`` for no response values, the value directly for one
response field, or a tuple for multiple response fields. Transport, protocol,
and remote-handler failures raise ``uRemoteError``.

.. _uremote-command-reference:

Command reference
-----------------

.. list-table::
   :header-rows: 1
   :widths: 27 27 46

   * - Command
     - Arguments
     - Successful response or behavior
   * - ``ping``
     - None
     - Uptime in milliseconds
   * - ``version``, ``get_version``
     - None
     - Major and minor firmware version
   * - ``set_mode_raw``
     - None
     - Select raw mode; return mode ``0``
   * - ``set_mode_cal``
     - None
     - Select calibrated mode; return mode ``1``
   * - ``mode``
     - Optional mode ``0..3``
     - Get or set active mode
   * - ``debug``, ``debug_status``
     - Arguments ignored
     - Uptime, mode, calibrated, emitter, LED mode, I2C overflow count
   * - ``last_commands``
     - None
     - Last UART and I2C commands, parameters, and timestamps
   * - ``calibrate``
     - Optional save flag
     - Start calibration; return ``1``
   * - ``is_calibrated``
     - None
     - Calibration-active flag
   * - ``save``, ``save_cal``
     - None
     - Save calibration; return ``1``
   * - ``load``, ``load_cal``
     - None
     - Load calibration; return ``1`` or an invalid-data error
   * - ``neopixel``
     - Index, red, green, blue
     - Set pixel ``0..8``; return ``1``
   * - ``print``
     - Numeric value
     - Return the numeric value
   * - ``data``
     - None
     - Eight-byte sensor array
   * - ``pos``
     - None
     - Position byte ``0..255``
   * - ``shape``
     - None
     - ASCII shape byte
   * - ``pds``, ``pdr``
     - None
     - Position, derivative, and shape as three numeric values
   * - ``all``
     - None
     - Complete 13-byte measurement packet
   * - ``get_cal_min``
     - None
     - Eight-byte calibration-minimum array
   * - ``get_cal_max``
     - None
     - Eight-byte calibration-maximum array
   * - ``set_cal_min``
     - Eight values or one byte array
     - Set minima; return ``1``
   * - ``set_cal_max``
     - Eight values or one byte array
     - Set maxima; return ``1``
   * - ``get_conf_value``
     - Config index
     - One configuration byte
   * - ``set_conf_value``
     - Index, value
     - Change and save config; return ``1``
   * - ``get_config``
     - None
     - Seven-byte configuration array
   * - ``load_config``
     - None
     - Load config, apply emitter, return ``1``
   * - ``save_config``
     - None
     - Save config; return ``1``
   * - ``get_uid``
     - None
     - Twelve-byte UID array
   * - ``cur_mode``
     - None
     - Current sensor mode
   * - ``blackline``
     - None
     - Legacy black-line flag; polarity detection is disabled
   * - ``set_emitter``, ``emitter``
     - Off/on value
     - Set emitter; return ``1``
   * - ``leds``, ``led``
     - Optional mode ``0..3``
     - Get or set automatic LED mode

The ``debug`` command does not set a debug level. It is an alias of
``debug_status`` and returns six explicit diagnostic fields.

Measurement data
----------------

The ``all`` response uses the same 13-byte layout as a normal I2C measurement
read. See :ref:`i2c-measurement-packet` for offsets, signed conversion, and shape
values.

Examples
--------

Read device identity and firmware version:

.. code-block:: python

   uid = sensor.call("get_uid")
   major, minor = sensor.call("get_version")
   print(uid.hex().upper(), major, minor)

Read processed line data:

.. code-block:: python

   position_byte, derivative_byte, shape_byte = sensor.call("pds")
   position = position_byte - 128
   derivative = derivative_byte - 128
   shape = chr(shape_byte)

Configure calibrated operation:

.. code-block:: python

   sensor.call("set_emitter", 1)
   sensor.call("load_cal")
   sensor.call("set_mode_cal")
   values = sensor.call("data")

Set one NeoPixel manually:

.. code-block:: python

   sensor.call("leds", 0)
   sensor.call("neopixel", 0, 20, 0, 0)

Diagnostics
-----------

``debug_status`` returns:

.. list-table::
   :header-rows: 1

   * - Field
     - Meaning
   * - 0
     - Uptime in milliseconds
   * - 1
     - Current sensor mode
   * - 2
     - Calibration-active flag
   * - 3
     - Current emitter state
   * - 4
     - Current LED mode
   * - 5
     - I2C request-queue overflow count

``last_commands`` returns six values: UART command, UART parameters, UART
timestamp, I2C command, I2C parameters, and I2C timestamp. USB requests are not
recorded, so web-dashboard polling does not overwrite the trace.

uRemote frame encoding
----------------------

Normal applications use the supplied library and do not need to encode frames
directly. The wire format for another client implementation is:

.. code-block:: text

   <frame_length> <$MU <status_and_command_length> <command> [<type> <length> <data> ...]

- The first byte counts all bytes after itself.
- The upper three header bits contain reply status.
- The lower five bits contain command-name length, maximum 31 bytes.
- Status ``0`` means success; nonzero status means an error reply.
- Argument types are ``A`` byte array, ``B`` boolean, ``N`` ASCII number, and
  ``S`` UTF-8 string.
- Successful replies repeat the request command name.

