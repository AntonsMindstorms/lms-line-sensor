LMS Line Sensor uRemote API
===========================

| **Firmware:** uRemote Line Sensor 5.4
| **Transport:** UART using the uRemote RPC protocol
| **UART speed:** 115200 baud
| **Sensor channels:** 8
| **Primary client:** Pybricks hub

This document describes the uRemote commands implemented by the supplied
LMS Line Sensor firmware and shows how to call them from Pybricks.

--------------

.. _1-overview:

1. Overview
-----------

The firmware runs a uRemote server on ``USART1``:

.. code:: cpp

   USART1Stream SerialA;
   uRemote remote(SerialA, handleRemote);
   ...
   SerialA.begin(115200);

A Pybricks hub acts as the client and invokes named commands:

.. code:: python

   result = ur.call("command_name", argument1, argument2)

The call is synchronous: the hub sends one request and waits for the
corresponding response.

Required files
~~~~~~~~~~~~~~

Copy the current ``uremote.py`` library into the Pybricks project. The
hub firmware must provide:

.. code:: python

   from pybricks.iodevices import UARTDevice

Create one shared ``uRemote`` object for the program:

.. code:: python

   from pybricks.parameters import Port
   from uremote import uRemote

   ur = uRemote(Port.C, baudrate=115200)

..

   The port is only an example. Use the port to which the sensor UART is
   connected.

--------------

.. _2-wiring:

2. Wiring
---------

Connect the hub UART and sensor UART with crossed transmit and receive
lines and a common ground.

========== =============
Hub signal Sensor signal
========== =============
Hub TX     Sensor RX
Hub RX     Sensor TX
GND        GND
========== =============

Typical Powered Up UART pins are:

============= ==================
Connector pin Signal
============= ==================
3             GND
4             3.3 V
5             Hub TX / sensor RX
6             Hub RX / sensor TX
============= ==================

Both UART data lines use 3.3 V logic.

The current uRemote Python library may initialize ``UARTDevice`` with a
nonzero ``power_pin``. Only use port power when the sensor board and
wiring are designed for it. Otherwise initialize the client with the
appropriate safe power setting for the hardware and firmware being used.

--------------

.. _3-basic-pybricks-connection-test:

3. Basic Pybricks connection test
---------------------------------

.. code:: python

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

Expected firmware version for the supplied source:

.. code:: text

   5.4

--------------

.. _4-uremote-wire-protocol:

4. uRemote wire protocol
------------------------

Applications normally use ``ur.call()`` and do not need to construct
frames manually.

Each frame has this form:

.. code:: text

   <total-length> <$MU> <header> <command> [typed arguments...]

Frame fields
~~~~~~~~~~~~

+------------------+------------+------------------------------------+
| Field            | Size       | Description                        |
+==================+============+====================================+
| ``total-length`` | 1 byte     | Number of bytes after the length   |
|                  |            | byte, including the four-byte      |
|                  |            | preamble                           |
+------------------+------------+------------------------------------+
| ``preamble``     | 4 bytes    | Fixed byte sequence ``<$MU``       |
+------------------+------------+------------------------------------+
| ``header``       | 1 byte     | Upper 3 bits contain status; lower |
|                  |            | 5 bits contain command-name length |
+------------------+------------+------------------------------------+
| ``command``      | 0–31 bytes | UTF-8 command name                 |
+------------------+------------+------------------------------------+
| ``arguments``    | variable   | Typed values                       |
+------------------+------------+------------------------------------+

The maximum complete frame length is 255 bytes. Command names are
limited to 31 bytes.

Status values
~~~~~~~~~~~~~

====== ==============================
Status Meaning
====== ==============================
``0``  Successful request or response
``1``  Error response
====== ==============================

Supported argument types
~~~~~~~~~~~~~~~~~~~~~~~~

