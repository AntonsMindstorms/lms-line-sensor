"""Vendored third-party pieces used for offline reference and Pybricks bundling.

- ``uremote.py`` — full upstream uRemote 1.3 (MicroPython / Pybricks / ESP32).
- ``uremote_pybricks.py`` — Pybricks-only trim, inlined into
  ``line_sensor_pybricks.py`` by ``tools/generate_line_sensor_pybricks.py``.

The desktop USB client is ``usb/uremote.py`` (pyserial adaptation of the same
protocol). LMS-ESP32 firmware may also ship a frozen ``uremote`` module.
Upstream: https://github.com/AntonsMindstorms/uRemote
"""
