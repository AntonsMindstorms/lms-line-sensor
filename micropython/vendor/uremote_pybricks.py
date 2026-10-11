"""Minimal Pybricks-only uRemote client for standalone bundling.

Derived from AntonsMindstorms uRemote 1.3 (Pybricks client paths only).
"""

from pybricks.iodevices import UARTDevice
from pybricks.parameters import Port
from pybricks.tools import StopWatch, wait, run_task


def const(value):
    return value


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
    """Pybricks UART RPC client (sync and async)."""

    def __init__(
        self, port_or_uart=1, baudrate=115200, wait_recv=1000, uart_timeout=1000, power_pin=2
    ):
        self.byte_timeout = 10
        self.wait_recv = wait_recv
        self._last_rx_error = None
        self._async_busy = False
        self._watch = StopWatch()
        if isinstance(port_or_uart, str):
            port_or_uart = getattr(Port, port_or_uart)
        self.uart = UARTDevice(port_or_uart, timeout=uart_timeout, power_pin=power_pin)
        self.uart.set_baudrate(baudrate)
        self.uart.read_all()
        self._ticks = self._watch.time
        self._elapsed = lambda start: self._watch.time() - start
        self._pause = wait
        self._waiting = self.uart.waiting
        self._drain = self.uart.read_all

    def _fail_rx(self, error):
        self.flush()
        self._last_rx_error = "Read error: " + error
        return b""

    def _require_sync_uart(self):
        if run_task():
            raise uRemoteError("use call_async() under run_task()/multitask()")

    def flush(self):
        """Discard all bytes waiting in the UART receive buffer."""
        while self._waiting():
            self._drain()

    def _packet(self, payload):
        frame = PREAMBLE + payload
        if len(frame) > MAX_FRAME:
            raise uRemoteError("frame too large")
        return bytes([len(frame)]) + frame

    def _send_bytes(self, payload):
        self.uart.write(self._packet(payload))

    def _read_byte(self):
        data = self.uart.read(1)
        return data[0] if data else None

    async def _read_byte_async(self):
        data = await self.uart.read(1)
        return data[0] if data else None

    def _recv_bytes(self):
        self._last_rx_error = None
        start = self._ticks()
        while self._elapsed(start) < self.wait_recv and not self._waiting():
            self._pause(1)
        if not self._waiting():
            return self._fail_rx("No data. Is remote script running?")

        length = self._read_byte()
        if length is None or length < MIN_FRAME or length > MAX_FRAME:
            return self._fail_rx(
                "No length byte. Is remote script running?"
                if length is None
                else "Invalid frame length"
            )

        payload = bytearray()
        total_start = byte_start = self._ticks()
        pre = 0
        while len(payload) < length:
            if self._elapsed(total_start) > self.wait_recv:
                return self._fail_rx("Incomplete frame.")
            if self._waiting():
                value = self._read_byte()
                if value is None:
                    return self._fail_rx("Incomplete frame.")
                payload.append(value)
                if pre < PREAMBLE_LEN:
                    if value != PREAMBLE[pre]:
                        return self._fail_rx("Preamble mismatch.")
                    pre += 1
                byte_start = self._ticks()
            elif self._elapsed(byte_start) > self.byte_timeout:
                return self._fail_rx("Inter-byte timeout.")
            else:
                self._pause(1)
        return bytes(payload[PREAMBLE_LEN:])

    async def _recv_bytes_async(self):
        self._last_rx_error = None
        start = self._ticks()
        while self._elapsed(start) < self.wait_recv and not self._waiting():
            await wait(0)
        if not self._waiting():
            return self._fail_rx("No data. Is remote script running?")

        length = await self._read_byte_async()
        if length is None or length < MIN_FRAME or length > MAX_FRAME:
            return self._fail_rx(
                "No length byte. Is remote script running?"
                if length is None
                else "Invalid frame length"
            )

        payload = bytearray()
        total_start = byte_start = self._ticks()
        pre = 0
        while len(payload) < length:
            if self._elapsed(total_start) > self.wait_recv:
                return self._fail_rx("Incomplete frame.")
            if self._waiting():
                value = await self._read_byte_async()
                if value is None:
                    return self._fail_rx("Incomplete frame.")
                payload.append(value)
                if pre < PREAMBLE_LEN:
                    if value != PREAMBLE[pre]:
                        return self._fail_rx("Preamble mismatch.")
                    pre += 1
                byte_start = self._ticks()
            elif self._elapsed(byte_start) > self.byte_timeout:
                return self._fail_rx("Inter-byte timeout.")
            else:
                await wait(0)
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
        cmd = str(encoded[1 : 1 + name_len], "utf-8")
        decoded = []
        pos = 1 + name_len
        while pos < len(encoded):
            item_type = encoded[pos]
            item_len = encoded[pos + 1]
            pos += 2
            chunk = encoded[pos : pos + item_len]
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

    async def _send_command_async(self, cmd, *data, status=STATUS_OK):
        await self.uart.write(self._packet(self._encode(status, cmd, *data)))

    def _decode_command(self, encoded):
        if not encoded:
            return STATUS_ERR, "", self._last_rx_error or "no bytes received"
        try:
            return self._decode(encoded)
        except (ValueError, IndexError, UnicodeError) as exc:
            self.flush()
            return STATUS_ERR, "", "decode error: " + str(exc)

    def _recv_command(self):
        return self._decode_command(self._recv_bytes())

    async def _recv_command_async(self):
        return self._decode_command(await self._recv_bytes_async())

    def _finish_call(self, cmd, status, reply_cmd, payload):
        if status != STATUS_OK or not reply_cmd:
            raise uRemoteError(payload if isinstance(payload, str) else str(payload))
        if reply_cmd != cmd:
            self.flush()
            raise uRemoteError("unexpected reply: " + reply_cmd)
        return _unwrap_result(payload)

    def exchange(self, cmd, *data):
        """Send a command and return ``(status, reply_cmd, payload)``."""
        self._require_sync_uart()
        self._send_command(cmd, *data)
        return self._recv_command()

    def call(self, cmd, *data):
        """Call a remote command and return its result."""
        self._require_sync_uart()
        self.flush()
        self._send_command(cmd, *data)
        return self._finish_call(cmd, *self._recv_command())

    async def call_async(self, cmd, *data):
        """Async call for use under ``run_task()`` / ``multitask()``."""
        while self._async_busy:
            await wait(0)
        self._async_busy = True
        try:
            self.flush()
            await self._send_command_async(cmd, *data)
            return self._finish_call(cmd, *(await self._recv_command_async()))
        finally:
            self._async_busy = False