=========== ================ ========================
Python type Wire type        Encoding
=========== ================ ========================
``int``     ``N`` (``0x4E``) UTF-8 decimal text
``str``     ``S`` (``0x53``) UTF-8 text
``bool``    ``B`` (``0x42``) One byte, ``0`` or ``1``
``bytes``   ``A`` (``0x41``) Raw byte array
=========== ================ ========================

On success, ``ur.call()`` returns:

================= ===================
Response contents Python result
================= ===================
No values         ``None``
One value         That value directly
Multiple values   A tuple
================= ===================

Byte-array responses are returned as ``bytes``.

--------------

.. _5-operating-modes:

5. Operating modes
------------------

+------------------+-------+-----------------------------------------+
| Mode             | Value | Description                             |
+==================+=======+=========================================+
| Raw              | ``0`` | Returns ADC-derived sensor values       |
+------------------+-------+-----------------------------------------+
| Calibrated       | ``1`` | Returns values normalized using stored  |
|                  |       | calibration limits                      |
+------------------+-------+-----------------------------------------+
| Digital/reserved | ``2`` | Defined by the companion firmware       |
|                  |       | headers but not used by this            |
|                  |       | implementation                          |
+------------------+-------+-----------------------------------------+
| Calibrating      | ``3`` | Internal timed calibration mode         |
+------------------+-------+-----------------------------------------+

Use raw and calibrated mode through the dedicated commands:

.. code:: python

   ur.call("set_mode_raw")
   ur.call("set_mode_cal")

The generic ``mode`` command does not validate the supplied value, so
normal clients should only set ``0`` or ``1``.

--------------

.. _6-sensor-data-encoding:

6. Sensor data encoding
-----------------------

The firmware maintains a 13-byte measurement record.

====== ========== =========== =======================================
Index  Name       Encoding    Description
====== ========== =========== =======================================
``0``  Sensor 0   ``0..255``  First reflectance channel
``1``  Sensor 1   ``0..255``  Reflectance channel
``2``  Sensor 2   ``0..255``  Reflectance channel
``3``  Sensor 3   ``0..255``  Reflectance channel
``4``  Sensor 4   ``0..255``  Reflectance channel
``5``  Sensor 5   ``0..255``  Reflectance channel
``6``  Sensor 6   ``0..255``  Reflectance channel
``7``  Sensor 7   ``0..255``  Last reflectance channel
``8``  Position   Offset byte Signed position is ``byte - 128``
``9``  Minimum    ``0..255``  Minimum of the eight processed channels
``10`` Maximum    ``0..255``  Maximum of the eight processed channels
``11`` Derivative Offset byte Signed derivative is ``byte - 128``
``12`` Shape      ASCII byte  Detected line shape
====== ========== =========== =======================================

Reflectance direction
~~~~~~~~~~~~~~~~~~~~~

The firmware comments define:

.. code:: text

   white = 255
   black = 0

Raw values depend on the sensor electronics and surface. Calibrated mode
maps each channel using its calibration minimum and maximum.

Position
~~~~~~~~

Position is transported as an unsigned byte for protocol compatibility:

.. code:: python

   signed_position = position_byte - 128

+--------------+------------------+----------------------------------+
| Encoded byte | Decoded position | Meaning                          |
+==============+==================+==================================+
| ``1``        | ``-127``         | Far to one side                  |
+--------------+------------------+----------------------------------+
| ``128``      | ``0``            | Centered, or neutral when no     |
|              |                  | line is detected                 |
+--------------+------------------+----------------------------------+
| ``255``      | ``127``          | Far to the other side            |
+--------------+------------------+----------------------------------+

The physical left/right sign depends on sensor orientation.

Derivative
~~~~~~~~~~

Derivative also uses an offset of 128:

.. code:: python

   signed_derivative = derivative_byte - 128

A result near zero means little lateral movement. The firmware smooths
the result and calculates it over a sample history, so the first
readings after startup are normally neutral.

Shape characters
~~~~~~~~~~~~~~~~

