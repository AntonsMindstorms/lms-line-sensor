"""uRemote client for desktop Python serial ports.

This Windows/Linux adaptation is based on AntonsMindstorms uRemote 1.2:
https://github.com/AntonsMindstorms/uRemote/blob/main/library/uremote.py
"""

from __future__ import annotations

import time
from typing import Any, Callable, Optional

__author__ = "Anton Vanhoucke & Ste7an; desktop adaptation for Line Sensor"
__copyright__ = "Copyright 2024,2025,2026 AntonsMindstorms.com"
__license__ = "GPL"
__version__ = "1.2-desktop"

STATUS_OK = 0
STATUS_ERR = 1
MAX_FRAME = 255
MIN_FRAME = 5
MAX_CMD_LEN = 31
PREAMBLE = b"<$MU"
PREAMBLE_LEN = len(PREAMBLE)

_T_BOOL = ord("B")
_T_NUM = ord("N")
_T_BYTES = ord("A")
_T_STR = ord("S")


class uRemoteError(Exception):
    """Transport, protocol, or remote-command failure."""


def _as_values(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    return [] if data is None else [data]


def _unwrap_result(payload: Any) -> Any:
    values = _as_values(payload)
    if not values:
        return None
    return values[0] if len(values) == 1 else tuple(values)


def list_serial_ports() -> list[Any]:
    """Return detected serial ports, sorted by device name.

    Each result is a ``serial.tools.list_ports.ListPortInfo`` object. Install
    ``pyserial`` before calling this function.
    """

    try:
        from serial.tools import list_ports
    except ImportError as error:
        raise uRemoteError(
            "pyserial is required; install it with: python -m pip install pyserial"
        ) from error
    return sorted(list_ports.comports(), key=lambda item: item.device.lower())


def select_serial_port(
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> str:
    """List serial/USB ports and ask the user which one to use."""

    ports = list_serial_ports()
    if not ports:
        raise uRemoteError(
            "No serial ports were found. Connect the line sensor and try again."
        )

    output_fn("Available serial/USB ports:")
    for index, port in enumerate(ports, start=1):
        description = port.description or "Serial device"
        details = f" ({port.manufacturer})" if port.manufacturer else ""
        output_fn(f"  {index}. {port.device} - {description}{details}")

    while True:
        choice = input_fn(f"Select a port [1-{len(ports)}]: ").strip()
        try:
            selected = int(choice)
        except ValueError:
            selected = 0
        if 1 <= selected <= len(ports):
            return ports[selected - 1].device
        output_fn("Please enter one of the listed numbers.")


class uRemote:
    """Synchronous uRemote RPC client using a Windows or Linux serial port.

    Args:
        port: Port name such as ``COM5`` or ``/dev/ttyACM0``.
        baudrate: Serial speed. The line sensor uses 115200 baud.
        wait_recv: Overall reply timeout in milliseconds.
        serial_timeout: Timeout of each pyserial read in seconds.
        settle_time: Delay after opening the port before clearing stale data.
        serial_instance: Optional open serial-like object, mainly for tests.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        wait_recv: int = 1500,
        serial_timeout: float = 0.05,
        settle_time: float = 0.25,
        serial_instance: Optional[Any] = None,
    ) -> None:
        self.wait_recv = wait_recv
        self.byte_timeout = 100
        self._last_rx_error: Optional[str] = None
        self._owns_serial = serial_instance is None

        if serial_instance is not None:
            self.uart = serial_instance
        else:
            try:
                import serial
            except ImportError as error:
                raise uRemoteError(
                    "pyserial is required; install it with: python -m pip install pyserial"
                ) from error
            try:
                self.uart = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    timeout=serial_timeout,
                    write_timeout=max(serial_timeout, wait_recv / 1000),
                )
            except serial.SerialException as error:
                raise uRemoteError(f"Cannot open {port}: {error}") from error

        if settle_time:
            time.sleep(settle_time)
        self.flush()

    def close(self) -> None:
        """Close the serial port."""

        if getattr(self.uart, "is_open", True):
            self.uart.close()

    def __enter__(self) -> "uRemote":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()

    def _waiting(self) -> int:
        return int(getattr(self.uart, "in_waiting", 0))

    def _read_byte(self) -> Optional[int]:
        value = self.uart.read(1)
        return value[0] if value else None

    def _fail_rx(self, error: str) -> bytes:
        self.flush()
        self._last_rx_error = "Read error: " + error
        return b""

    def flush(self) -> None:
        """Discard bytes waiting in the serial receive buffer."""

        reset = getattr(self.uart, "reset_input_buffer", None)
        if reset is not None:
            reset()
            return
        while self._waiting():
            self.uart.read(self._waiting())

    def _send_bytes(self, payload: bytes) -> None:
        frame = PREAMBLE + payload
        if len(frame) > MAX_FRAME:
            raise uRemoteError("frame too large")
        try:
            written = self.uart.write(bytes([len(frame)]) + frame)
        except Exception as error:
            raise uRemoteError(f"Serial write failed: {error}") from error
        if written is not None and written != len(frame) + 1:
            raise uRemoteError("Serial write was incomplete")

    def _recv_bytes(self) -> bytes:
        self._last_rx_error = None
        deadline = time.monotonic() + self.wait_recv / 1000
        while time.monotonic() < deadline and not self._waiting():
            time.sleep(0.001)
        if not self._waiting():
            return self._fail_rx("No data. Is the correct port selected?")

        length = self._read_byte()
        if length is None or length < MIN_FRAME or length > MAX_FRAME:
            message = "No length byte" if length is None else "Invalid frame length"
            return self._fail_rx(message)

        frame = bytearray()
        byte_deadline = time.monotonic() + self.byte_timeout / 1000
        while len(frame) < length:
            if time.monotonic() >= deadline:
                return self._fail_rx("Incomplete frame")
            value = self._read_byte()
            if value is not None:
                frame.append(value)
                byte_deadline = time.monotonic() + self.byte_timeout / 1000
            elif time.monotonic() >= byte_deadline:
                return self._fail_rx("Inter-byte timeout")

        if bytes(frame[:PREAMBLE_LEN]) != PREAMBLE:
            return self._fail_rx("Preamble mismatch")
        return bytes(frame[PREAMBLE_LEN:])

    def _encode(self, status: int, cmd: str, *argv: Any) -> bytes:
        command = cmd.encode("utf-8")
        if not command or len(command) > MAX_CMD_LEN:
            raise uRemoteError("command name must contain 1 to 31 UTF-8 bytes")
        out = bytes([(status << 5) | len(command)]) + command
        for arg in argv:
            if type(arg) is bool:
                encoded = bytes([1 if arg else 0])
                arg_type = _T_BOOL
            elif type(arg) is int:
                encoded = str(arg).encode("utf-8")
                arg_type = _T_NUM
            elif isinstance(arg, (bytes, bytearray, memoryview)):
                encoded = bytes(arg)
                arg_type = _T_BYTES
            elif type(arg) is str:
                encoded = arg.encode("utf-8")
                arg_type = _T_STR
            else:
                raise TypeError(f"unsupported uRemote argument type: {type(arg).__name__}")
            if len(encoded) > 255:
                raise uRemoteError("argument is too large")
            out += bytes([arg_type, len(encoded)]) + encoded
        return out

    def _decode(self, encoded: bytes) -> tuple[int, str, Any]:
        if not encoded:
            raise ValueError("empty payload")
        header = encoded[0]
        status, command_length = header >> 5, header & 0x1F
        if command_length == 0 or 1 + command_length > len(encoded):
            raise ValueError("invalid command length")
        command = encoded[1 : 1 + command_length].decode("utf-8")
        decoded: list[Any] = []
        position = 1 + command_length
        while position < len(encoded):
            if position + 2 > len(encoded):
                raise ValueError("invalid argument header")
            arg_type, length = encoded[position], encoded[position + 1]
            position += 2
            if position + length > len(encoded):
                raise ValueError("invalid argument length")
            chunk = encoded[position : position + length]
            position += length
            if arg_type == _T_NUM:
                decoded.append(int(chunk))
            elif arg_type == _T_BYTES:
                decoded.append(bytes(chunk))
            elif arg_type == _T_STR:
                decoded.append(chunk.decode("utf-8"))
            elif arg_type == _T_BOOL:
                if length != 1:
                    raise ValueError("invalid boolean length")
                decoded.append(bool(chunk[0]))
            else:
                raise ValueError(f"unknown type {arg_type}")
        payload: Any = decoded[0] if len(decoded) == 1 else decoded
        return status, command, payload

    def _send_command(self, cmd: str, *data: Any, status: int = STATUS_OK) -> None:
        self._send_bytes(self._encode(status, cmd, *data))

    def _recv_command(self) -> tuple[int, str, Any]:
        encoded = self._recv_bytes()
        if not encoded:
            return STATUS_ERR, "", self._last_rx_error or "no bytes received"
        try:
            return self._decode(encoded)
        except (ValueError, IndexError, UnicodeError) as error:
            self.flush()
            return STATUS_ERR, "", "decode error: " + str(error)

    def exchange(self, cmd: str, *data: Any) -> tuple[int, str, Any]:
        """Send a command and return raw ``(status, command, payload)``."""

        self.flush()
        self._send_command(cmd, *data)
        return self._recv_command()

    def call(self, cmd: str, *data: Any) -> Any:
        """Call a sensor command and return None, a scalar, or a tuple."""

        status, reply_cmd, payload = self.exchange(cmd, *data)
        if status != STATUS_OK or not reply_cmd:
            raise uRemoteError(payload if isinstance(payload, str) else str(payload))
        if reply_cmd != cmd:
            self.flush()
            raise uRemoteError(f"unexpected reply: {reply_cmd}")
        return _unwrap_result(payload)


# Conventional Python class alias while retaining the upstream API name.
URemote = uRemote

