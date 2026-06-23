# Run this script on the LMS-ESP32 board with ViperIDE.
# Get line_sensor.py from https://github.com/AntonsMindstorms/lms-line-sensor/blob/main/micropython/line_sensor.py
# Copy line_sensor.py to the LMS-ESP32 board with ViperIDE.

from pupremote import PUPRemoteSensor
from line_sensor import LineSensorI2C

ls = LineSensorI2C()


def calib(start):
    if start:
        # Put line sensor in calibration mode
        ls.start_calibration()
    else:
        # Not start. Save calibration and use the new values.
        ls.save_calibration()
        ls.mode_calibrated()


pr = PUPRemoteSensor()
pr.add_channel("lines", "bbB")
pr.add_command("calib", from_hub_fmt="b")
pr.process()  # Get 5v power

# Now turn the ir emitting leds on
ls.ir_power(True)

# Load calibrated values from flash memory
ls.mode_calibrated()

while 1:
    pos, der, shape = ls.data(ls.POSITION, ls.DERIVATIVE, ls.SHAPE)
    print(pos, der, shape)
    pr.update_channel("lines", pos, der, ord(shape)) # Convert shape character to byte with ord()
    pr.process()
