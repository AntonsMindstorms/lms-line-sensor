from pupremote import PUPRemoteSensor
from line_sensor import LineSensor

ls = LineSensor()
ls.load_calibration()
ls.mode_calibrated()
ls.mode_calibrated()


pr = PUPRemoteSensor()
pr.add_channel("lines", "bbB")
pr.process()  # Get 5v power

# Now turn leds on
ls.ir_on()
ls.rgb_mode(ls.LEDS_POSITION)

while 1:
    pos, der, shape = ls.position_and_shape()
    print(pos, der, shape, ls.light_values(inverted=True), ls.position())
    pr.update_channel("lines", pos, der, ord(shape))
    pr.process()
