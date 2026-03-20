from pupremote import PUPRemoteSensor
from line_sensor import LineSensor

ls = LineSensor()
ls.load_calibration()
ls.mode_calibrated()

def calib(start):
    if start:
        print('start')
        ls.start_calibration()
    else:
        print('stop')
        ls.stop_calibration()

        
    
pr = PUPRemoteSensor()
pr.add_channel('lines', 'bbB')
pr.add_command('calib', from_hub_fmt = 'b')
pr.process() # Get 5v power

# Now turn leds on
ls.ir_on()
ls.rgb_mode(ls.LEDS_POSITION)

while 1:
    pos, der, shape = ls.position_and_shape()
    print(pos, der, shape, ls.current_mode)
    pr.update_channel('lines',pos,der,ord(shape))
    pr.process()
