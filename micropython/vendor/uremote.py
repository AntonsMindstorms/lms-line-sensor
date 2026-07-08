"""Vendored uRemote client/server library.

Source: https://github.com/AntonsMindstorms/uRemote
Fetched from the upstream ``main`` branch and kept locally so bundle
generation stays reproducible and offline.
"""

# ============================================================
# uRemote - unified MicroPython library
# Tested on Pybricks, LMS-ESP32 and OpenMV AE3
# ============================================================
__author__ = "Anton Vanhoucke & Ste7an"
__copyright__ = "Copyright 2024,2025,2026 AntonsMindstorms.com"
__license__ = "GPL"
__version__ = "1.2"
__status__ = "Production"

import __main__
import sys

try:
    from micropython import const
except ImportError:
    def const(arg):
        return arg


STATUS_OK = const(0)
STATUS_ERR = const(1)
MAX_FRAME = const(255)
MIN_FRAME = const(5)
MAX_CMD_LEN = const(31)
PREAMBLE = b"<$MU"
PREAMBLE_LEN = const(4)

_T_BOOL = const(66)
_T_NUM = const(78)
_T_BYTES = const(65)
_T_STR = const(83)

try:
    from lms_esp32 import RX_PIN, TX_PIN
except ImportError:
    RX_PIN = None
    TX_PIN = None

if "Pybricks" in sys.version:
    _IS_PYBRICKS = True
    from pybricks.iodevices import UARTDevice
    from pybricks.tools import StopWatch, wait
    from pybricks.parameters import Port
else:
    _IS_PYBRICKS = False
    import time
    import machine


class uRemoteError(Exception):
    pass


def _as_values(data):
    if isinstance(data, list):
        return data
    return [] if data is None else [data]


def _unwrap_result(payload):
    values = _as_values(payload)
    if not values:
        return None
    return values[0] if len(values) == 1 else tuple(values)


