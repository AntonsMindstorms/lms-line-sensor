from pupremote import PUPRemoteSensor
from line_sensor import LineSensorI2C

ls = LineSensorI2C()


def calib(start):
    if start:
        ls.start_calibration()
    else:
        ls.save_calibration()


pr = PUPRemoteSensor()
pr.add_channel("lines", "bbB")
pr.add_command("calib", from_hub_fmt="b")
pr.process()  # Get 5v power

# Now turn leds on
ls.ir_power(True)
ls.leds(ls.LEDS_POSITION)

while 1:
    pos, der, shape = ls.position_derivative_shape()
    # print(pos, der, shape)
    pr.update_channel("lines", pos, der, ord(shape))
    pr.process()
