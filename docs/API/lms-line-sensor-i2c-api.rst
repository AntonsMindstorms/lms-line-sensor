LMS Line Sensor I2C API
=======================

| Firmware reference: **3.87**
| Default I2C slave address: **``0x33``**
| Two QWIIC I2C ports
| Serial debug port (115200) at TX pin of 2x3 Header.
| Sensor channels: **8**

This document describes the I2C protocol implemented by the LMS line-sensor firmware and gives MicroPython examples for an ESP32 acting as the I2C controller.

.. _1-bus-setup:

1. Bus setup
------------

The line sensor is an I2C slave. The ESP32 is the I2C controller.

- Connect the line sensor board to the LMS-ESp32v2 using a straight QWIIC 4 pin cable

When conecting to another i2C contoller:

-  Use a common ground between the ESP32 and the line sensor.
-  Use the logic voltage required by the sensor board. ESP32 GPIO is 3.3 V only.
-  The firmware uses 7-bit I2C address ``0x33`` unless compiled with ``TEST_VERSION``, in which case it uses ``0x34``.

Example ESP32 initialization:

.. code-block:: python

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

.. _2-transaction-model:

2. Transaction model
--------------------

Write-only command
~~~~~~~~~~~~~~~~~~

Send the command byte followed by any command arguments:

.. code-block:: text

   START | address + W | command | argument 0 | argument 1 | ... | STOP

MicroPython:

.. code-block:: python

   i2c.writeto(LINE_SENSOR_ADDRESS, bytes((command, *arguments)))

Command followed by a response
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Send the command and arguments, allow the slave to process them, and then read the documented response length:

.. code-block:: text

   START | address + W | command | arguments... | STOP
   START | address + R | response bytes...      | STOP

MicroPython:

.. code-block:: python

   from time import sleep_us

   i2c.writeto(LINE_SENSOR_ADDRESS, bytes((command, *arguments)))
   sleep_us(300)
   response = i2c.readfrom(LINE_SENSOR_ADDRESS, response_length)

Reading measurements
~~~~~~~~~~~~~~~~~~~~

A measurement is read without first sending a command:

.. code-block:: python

   frame = i2c.readfrom(LINE_SENSOR_ADDRESS, 13)

The returned data depends on the current operating mode:

-  Raw mode: raw 8-bit ADC values.
-  Calibrated mode: normalized sensor values.
-  Calibrating mode: raw values.

.. _3-measurement-frame:

3. Measurement frame
--------------------

Every normal measurement read returns 13 bytes.

+--------+------------+-------------------+----------------------+
| Offset | Field      | Range or encoding | Description          |
+========+============+===================+======================+
| 0      | Sensor 0   | ``0..255``        | Leftmost or first    |
|        |            |                   | detector, according  |
|        |            |                   | to board             |
|        |            |                   | orientation.         |
+--------+------------+-------------------+----------------------+
| 1      | Sensor 1   | ``0..255``        | Detector value.      |
+--------+------------+-------------------+----------------------+
| 2      | Sensor 2   | ``0..255``        | Detector value.      |
+--------+------------+-------------------+----------------------+
| 3      | Sensor 3   | ``0..255``        | Detector value.      |
+--------+------------+-------------------+----------------------+
| 4      | Sensor 4   | ``0..255``        | Detector value.      |
+--------+------------+-------------------+----------------------+
| 5      | Sensor 5   | ``0..255``        | Detector value.      |
+--------+------------+-------------------+----------------------+
| 6      | Sensor 6   | ``0..255``        | Detector value.      |
+--------+------------+-------------------+----------------------+
| 7      | Sensor 7   | ``0..255``        | Rightmost or last    |
|        |            |                   | detector, according  |
|        |            |                   | to board             |
|        |            |                   | orientation.         |
+--------+------------+-------------------+----------------------+
| 8      | Position   | ``0..255``        | Signed line position |
|        |            |                   | encoded with an      |
|        |            |                   | offset of 128.       |
+--------+------------+-------------------+----------------------+
| 9      | Minimum    | ``0..255``        | Minimum of the eight |
|        |            |                   | values used for      |
|        |            |                   | position             |
|        |            |                   | calculation.         |
+--------+------------+-------------------+----------------------+
| 10     | Maximum    | ``0..255``        | Maximum of the eight |
|        |            |                   | values used for      |
|        |            |                   | position             |
|        |            |                   | calculation.         |
+--------+------------+-------------------+----------------------+
| 11     | Derivative | ``0..255``        | Smoothed position    |
|        |            |                   | derivative, centered |
|        |            |                   | at 128.              |
+--------+------------+-------------------+----------------------+
| 12     | Shape      | ASCII byte        | Detected line shape. |
+--------+------------+-------------------+----------------------+

