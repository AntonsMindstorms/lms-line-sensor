"""LineSensorUR for the standalone Pybricks bundle."""

from pybricks.tools import wait


class LineSensorUR(BaseLineSensor):
    def __init__(self, port, settle_ms=1, remote_class=None):
        self.ur = (remote_class or uRemote)(port)
        self.settle_ms = settle_ms

    def data(self, *indices):
        raw = self.read_all()
        return self._select_indices(raw, indices)

    def read_all(self):
        if self.settle_ms:
            wait(self.settle_ms)
        return tuple(self.ur.call("all"))

    def mode_raw(self):
        return self.ur.call("mode", self.MODE_RAW)

    def mode_calibrated(self):
        return self.ur.call("mode", self.MODE_CALIBRATED)

    def leds(self, mode):
        return self.ur.call("led", mode)

    def start_calibration(self):
        self.leds(self.LEDS_OFF)
        return self.ur.call("calibrate")

    def calibrate(self, duration=5):
        self.start_calibration()
        wait(1000 * (duration + 1))
        wait(1500)
        return self.save_calibration()

    def save_calibration(self):
        return self.ur.call("save")

    def load_calibration(self):
        return self.ur.call("load")

    def ir_power(self, power):
        return self.ur.call("emitter", power)

    def neopixel(self, led_nr, r, g, b):
        return self.ur.call("neopixel", led_nr, r, g, b)
