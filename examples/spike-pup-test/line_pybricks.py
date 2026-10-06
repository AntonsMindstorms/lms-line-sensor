from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor, ColorSensor, UltrasonicSensor, ForceSensor
from pybricks.parameters import Button, Color, Direction, Port, Side, Stop
from pybricks.robotics import DriveBase
from pybricks.tools import wait, StopWatch
from pupremote_hub import PUPRemoteHub

# Initialize hardware
hub = PrimeHub()
# lmotor = Motor(Port.F, Direction.COUNTERCLOCKWISE)
# rmotor = Motor(Port.E)
pr = PUPRemoteHub(Port.A)
pr.add_channel('lines', 'bbB')
pr.add_command('calib', from_hub_fmt='b')
w = StopWatch()


# Modes
FOLLOW = 0
COUNTDOWN = 1
CALIBRATE = 2

# Start in countdown mode
mode = COUNTDOWN
while 1: # Main loop
    if Button.LEFT in hub.buttons.pressed():
        mode = CALIBRATE

    if mode == FOLLOW:
        pos,der,shape = pr.call('lines') # Get line position, derivative, and shape.
        print(pos, der, chr(shape))
        hub.display.char(chr(shape))
        wait(10)

    if mode == CALIBRATE:
        pr.call('calib',1) # Start calibration.
        for i in range(5): # Flash + and x on the display.
            hub.display.char('+')
            wait(500)
            hub.display.char('x')
            wait(500)
        pr.call('calib',0) # Stop calibration.
        mode = COUNTDOWN # Go to countdown mode.
        w.reset() # Reset stopwatch.

    if mode == COUNTDOWN:
        hub.display.char(str(3-w.time()//1000)) # Display countdown on the display.
        if w.time() > 3000:
            mode = FOLLOW # Go to follow mode.



