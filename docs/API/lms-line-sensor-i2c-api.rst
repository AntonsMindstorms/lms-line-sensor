LMS Line Sensor I2C API
=======================

| Firmware reference: **5.5**
| Default 7-bit slave address: **``0x33``**
| Sensor channels: **8**

Bus setup
---------

The line sensor is an I2C target and the connected controller is the I2C
controller. Use either QWIIC connector or connect SDA, SCL, 3.3 V, and ground
according to the board pinout.

MicroPython initialization example:

.. code-block:: python

   from machine import I2C, Pin

   ADDRESS = 0x33
   i2c = I2C(1, scl=Pin(4), sda=Pin(5), freq=100_000)
   print([hex(address) for address in i2c.scan()])

Transaction model
-----------------

A command write starts with the numeric command byte followed by zero or more
unsigned-byte arguments.

.. code-block:: text

   START | address + W | command | argument 0 | ... | STOP

For commands with a response, write the command and then read the documented
number of bytes:

.. code-block:: python

   i2c.writeto(ADDRESS, bytes((command, *arguments)))
   response = i2c.readfrom(ADDRESS, response_length)

The command-specific response is consumed by one read. Later reads return the
normal 13-byte measurement packet. Write-only commands are queued and executed
from the main firmware loop; they have no acknowledgement.

.. _i2c-measurement-packet:

Measurement packet
------------------

A normal I2C read returns 13 bytes.

.. list-table::
   :header-rows: 1
   :widths: 10 25 20 45

   * - Offset
     - Field
     - Encoding
     - Description
   * - 0-7
     - Sensor 0-7
     - ``0..255``
     - Eight reflectance values in the active mode
   * - 8
     - Position
     - ``0..255``
     - Signed position encoded around 128
   * - 9
     - Minimum
     - ``0..255``
     - Minimum processed sensor value
   * - 10
     - Maximum
     - ``0..255``
     - Maximum processed sensor value
   * - 11
     - Derivative
     - ``0..255``
     - Smoothed position derivative centered at 128
   * - 12
     - Shape
     - ASCII byte
     - Detected line shape

Decode signed values with:

.. code-block:: python

   signed_position = round(packet[8] * 256 / 255 - 128)
   signed_derivative = packet[11] - 128

Shape bytes are space for no recognized shape, ``|`` for straight, ``T`` for a
T intersection, ``<`` for left, ``>`` for right, and ``Y`` for a Y intersection.

Sensor modes
------------

.. list-table::
   :header-rows: 1

   * - Value
     - Mode
     - Description
   * - ``0``
     - Raw
     - Uncalibrated sensor values
   * - ``1``
     - Calibrated
     - Values normalized from calibration minima and maxima
   * - ``2``
     - Digital
     - Reserved compatibility mode; currently exposes raw values
   * - ``3``
     - Calibrating
     - Collecting new calibration limits

LED modes
---------

.. list-table::
   :header-rows: 1

   * - Value
     - Mode
     - Description
   * - ``0``
     - Off
     - Automatic sensor LEDs off
   * - ``1``
     - Normal
     - Brightness follows sensor values
   * - ``2``
     - Inverted
     - Brightness follows inverted sensor values
   * - ``3``
     - Position
     - Indicates detected line position

Setting an individual NeoPixel enables manual LED control. Send ``CMD_LEDS`` to
return to automatic LED rendering.

Command reference
-----------------