Position encoding
~~~~~~~~~~~~~~~~~

Convert the position byte to a signed value with:

.. code-block:: python

   signed_position = frame[8] - 128

The practical range is ``-127..127``:

-  Negative: line toward sensor 0.
-  ``0``: centered.
-  Positive: line toward sensor 7.

The encoded center value is therefore ``128``.

When no usable line is detected, the firmware also returns position ``128``. Check the shape byte or the minimum/maximum fields to distinguish a centered line from no line.

Derivative encoding
~~~~~~~~~~~~~~~~~~~

The derivative is centered at 128:

.. code-block:: python

   signed_derivative = frame[11] - 128

The value is internally scaled and clipped to ``0..255``; it is intended as a relative movement indication rather than a value in a physical unit.

Shape values
~~~~~~~~~~~~

======= ========= ================================================
Byte    Character Meaning
======= ========= ================================================
``32``  space     No line detected.
``124`` ``|``     Straight line or an otherwise unclassified line.
``84``  ``T``     T junction.
``60``  ``<``     Left L shape.
``62``  ``>``     Right L shape.
``89``  ``Y``     Y junction.
======= ========= ================================================

.. _4-command-summary:

4. Command summary
------------------

All command IDs and arguments are unsigned bytes.

+----+-------------------+-----------------+----------+-----------------+
| ID | Name              | Request after   | Response | Description     |
|    |                   | command byte    |          |                 |
+====+===================+=================+==========+=================+
| 0  | ``SET_MODE_RAW``  | None            | None     | Select raw      |
|    |                   |                 |          | measurement     |
|    |                   |                 |          | mode.           |
+----+-------------------+-----------------+----------+-----------------+
| 1  | ``SET_MODE_CAL``  | None            | None     | Select          |
|    |                   |                 |          | calibr          |
|    |                   |                 |          | ated/normalized |
|    |                   |                 |          | measurement     |
|    |                   |                 |          | mode.           |
+----+-------------------+-----------------+----------+-----------------+
| 2  | ``GET_VERSION``   | None            | 13 bytes | Bytes 0 and 1   |
|    |                   |                 |          | contain major   |
|    |                   |                 |          | and minor       |
|    |                   |                 |          | firmware        |
|    |                   |                 |          | versions.       |
|    |                   |                 |          | Remaining bytes |
|    |                   |                 |          | are zero.       |
+----+-------------------+-----------------+----------+-----------------+
| 3  | ``DEBUG``         | ``level``       | None     | Set serial log  |
|    |                   |                 |          | level:          |
|    |                   |                 |          | ``0..4``.       |
+----+-------------------+-----------------+----------+-----------------+
| 4  | ``CALIBRATE``     | Optional        | None     | Start           |
|    |                   | ``save``        |          | calibration.    |
|    |                   |                 |          | Nonzero         |
|    |                   |                 |          | ``save`` stores |
|    |                   |                 |          | calibration     |
|    |                   |                 |          | after           |
|    |                   |                 |          | completion.     |
+----+-------------------+-----------------+----------+-----------------+
| 5  |                   | None            | 13 bytes | Byte 0 is ``1`` |
|    | ``IS_CALIBRATED`` |                 |          | when            |
|    |                   |                 |          | calibration     |
|    |                   |                 |          | data is         |
|    |                   |                 |          | present,        |
|    |                   |                 |          | otherwise       |
|    |                   |                 |          | ``0``.          |
+----+-------------------+-----------------+----------+-----------------+
| 6  | ``LOAD_CAL``      | None            | None     | Load            |
|    |                   |                 |          | calibration     |
|    |                   |                 |          | minimum and     |
|    |                   |                 |          | maximum values  |
|    |                   |                 |          | from EEPROM.    |
|    |                   |                 |          | Deferred to the |
|    |                   |                 |          | main loop.      |
+----+-------------------+-----------------+----------+-----------------+
| 7  | ``SAVE_CAL``      | None            | None     | Save current    |
|    |                   |                 |          | calibration     |
|    |                   |                 |          | values to       |
|    |                   |                 |          | EEPROM.         |
|    |                   |                 |          | Deferred to the |
|    |                   |                 |          | main loop.      |
+----+-------------------+-----------------+----------+-----------------+
| 8  | ``GET_MIN``       | None            | 13 bytes | Bytes 0..7      |
|    |                   |                 |          | contain         |
|    |                   |                 |          | calibration     |
|    |                   |                 |          | minima.         |
+----+-------------------+-----------------+----------+-----------------+
| 9  | ``GET_MAX``       | None            | 13 bytes | Bytes 0..7      |
|    |                   |                 |          | contain         |
|    |                   |                 |          | calibration     |
|    |                   |                 |          | maxima.         |
+----+-------------------+-----------------+----------+-----------------+
| 10 | ``SET_MIN``       | Eight values    | None     | Set the eight   |
|    |                   |                 |          | calibration     |
|    |                   |                 |          | minima.         |
+----+-------------------+-----------------+----------+-----------------+
| 11 | ``SET_MAX``       | Eight values    | None     | Set the eight   |
|    |                   |                 |          | calibration     |
|    |                   |                 |          | maxima.         |
+----+-------------------+-----------------+----------+-----------------+
| 12 | ``NEOPIXEL``      | ``index, red    | None     | Set one         |
|    |                   | , green, blue`` |          | NeoPixel        |
|    |                   |                 |          | immediately.    |
+----+-------------------+-----------------+----------+-----------------+
| 13 | ``LEDS``          | ``mode``        | None     | Select          |
|    |                   |                 |          | automatic LED   |
|    |                   |                 |          | display mode.   |
+----+-------------------+-----------------+----------+-----------------+
| 14 | ``SET_EMITTER``   | ``level``       | None     | Set the         |
|    |                   |                 |          | optional IR     |
|    |                   |                 |          | emitter control |
|    |                   |                 |          | output low or   |
|    |                   |                 |          | high.           |
+----+-------------------+-----------------+----------+-----------------+
| 15 | ``GET_VALUE``     | ``index``       | 13 bytes | Byte 0 contains |
|    |                   |                 |          | one             |
|    |                   |                 |          | configuration   |
|    |                   |                 |          | byte.           |
+----+-------------------+-----------------+----------+-----------------+
| 16 | ``SET_VALUE``     | `               | None     | Set one         |
|    |                   | `index, value`` |          | configuration   |
|    |                   |                 |          | byte and        |
|    |                   |                 |          | schedule the    |
|    |                   |                 |          | configuration   |
|    |                   |                 |          | for saving.     |
+----+-------------------+-----------------+----------+-----------------+
| 17 | ``SHOW_CONFIG``   | None            | None     | Print           |
|    |                   |                 |          | configuration   |
|    |                   |                 |          | to the sensor's |
|    |                   |                 |          | serial console  |
|    |                   |                 |          | only.           |
+----+-------------------+-----------------+----------+-----------------+
| 18 | ``LOAD_CONFIG``   | None            | None     | Load            |
|    |                   |                 |          | configuration   |
|    |                   |                 |          | from EEPROM, or |
|    |                   |                 |          | use defaults if |
|    |                   |                 |          | invalid.        |
+----+-------------------+-----------------+----------+-----------------+
| 19 | ``SAVE_CONFIG``   | None            | None     | Save            |
|    |                   |                 |          | configuration   |
|    |                   |                 |          | to EEPROM.      |
|    |                   |                 |          | Deferred to the |
|    |                   |                 |          | main loop.      |
+----+-------------------+-----------------+----------+-----------------+
| 20 | ``GPIO_OUT``      | ``logic         | None     | Configure a     |
|    |                   | al_pin, value`` |          | test GPIO as    |
|    |                   |                 |          | output and      |
|    |                   |                 |          | write it.       |
+----+-------------------+-----------------+----------+-----------------+
| 21 | ``GPIO_IN``       | ``logical_pin`` | 1 byte   | Read a test     |
|    |                   |                 |          | GPIO. Returns   |
|    |                   |                 |          | ``0``, ``1``,   |
|    |                   |                 |          | or ``0xFF`` for |
|    |                   |                 |          | an invalid pin. |
+----+-------------------+-----------------+----------+-----------------+
| 22 | ``SERIAL_DISABLE``| None            | 1 byte   | Disable serial  |
|    |                   |                 |          | output.         |
|    |                   |                 |          | Response is     |
|    |                   |                 |          | ``1``.          |
+----+-------------------+-----------------+----------+-----------------+
| 23 | ``SERIAL_ENABLE`` | None            | 1 byte   | Enable serial   |
|    |                   |                 |          | output.         |
|    |                   |                 |          | Response is     |
|    |                   |                 |          | ``1``.          |
+----+-------------------+-----------------+----------+-----------------+
| 24 | ``GET_UID``       | None            | 12 bytes | Read the        |
|    |                   |                 |          | CH32V203 96-bit |
|    |                   |                 |          | unique ID in    |
|    |                   |                 |          | little-endian   |
|    |                   |                 |          | byte order per  |
|    |                   |                 |          | 32-bit word.    |
+----+-------------------+-----------------+----------+-----------------+