======= ========= ======================
Byte    Character Meaning
======= ========= ======================
``32``  space     No line detected
``124`` \`        \`
``84``  ``T``     T intersection
``60``  ``<``     Left branch or corner
``62``  ``>``     Right branch or corner
``89``  ``Y``     Y intersection
======= ========= ======================

Decode a shape response with:

.. code:: python

   shape = chr(shape_byte)

--------------

.. _7-complete-command-summary:

7. Complete command summary
---------------------------

+----------------+----------------+----------------+----------------+
| Command        | Arguments      | Return value   | Description    |
+================+================+================+================+
| ``ping``       | none           | uptime in ms   | Protocol and   |
|                |                |                | connection     |
|                |                |                | test           |
+----------------+----------------+----------------+----------------+
| ``add``        | ``a``, ``b``   | ``a + b``      | Numeric        |
|                |                |                | protocol       |
|                |                |                | self-test      |
+----------------+----------------+----------------+----------------+
| ``version``    | none           | ``(m           | Firmware       |
|                |                | ajor, minor)`` | version        |
+----------------+----------------+----------------+----------------+
| ``get_version``| none           | ``(m           | Alias of       |
|                |                | ajor, minor)`` | ``version``    |
+----------------+----------------+----------------+----------------+
| ``set_mode_raw``  | none           | mode ``0``     | Select raw     |
|                |                |                | mode           |
+----------------+----------------+----------------+----------------+
| ``set_mode_cal`` | none           | mode ``1``     | Select         |
|                |                |                | calibrated     |
|                |                |                | mode           |
+----------------+----------------+----------------+----------------+
| ``mode``       | optional mode  | active mode    | Get or set     |
|                |                |                | mode           |
+----------------+----------------+----------------+----------------+
| ``cur_mode``   | none           | active mode    | Read current   |
|                |                |                | mode           |
+----------------+----------------+----------------+----------------+
| ``debug``      | log level      | active level   | Set USB/debug  |
|                |                |                | log level      |
+----------------+----------------+----------------+----------------+
| ``calibrate``  | optional save  | ``1``          | Start timed    |
|                | flag           |                | calibration    |
+----------------+----------------+----------------+----------------+
| ``is_calibrated`` | none           | ``0`` or ``1`` | Cali           |
|                |                |                | bration-active |
|                |                |                | flag           |
+----------------+----------------+----------------+----------------+
| ``save``       | none           | ``1``          | Save           |
|                |                |                | calibration to |
|                |                |                | EEPROM         |
+----------------+----------------+----------------+----------------+
| ``save_cal``   | none           | ``1``          | Alias of       |
|                |                |                | ``save``       |
+----------------+----------------+----------------+----------------+
| ``load``       | none           | ``1``          | Load           |
|                |                |                | calibration    |
|                |                |                | from EEPROM    |
+----------------+----------------+----------------+----------------+
| ``load_cal``   | none           | ``1``          | Alias of       |
|                |                |                | ``load``       |
+----------------+----------------+----------------+----------------+
| ``data``       | none           | 8-byte array   | Eight sensor   |
|                |                |                | channels       |
+----------------+----------------+----------------+----------------+
| ``pos``        | none           | position byte  | Encoded        |
|                |                |                | position only  |
+----------------+----------------+----------------+----------------+
| ``shape``      | none           | shape byte     | ASCII shape    |
|                |                |                | byte only      |
+----------------+----------------+----------------+----------------+
| ``pds``        | none           | ``(po          | Compact        |
|                |                | sition, deriva | control-loop   |
|                |                | tive, shape)`` | response       |
+----------------+----------------+----------------+----------------+
| ``pdr``        | none           | same as        | Compatibility  |
|                |                | ``pds``        | alias          |
+----------------+----------------+----------------+----------------+
| ``all``        | none           | 13-byte array  | Complete       |
|                |                |                | measurement    |
|                |                |                | record         |
+----------------+----------------+----------------+----------------+
| ``get_min``    | none           | 8-byte array   | Calibration    |
|                |                |                | minima         |
+----------------+----------------+----------------+----------------+
| ``get_max``    | none           | 8-byte array   | Calibration    |
|                |                |                | maxima         |
+----------------+----------------+----------------+----------------+
| ``set_min``    | 8 numbers or   | ``1``          | Set            |
|                | one byte array |                | calibration    |
|                |                |                | minima         |
+----------------+----------------+----------------+----------------+
| ``set_max``    | 8 numbers or   | ``1``          | Set            |
|                | one byte array |                | calibration    |
|                |                |                | maxima         |
+----------------+----------------+----------------+----------------+
| ``get_value``  | config index   | byte value     | Read one       |
|                |                |                | configuration  |
|                |                |                | byte           |
+----------------+----------------+----------------+----------------+
| ``set_value``  | index, value   | ``1``          | Set and        |
|                |                |                | immediately    |
|                |                |                | save one       |
|                |                |                | configuration  |
|                |                |                | byte           |
+----------------+----------------+----------------+----------------+
| ``show_config``              | none           | configuration  | Return         |
|                |                | bytes          | complete       |
|                |                |                | configuration  |
|                |                |                | structure      |
+----------------+----------------+----------------+----------------+
| ``load_config``| none           | ``1``          | Load           |
|                 |               |                | configuration, |
|                |                |                | or restore     |
|                |                |                | defaults if    |
|                |                |                | invalid        |
+----------------+----------------+----------------+----------------+
| ``save_config``| none           | ``1``          | Save           |
|                |                | configuration  |
|                |                |                | to EEPROM      |
+----------------+----------------+----------------+----------------+
| ``set_emitter`` | bool or number | ``1``          | Set IR emitter |
|                  |                |                | state          |
+----------------+----------------+----------------+----------------+
| ``emitter``    | bool or number | ``1``          | Alias of       |
|                |                |                | `              |
|                |                |                | `set_emitter`` |
+----------------+----------------+----------------+----------------+
| ``leds``       | optional mode  | active LED     | Get or set     |
|                |                | mode           | automatic LED  |
|                |                |                | display mode   |
+----------------+----------------+----------------+----------------+
| ``led``        | optional mode  | active LED     | Alias of       |
|                |                | mode           | ``leds``       |
+----------------+----------------+----------------+----------------+
| ``neopixel``   | index, red,    | ``1``          | Set one        |
|                | green, blue    |                | onboard RGB    |
|                |                |                | LED            |
+----------------+----------------+----------------+----------------+
| ``get_uid``    | none           | 12-byte array  | Read CH32V203  |
|                |                |                | unique ID      |
+----------------+----------------+----------------+----------------+
| ``blackline``  | none           | ``0`` or ``1`` | Return the     |
|                |                |                | firmware's     |
|                |                |                | black-line     |
|                |                |                | flag           |
+----------------+----------------+----------------+----------------+
| ``print``      | numeric value  | same value     | Numeric echo   |
|                |                |                | helper         |
+----------------+----------------+----------------+----------------+

--------------

.. _8-command-reference:

8. Command reference
--------------------

.. _81-ping:

8.1 ``ping``
~~~~~~~~~~~~

Returns the firmware ``millis()`` counter.

.. code:: python

   uptime_ms = ur.call("ping")
   print(uptime_ms)

This is the best first command for testing communication.

--------------

.. _82-add:

8.2 ``add``
~~~~~~~~~~~

Adds two numeric arguments.

.. code:: python

   answer = ur.call("add", 20, 22)
   print(answer)  # 42

The command reports an error when fewer than two arguments are supplied.

--------------

.. _83-version--get_version:

8.3 ``version`` / ``get_version``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Returns two numeric response fields.

.. code:: python

   major, minor = ur.call("get_version")
   print("{}.{}".format(major, minor))

--------------

.. _84-set_mode_raw:

8.4 ``set_mode_raw``
~~~~~~~~~~~~~~~~~~~~

Selects raw sensor data.

.. code:: python

   mode = ur.call("set_mode_raw")
   assert mode == 0

--------------

.. _85-set_mode_cal:

8.5 ``set_mode_cal``
~~~~~~~~~~~~~~~~~~~~

Selects calibrated sensor data.

.. code:: python

   mode = ur.call("set_mode_cal")
   assert mode == 1

Calibration values should be valid before using this mode.

--------------

.. _86-mode:

8.6 ``mode``
~~~~~~~~~~~~

Reads or changes the active mode.

.. code:: python

   current = ur.call("mode")
   print(current)

   current = ur.call("mode", 1)
   print(current)

Prefer ``set_mode_raw`` and ``set_mode_cal`` for normal operation.

--------------

.. _87-cur_mode:

8.7 ``cur_mode``
~~~~~~~~~~~~~~~~

Returns the active mode without accepting an argument.

.. code:: python

   current = ur.call("cur_mode")

--------------

.. _88-debug:

8.8 ``debug``
~~~~~~~~~~~~~

Sets the firmware debug-log threshold.

===== ===========
Level Name
===== ===========
``0`` Error
``1`` Warning
``2`` Information
``3`` Debug
``4`` Verbose
===== ===========

.. code:: python

   active_level = ur.call("debug", 0)

Debug output is written to the firmware's ``Serial`` interface. The
source deliberately avoids writing unframed debug text to the uRemote
UART.

--------------

.. _89-calibrate:

8.9 ``calibrate``
~~~~~~~~~~~~~~~~~

Starts calibration and automatically stops after the configured
duration.

.. code:: python

   ur.call("calibrate")

Pass a nonzero save flag to save the new limits automatically when
calibration stops:

.. code:: python

   ur.call("calibrate", 1)

During calibration:

-  The IR emitter is enabled.
-  Sensor LED display is turned off.
-  Raw minimum and maximum values are collected.
-  The blue calibration indicator flashes.
-  The previous mode and LED mode are restored when calibration ends.

The duration is read from configuration index ``3``.

--------------

.. _810-is_calibrated:

8.10 ``is_calibrated``
~~~~~~~~~~~~~~~~~~~~~~

.. code:: python

   calibrated = bool(ur.call("is_calibrated"))

This indicates that calibration limits are active in RAM. It does not
prove that the limits cover the full black/white range correctly.

--------------

.. _811-save--save_cal:

8.11 ``save`` / ``save_cal``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Stores the current eight minimum and eight maximum calibration values in
EEPROM.

.. code:: python

   ur.call("save_cal")

The firmware only writes calibration data when ``is_calibrated`` is
true.

--------------

.. _812-load--load_cal:

8.12 ``load`` / ``load_cal``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Loads calibration values from EEPROM and marks the sensor calibrated.

.. code:: python

   ur.call("load_cal")

--------------

.. _813-data:

8.13 ``data``
~~~~~~~~~~~~~

Returns only the eight current sensor channel bytes.

.. code:: python

   values = ur.call("data")
   print(tuple(values))

The returned type is ``bytes``. Values come from the currently selected
mode.

--------------

.. _814-pos:

8.14 ``pos``
~~~~~~~~~~~~

Returns one encoded position value.

.. code:: python

   position = ur.call("pos") - 128

--------------

.. _815-shape:

8.15 ``shape``
~~~~~~~~~~~~~~

Returns one ASCII shape byte.

.. code:: python

   shape = chr(ur.call("shape"))

--------------

.. _816-pds--pdr:

8.16 ``pds`` / ``pdr``
~~~~~~~~~~~~~~~~~~~~~~

Returns position, derivative, and shape as three numeric response
fields.

.. code:: python

   position_byte, derivative_byte, shape_byte = ur.call("pds")

   position = position_byte - 128
   derivative = derivative_byte - 128
   shape = chr(shape_byte)

This is the recommended command for a fast line-following control loop
because it transfers only the processed fields required by the
controller.

--------------

.. _817-all:

8.17 ``all``
~~~~~~~~~~~~

Returns the complete 13-byte measurement record.

.. code:: python

   record = ur.call("all")

   sensors = tuple(record[0:8])
   position = record[8] - 128
   minimum = record[9]
   maximum = record[10]
   derivative = record[11] - 128
   shape = chr(record[12])

--------------

.. _818-get_min--get_max:

8.18 ``get_min`` / ``get_max``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: python

   minimum = tuple(ur.call("get_min"))
   maximum = tuple(ur.call("get_max"))

Each response contains eight bytes.

--------------

.. _819-set_min--set_max:

8.19 ``set_min`` / ``set_max``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These commands accept either eight separate numeric arguments:

.. code:: python

   ur.call("set_min", 10, 11, 12, 13, 14, 15, 16, 17)
   ur.call("set_max", 220, 221, 222, 223, 224, 225, 226, 227)

or one packed byte array:

.. code:: python

   minimum = bytes((10, 11, 12, 13, 14, 15, 16, 17))
   maximum = bytes((220, 221, 222, 223, 224, 225, 226, 227))

   ur.call("set_min", minimum)
   ur.call("set_max", maximum)

The firmware marks calibration active after both arrays have been
supplied. Call ``save_cal`` to persist them.

--------------

.. _820-get_value:

8.20 ``get_value``
~~~~~~~~~~~~~~~~~~

Reads one byte from the configuration structure.

.. code:: python

   calibration_seconds = ur.call("get_value", 3)

See the configuration table below.

--------------

.. _821-set_value:

8.21 ``set_value``
~~~~~~~~~~~~~~~~~~

Changes one configuration byte and immediately saves the complete
configuration to EEPROM.

.. code:: python

   ur.call("set_value", 3, 7)  # calibration duration = 7 seconds

Use valid byte values only. Avoid unnecessary repeated writes because
this command writes EEPROM on every successful call.

--------------

.. _822-show_config:

8.22 ``show_config``
~~~~~~~~~~~~~~~~~~~~

Returns the complete raw configuration structure as a byte array.

.. code:: python

   raw = ur.call("show_config")
   print(tuple(raw))

It also invokes the firmware's debug-side configuration print function.

--------------

.. _823-load_config:

8.23 ``load_config``
~~~~~~~~~~~~~~~~~~~~

Loads configuration from EEPROM. If validation fails, firmware defaults
are restored and saved.

.. code:: python

   ur.call("load_config")

The configured emitter state is applied after loading.

--------------

.. _824-save_config:

8.24 ``save_config``
~~~~~~~~~~~~~~~~~~~~

.. code:: python

   ur.call("save_config")

This is normally unnecessary directly after ``set_value``, because
``set_value`` already saves.

--------------

.. _825-set_emitter--emitter:

8.25 ``set_emitter`` / ``emitter``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Controls the IR emitter.

.. code:: python

   ur.call("emitter", True)
   ur.call("emitter", False)

Numeric values also work:

.. code:: python

   ur.call("set_emitter", 1)

--------------

.. _826-leds--led:

8.26 ``leds`` / ``led``
~~~~~~~~~~~~~~~~~~~~~~~

Gets or sets the automatic sensor LED display mode.

=============== ===== =================================
Mode            Value Description
=============== ===== =================================
Off             ``0`` Clear the LEDs
Values          ``1`` Display channel intensity
Inverted values ``2`` Display inverse channel intensity
Position        ``3`` Display detected line position
=============== ===== =================================

.. code:: python

   active_mode = ur.call("leds", 3)
   print(active_mode)

Read the current mode without changing it:

.. code:: python

   active_mode = ur.call("leds")

The firmware limits physical NeoPixel refreshes to at most 10 Hz.

--------------

.. _827-neopixel:

8.27 ``neopixel``
~~~~~~~~~~~~~~~~~

Sets one RGB LED.

.. code:: python

   ur.call("neopixel", 0, 20, 0, 0)

Valid indices are ``0..8``: eight sensor LEDs and one calibration-status
LED. RGB values are bytes in the range ``0..255``.

An out-of-range index is ignored, but the firmware still returns
success.

Automatic LED rendering may overwrite manually selected colors while an
automatic LED mode is active. Set LED mode to off before manual control:

.. code:: python

   ur.call("leds", 0)
   ur.call("neopixel", 0, 20, 0, 0)

--------------

.. _828-get_uid:

8.28 ``get_uid``
~~~~~~~~~~~~~~~~

Returns the 12-byte CH32V203 device UID.

.. code:: python

   uid = ur.call("get_uid")
   uid_hex = "".join("{:02X}".format(value) for value in uid)
   print(uid_hex)

--------------

.. _829-blackline:

8.29 ``blackline``
~~~~~~~~~~~~~~~~~~

Returns the internal black-line detection flag.

.. code:: python

   black_line = bool(ur.call("blackline"))

**Firmware 5.4 caveat:** automatic line-type detection is not run when
normal calibration stops because the call is commented out in
``stopCalibration()``. The value can therefore remain at its initial
value or reflect an earlier loaded calibration. Do not use this command
as the sole source of truth unless the firmware behavior is updated or
independently verified.

--------------

.. _830-print:

8.30 ``print``
~~~~~~~~~~~~~~

Numeric echo command:

.. code:: python

   value = ur.call("print", 123)

Despite its name, it is not a general remote print function. The
firmware converts the first argument to an integer and returns it.

--------------

.. _9-configuration-structure:

9. Configuration structure
--------------------------

The configuration consists of seven bytes.

+-------+-------------------+-------------------+-------------------+
| Index | Field             | Default in        | Description       |
|       |                   | firmware 5.4      |                   |
+=======+===================+===================+===================+
| ``0`` | Major version     | ``5``             | Configuration     |
|       |                   |                   | compatibility     |
|       |                   |                   | major version     |
+-------+-------------------+-------------------+-------------------+
| ``1`` | Minor version     | ``4``             | Configuration     |
|       |                   |                   | compatibility     |
|       |                   |                   | minor version     |
+-------+-------------------+-------------------+-------------------+
| ``2`` | Load calibration  | ``0``             | Load EEPROM       |
|       | at startup        |                   | calibration and   |
|       |                   |                   | enter calibrated  |
|       |                   |                   | mode when ``1``   |
+-------+-------------------+-------------------+-------------------+
| ``3`` | Calibration       | firmware          | Calibration time  |
|       | duration          | ``CAL_TIME``      | in seconds        |
+-------+-------------------+-------------------+-------------------+
| ``4`` | Shape black       | firmware          | Per-channel       |
|       | threshold         | ``                | threshold used    |
|       |                   | THRESHOLD_BLACK`` | for shape mask    |
+-------+-------------------+-------------------+-------------------+
| ``5`` | IR power at       | ``0``             | Emitter state     |
|       | startup           |                   | restored at       |
|       |                   |                   | startup           |
+-------+-------------------+-------------------+-------------------+
| ``6`` | CRC               | calculated        | XOR checksum over |
|       |                   |                   | indices ``0..5``  |
+-------+-------------------+-------------------+-------------------+

Read all fields:

.. code:: python

   config = ur.call("show_config")

   print("major:", config[0])
   print("minor:", config[1])
   print("load calibration:", config[2])
   print("calibration duration:", config[3])
   print("shape threshold:", config[4])
   print("IR startup power:", config[5])
   print("CRC:", config[6])

Recommended writable indexes are ``2..5``. Treat version fields and CRC
as firmware-managed values.

Configure calibrated startup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: python

   ur.call("set_value", 2, 1)

Configure calibration duration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: python

   ur.call("set_value", 3, 7)

Configure shape threshold
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: python

   ur.call("set_value", 4, 100)

Enable emitter after startup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: python

   ur.call("set_value", 5, 1)

--------------
