LMS Line Sensor
===============

MicroPython driver documentation for the LMS Line Sensor.

Installation
============

The package is distributed on PyPI for convenient versioning and packaging, but it is intended to run on MicroPython targets that provide the ``machine`` module.

Install the package locally:

.. code-block:: bash

   pip install lms-line-sensor

If your deployment workflow copies modules to the board manually, transfer ``line_sensor.py`` from the installed package to your device filesystem.

Usage
=====

Micropython
-----------

Create a sensor instance by passing the I2C pin assignments and, if needed, a custom device address.

.. code-block:: python

   from time import sleep

   from line_sensor import LineSensor

   sensor = LineSensor(scl_pin=4, sda_pin=5, device_addr=51)
   sensor.ir_led_on()
   sensor.load_calibration_from_rom()
   sensor.mode_calibrated()

   while True:
       print(sensor.position(), sensor.position_derivative())
       sleep(0.1)

Useful constants exposed by ``LineSensor`` include:

- ``MODE_RAW`` and ``MODE_CALIBRATED`` for acquisition mode selection.
- ``LEDS_OFF``, ``LEDS_NORMAL``, ``LEDS_INVERTED``, and ``LEDS_POSITION`` for LED display modes.
- ``POSITION``, ``MIN``, ``MAX``, ``DERIVATIVE``, and ``SHAPE`` for indexing values returned by ``data()``.

Microblocks
-----------

Quick example program:

.. image:: line-sensor-microblocks.png

API Reference
=============

.. automodule:: line_sensor
   :members:
   :undoc-members:
   :show-inheritance: