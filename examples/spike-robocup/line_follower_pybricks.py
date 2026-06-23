from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor, ColorSensor, UltrasonicSensor, ForceSensor
from pybricks.parameters import Button, Color, Direction, Port, Side, Stop
from pybricks.robotics import DriveBase
from pybricks.tools import wait, StopWatch
from pupremote_hub import PUPRemoteHub

# Initialize hardware
hub = PrimeHub()
lmotor = Motor(Port.F, Direction.COUNTERCLOCKWISE)
rmotor = Motor(Port.E)
pr = PUPRemoteHub(Port.C)
pr.add_channel('lines', 'bbB')
pr.add_command('calib', from_hub_fmt='b')
w = StopWatch()

# Tuning constants
FACTOR = 1 # Increase with multiples of .1 to make the robot go faster.
BASE_DC = 30 * FACTOR # Basic % motor power (voltage)
D_BRAKE = 0.04 # Brake power as a function of derivative.
KP = -0.25 * FACTOR # Proportional gain.
KD = -0.06 * FACTOR # Derivative gain.

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
        if chr(shape) in '|<>TY':
            lpwr = BASE_DC - abs(der)*D_BRAKE - pos*KP - der*KD # Left motor power.
            rpwr = BASE_DC - abs(der)*D_BRAKE + pos*KP + der*KD # Right motor power.
            lmotor.dc(lpwr) # Set left motor power.
            rmotor.dc(rpwr) # Set right motor power.
        else:
            lmotor.dc(20) # Stop on white.
            rmotor.dc(20) # Stop on white.

    if mode == CALIBRATE:
        lmotor.dc(0) # Stop motors.
        rmotor.dc(0) # Stop motors.
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