.. _5-command-details:

5. Command details
------------------

.. _51-operating-mode:

5.1 Operating mode
~~~~~~~~~~~~~~~~~~

.. _set_mode_raw--command-0:

``SET_MODE_RAW`` — command 0
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Request:  [0]
   Response: none

The next normal 13-byte read returns raw values.

.. _set_mode_cal--command-1:

``SET_MODE_CAL`` — command 1
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Request:  [1]
   Response: none

The next normal 13-byte read returns normalized values. Valid calibration data should be loaded or generated first.

.. _52-firmware-and-status:

5.2 Firmware and status
~~~~~~~~~~~~~~~~~~~~~~~

.. _get_version--command-2:

``GET_VERSION`` — command 2
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Request:  [2]
   Response: [major, minor, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

For this source version, the expected result begins with ``[3, 87]``.

.. _debug--command-3:

``DEBUG`` — command 3
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Request:  [3, level]
   Response: none

===== ===========
Level Name
===== ===========
0     Error
1     Warning
2     Information
3     Debug
4     Verbose
===== ===========

.. _is_calibrated--command-5:

``IS_CALIBRATED`` — command 5
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Request:  [5]
   Response: [state, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

``state`` is ``0`` or ``1``.

This flag becomes true as calibration samples are collected; it is not a reliable indication that the configured calibration duration has finished.

.. _53-calibration:

5.3 Calibration
~~~~~~~~~~~~~~~

.. _calibrate--command-4:

``CALIBRATE`` — command 4
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Request:  [4]          # calibrate without automatically saving
   Request:  [4, 0]       # same behavior
   Request:  [4, 1]       # save calibration after completion
   Response: none

Calibration behavior:

1. The IR emitter is enabled.
2. Current mode and LED mode are remembered.
3. Calibration minima and maxima are reset.
4. Samples are collected for ``CONFIG_CAL_DURATION`` seconds, default 7 seconds.
5. The previous operating and LED modes are restored.
6. Calibration is saved when the optional argument is nonzero.

Move both the dark line and the light background across every detector during calibration.

.. _load_cal--command-6:

``LOAD_CAL`` — command 6
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Request:  [6]
   Response: none

Loads 8 minimum and 8 maximum bytes from EEPROM and marks the device calibrated.

.. _save_cal--command-7:

``SAVE_CAL`` — command 7
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Request:  [7]
   Response: none

Saves calibration only when the sensor currently considers itself calibrated.

.. _get_min-and-get_max--commands-8-and-9:

``GET_MIN`` and ``GET_MAX`` — commands 8 and 9
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Request:  [8]
   Response: [min0, min1, min2, min3, min4, min5, min6, min7, 0, 0, 0, 0, 0]

   Request:  [9]
   Response: [max0, max1, max2, max3, max4, max5, max6, max7, 0, 0, 0, 0, 0]

.. _set_min-and-set_max--commands-10-and-11:

``SET_MIN`` and ``SET_MAX`` — commands 10 and 11
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Request:  [10, min0, min1, min2, min3, min4, min5, min6, min7]
   Response: none

   Request:  [11, max0, max1, max2, max3, max4, max5, max6, max7]
   Response: none

The device is marked calibrated after both arrays have been supplied. These commands do not save the arrays automatically; use ``SAVE_CAL`` afterward when persistent storage is required.

For every sensor, ``maximum`` must be greater than ``minimum`` to avoid invalid normalization arithmetic.

.. _54-neopixels-and-emitter:

5.4 NeoPixels and emitter
~~~~~~~~~~~~~~~~~~~~~~~~~

.. _neopixel--command-12:

``NEOPIXEL`` — command 12
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Request:  [12, index, red, green, blue]
   Response: none

-  ``index``: normally ``0..8`` because the strip contains 9 pixels.
-  ``red``, ``green``, ``blue``: ``0..255``.
-  Pixels 0..7 correspond to the detector display.
-  Pixel 8 is used by firmware as the calibration/status indicator and can be overwritten later by the firmware.

.. _leds--command-13:

``LEDS`` — command 13
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Request:  [13, mode]
   Response: none

+------+----------+--------------------------------------------------+
| Mode | Name     | Behavior                                         |
+======+==========+==================================================+
| 0    | Off      | Clear all NeoPixels.                             |
+------+----------+--------------------------------------------------+
| 1    | Normal   | Show detector intensity; green in calibrated     |
|      |          | mode and red in raw mode.                        |
+------+----------+--------------------------------------------------+
| 2    | Inverted | Show inverted detector intensity.                |
+------+----------+--------------------------------------------------+
| 3    | Position | Show the calculated position across the detector |
|      |          | LEDs.                                            |
+------+----------+--------------------------------------------------+

.. _set_emitter--command-14:

``SET_EMITTER`` — command 14
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Request:  [14, level]
   Response: none

-  ``0``: emitter control output low.
-  Nonzero: emitter control output high.

.. _55-configuration:

5.5 Configuration
~~~~~~~~~~~~~~~~~

The configuration structure contains seven bytes:

+-------+----------------------+------------+----------------------+
| Index | Name                 | Default    | Description          |
+=======+======================+============+======================+
| 0     | ``MAJ_VERSION``      | 3          | Configuration format |
|       |                      |            | major version.       |
+-------+----------------------+------------+----------------------+
| 1     | ``MIN_VERSION``      | 87         | Configuration format |
|       |                      |            | minor version.       |
+-------+----------------------+------------+----------------------+
| 2     | ``LOAD_CAL_STARTUP`` | 0          | Load saved           |
|       |                      |            | calibration and      |
|       |                      |            | enter calibrated     |
|       |                      |            | mode at startup when |
|       |                      |            | set to 1.            |
+-------+----------------------+------------+----------------------+
| 3     | ``CAL_DURATION``     | 7          | Calibration duration |
|       |                      |            | in seconds.          |
+-------+----------------------+------------+----------------------+
| 4     | ``SHA                | 100        | Per-detector         |
|       | PE_THRESHOLD_BLACK`` |            | threshold used to    |
|       |                      |            | build the shape      |
|       |                      |            | mask.                |
+-------+----------------------+------------+----------------------+
| 5     | ``IR_POWER``         | 0          | Emitter level        |
|       |                      |            | applied during       |
|       |                      |            | startup.             |
+-------+----------------------+------------+----------------------+
| 6     | ``CRC``              | calculated | XOR checksum over    |
|       |                      |            | indices 0..5.        |
|       |                      |            | Managed by the       |
|       |                      |            | firmware.            |
+-------+----------------------+------------+----------------------+

.. _get_value--command-15:

``GET_VALUE`` — command 15
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Request:  [15, index]
   Response: [value, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

For an out-of-range index, the returned value is ``0``.

.. _set_value--command-16:

``SET_VALUE`` — command 16
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Request:  [16, index, value]
   Response: none

The firmware schedules the configuration for saving after a valid write.

Avoid changing indices 0, 1, or 6. Changing the stored version bytes can make the configuration fail validation, and index 6 is the checksum maintained by firmware.

Changes to ``IR_POWER`` are stored but are not immediately applied by this command. Send ``SET_EMITTER`` to change the output immediately, or restart/load as appropriate.

.. _show_config--command-17:

``SHOW_CONFIG`` — command 17
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Prints the configuration to the sensor's serial port. No data is returned over I2C.

.. _load_config--command-18:

``LOAD_CONFIG`` — command 18
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Loads and validates configuration from EEPROM. Invalid data is replaced in RAM with defaults.

.. _save_config--command-19:

``SAVE_CONFIG`` — command 19
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Schedules an EEPROM configuration write in the main loop.

.. _56-test-gpio-and-serial-control:

5.6 Test GPIO and serial control
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Logical GPIO mapping:

=========== ========
Logical pin MCU pin
=========== ========
0           ``PA9``
1           ``PA10``
=========== ========

.. _gpio_out--command-20:

``GPIO_OUT`` — command 20
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Request:  [20, logical_pin, value]
   Response: none

A zero value drives low; a nonzero value drives high.

.. _gpio_in--command-21:

``GPIO_IN`` — command 21
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Request:  [21, logical_pin]
   Response: [value]

The input uses the MCU's internal pull-up.

-  ``0``: low.
-  ``1``: high.
-  ``255``: invalid logical pin.

.. _serial_disable--command-22:

``SERIAL_DISABLE`` — command 22
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Request:  [22]
   Response: [1]

Disables serial output. This is useful when PA9/PA10 are tested as GPIO and serial activity would interfere.

.. _serial_enable--command-23:

``SERIAL_ENABLE`` — command 23
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Request:  [23]
   Response: [1]

Restarts serial output at 115200 baud.

.. _57-unique-id:

5.7 Unique ID
~~~~~~~~~~~~~

.. _get_uid--command-24:

``GET_UID`` — command 24
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Request:  [24]
   Response: 12 UID bytes

Each 32-bit UID word is serialized least-significant byte first. A convenient display form is a 24-character hexadecimal string.