.. list-table::
   :header-rows: 1
   :widths: 7 25 25 43

   * - ID
     - Command
     - Arguments
     - Response or behavior
   * - 0
     - ``CMD_SET_MODE_RAW``
     - None
     - Select raw mode; no command reply
   * - 1
     - ``CMD_SET_MODE_CAL``
     - None
     - Select calibrated mode; no command reply
   * - 2
     - ``CMD_GET_VERSION``
     - None
     - Two bytes: major, minor
   * - 3
     - ``CMD_DEBUG``
     - Optional legacy level
     - Reserved no-op; no command reply
   * - 4
     - ``CMD_CALIBRATE``
     - Optional save flag
     - Start calibration; no command reply
   * - 5
     - ``CMD_IS_CALIBRATED``
     - None
     - One byte: ``0`` or ``1``
   * - 6
     - ``CMD_LOAD_CAL``
     - None
     - Load calibration; no command reply
   * - 7
     - ``CMD_SAVE_CAL``
     - None
     - Save calibration; no command reply
   * - 8
     - ``CMD_GET_CAL_MIN``
     - None
     - Eight minimum bytes
   * - 9
     - ``CMD_GET_CAL_MAX``
     - None
     - Eight maximum bytes
   * - 10
     - ``CMD_SET_CAL_MIN``
     - Eight values
     - Update minima; no command reply
   * - 11
     - ``CMD_SET_CAL_MAX``
     - Eight values
     - Update maxima; no command reply
   * - 12
     - ``CMD_NEOPIXEL``
     - Index, red, green, blue
     - Set pixel ``0..8``; no command reply
   * - 13
     - ``CMD_LEDS``
     - Mode ``0..3``
     - Select automatic LED mode; no command reply
   * - 14
     - ``CMD_SET_EMITTER``
     - Off/on byte
     - Set IR emitter; no command reply
   * - 15
     - ``CMD_GET_CONF_VALUE``
     - Config index
     - One config byte; invalid index returns ``0``
   * - 16
     - ``CMD_SET_CONF_VALUE``
     - Index, value
     - Change and save config; no command reply
   * - 17
     - ``CMD_GET_CONFIG``
     - None
     - Seven configuration bytes
   * - 18
     - ``CMD_LOAD_CONFIG``
     - None
     - Load config and apply emitter; no command reply
   * - 19
     - ``CMD_SAVE_CONFIG``
     - None
     - Save config; no command reply
   * - 20
     - Legacy
     - None
     - Do not use
   * - 21
     - Legacy
     - None
     - Do not use
   * - 22
     - ``CMD_UART_TEST``
     - None
     - I2C-only UART loopback: ``1`` pass, ``0`` fail
   * - 23
     - Unassigned
     - None
     - Rejected
   * - 24
     - ``CMD_GET_UID``
     - None
     - Twelve UID bytes

Configuration structure
-----------------------

.. list-table::
   :header-rows: 1

   * - Index
     - Field
     - Meaning
   * - 0
     - Firmware major version
     - Firmware-managed
   * - 1
     - Firmware minor version
     - Firmware-managed
   * - 2
     - Load calibration at startup
     - ``0`` off, ``1`` on
   * - 3
     - Calibration duration
     - Seconds
   * - 4
     - Shape threshold
     - ``0..255``
   * - 5
     - IR emitter at startup
     - ``0`` off, nonzero on
   * - 6
     - CRC
     - XOR over bytes 0-5; generated when saving

Loading configuration applies the stored emitter state. Saving recalculates the
CRC. Recommended writable fields are indices 2-5.

Examples
--------

Select calibrated mode and read measurements:

.. code-block:: python

   i2c.writeto(ADDRESS, bytes([1]))
   packet = i2c.readfrom(ADDRESS, 13)
   values = tuple(packet[:8])
   position = packet[8] - 128

Read firmware version:

.. code-block:: python

   i2c.writeto(ADDRESS, bytes([2]))
   major, minor = i2c.readfrom(ADDRESS, 2)

UART loopback production test
-----------------------------

``CMD_UART_TEST`` is available only through I2C. Connect UART TX (PA9) to UART
RX (PA10) with a test wire. The firmware clears UART RX, sends a valid uRemote
``test`` frame, waits up to 50 ms, and compares every received byte.

The test runs in the main loop. Wait at least 100 ms between writing command 22
and reading its result:

.. code-block:: python

   from time import sleep_ms

   i2c.writeto(ADDRESS, bytes([22]))
   sleep_ms(100)
   passed = i2c.readfrom(ADDRESS, 1)[0] == 1

A missing jumper, mismatch, incomplete frame, or timeout returns ``0``.