class uRemote:
    """UART RPC client/server for Pybricks hubs and ESP32 boards."""

    def __init__(
        self,
        port_or_uart=1,
        baudrate=115200,
        wait_recv=1000,
        uart_timeout=1000,
        rx=RX_PIN,
        tx=TX_PIN,
        power_pin=2,
    ):
        self.byte_timeout = 10
        self.wait_recv = wait_recv
        self._last_rx_error = None
        if _IS_PYBRICKS:
            self._watch = StopWatch()
            if isinstance(port_or_uart, str):
                port_or_uart = eval("Port." + port_or_uart)
            self.uart = UARTDevice(port_or_uart, timeout=uart_timeout, power_pin=power_pin)
            self.uart.set_baudrate(baudrate)
            self.uart.read_all()
        else:
            kwargs = {"timeout": uart_timeout, "baudrate": baudrate}
            if rx is not None and tx is not None:
                kwargs["rx"] = machine.Pin(rx)
                kwargs["tx"] = machine.Pin(tx)
            self.uart = machine.UART(port_or_uart, **kwargs)

    def _ticks(self):
        return self._watch.time() if _IS_PYBRICKS else time.ticks_ms()

    def _elapsed(self, start):
        if _IS_PYBRICKS:
            return self._watch.time() - start
        return time.ticks_diff(time.ticks_ms(), start)

    def _pause(self, ms):
        if _IS_PYBRICKS:
            wait(ms)
        else:
            time.sleep_ms(ms)

    def _waiting(self):
        return self.uart.waiting() if _IS_PYBRICKS else self.uart.any()

    def _read_byte(self):
        data = self.uart.read(1)
        return data[0] if data else None

    def _fail_rx(self, error):
        self.flush()
        self._last_rx_error = "Read error: " + error
        return b""

    def flush(self):
        """Discard all bytes waiting in the UART receive buffer."""
        while self._waiting():
            if _IS_PYBRICKS:
                self.uart.read_all()
            else:
                self.uart.read()

    def _send_bytes(self, payload):
        frame = PREAMBLE + payload
        if len(frame) > MAX_FRAME:
            raise uRemoteError("frame too large")
        self.uart.write(bytes([len(frame)]) + frame)

    def _recv_bytes(self):
        self._last_rx_error = None
        start = self._ticks()
        while self._elapsed(start) < self.wait_recv and not self._waiting():
            self._pause(1)
        if not self._waiting():
            return self._fail_rx("No data. Is remote script running?")

        length = self._read_byte()
        if length is None or length < MIN_FRAME or length > MAX_FRAME:
            if length is None:
                return self._fail_rx("No length byte. Is remote script running?")
            return self._fail_rx("Invalid frame length")

        payload = bytearray()
        total_start = self._ticks()
        byte_start = total_start
        preamble_index = 0
        while len(payload) < length:
            if self._elapsed(total_start) > self.wait_recv:
                return self._fail_rx("Incomplete frame.")
            if self._waiting():
                value = self._read_byte()
                if value is None:
                    return self._fail_rx("Incomplete frame.")
                payload.append(value)
                if preamble_index < PREAMBLE_LEN:
                    if value != PREAMBLE[preamble_index]:
                        return self._fail_rx("Preamble mismatch.")
                    preamble_index += 1
                byte_start = self._ticks()
            elif self._elapsed(byte_start) > self.byte_timeout:
                return self._fail_rx("Inter-byte timeout.")
            else:
                self._pause(1)
        return bytes(payload[PREAMBLE_LEN:])

    def _encode(self, status, cmd, *argv):
        name_len = len(cmd)
        if name_len > MAX_CMD_LEN:
            raise uRemoteError("command name too long")
        out = bytes([(status << 5) | name_len]) + bytes(cmd, "utf-8")
        for arg in argv:
            if type(arg) == bool:
                out += bytes([_T_BOOL, 1, 1 if arg else 0])
            elif type(arg) == int:
                raw = str(arg)
                out += bytes([_T_NUM, len(raw)]) + bytes(raw, "utf-8")
            elif type(arg) == bytes:
                out += bytes([_T_BYTES, len(arg)]) + arg
            elif type(arg) == str:
                out += bytes([_T_STR, len(arg)]) + bytes(arg, "utf-8")
            else:
                raise TypeError("unsupported type")
        return out

    def _decode(self, encoded):
        header = encoded[0]
        status = header >> 5
        name_len = header & 0x1F
        cmd = str(encoded[1:1 + name_len], "utf-8")
        decoded = []
        pos = 1 + name_len
        while pos < len(encoded):
            item_type = encoded[pos]
            item_len = encoded[pos + 1]
            pos += 2
            chunk = encoded[pos:pos + item_len]
            pos += item_len
            if item_type == _T_NUM:
                decoded.append(int(chunk))
            elif item_type == _T_BYTES:
                decoded.append(chunk)
            elif item_type == _T_STR:
                decoded.append(str(chunk, "utf-8"))
            elif item_type == _T_BOOL:
                decoded.append(bool(chunk[0]))
            else:
                raise ValueError("unknown type " + str(item_type))
        if len(decoded) == 1:
            decoded = decoded[0]
        return status, cmd, decoded

    def _send_command(self, cmd, *data, status=STATUS_OK):
        self._send_bytes(self._encode(status, cmd, *data))

    def _recv_command(self):
        data = self._recv_bytes()
        if not data:
            return STATUS_ERR, "", self._last_rx_error or "no bytes received"
        try:
            return self._decode(data)
        except (ValueError, IndexError, UnicodeError) as exc:
            self.flush()
            return STATUS_ERR, "", "decode error: " + str(exc)

    def exchange(self, cmd, *data):
        """Send a command and return the raw reply tuple."""
        self._send_command(cmd, *data)
        return self._recv_command()

    def call(self, cmd, *data):
        """Call a remote command and return its result."""
        self._send_command(cmd, *data)
        status, reply_cmd, payload = self._recv_command()
        if status != STATUS_OK or not reply_cmd:
            raise uRemoteError(payload if isinstance(payload, str) else str(payload))
        if reply_cmd != cmd:
            raise uRemoteError("unexpected reply: " + reply_cmd)
        return _unwrap_result(payload)

    def process(self):
        """Handle one incoming command and send a reply."""
        if not self._waiting():
            return
        status, cmd, data = self._recv_command()
        if status != STATUS_OK or not cmd:
            return
        if not isinstance(data, list):
            data = [data]
        if hasattr(__main__, cmd):
            try:
                response = getattr(__main__, cmd)(*data)
            except Exception as exc:
                self._send_command(cmd, cmd + ": " + str(exc), status=STATUS_ERR)
                return
            if response is None:
                response = ()
            elif not isinstance(response, tuple):
                response = (response,)
            self._send_command(cmd, *response, status=STATUS_OK)
        else:
            self._send_command(cmd, cmd + "() function not found remotely", status=STATUS_ERR)
