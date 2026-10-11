"""Third-party code used for offline reference and Pybricks bundling.

- ``uRemote/`` is a git submodule of https://github.com/AntonsMindstorms/uRemote.
  ``tools/generate_line_sensor_pybricks.py`` trims its ``library/uremote.py``
  to the Pybricks client and inlines it into ``line_sensor_pybricks.py``.

The desktop USB client is ``usb/uremote.py`` (pyserial adaptation of the same
protocol). LMS-ESP32 firmware may also ship a frozen ``uremote`` module.
"""
