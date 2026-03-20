from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor, ColorSensor, UltrasonicSensor, ForceSensor
from pybricks.parameters import Button, Color, Direction, Port, Side, Stop
from pybricks.robotics import DriveBase
from pybricks.tools import wait, StopWatch
from pupremote_hub import PUPRemoteHub

hub = PrimeHub()
lmotor = Motor(Port.F, Direction.COUNTERCLOCKWISE)
rmotor = Motor(Port.E)
pr = PUPRemoteHub(Port.C)
pr.add_channel('lines', 'bbB')
pr.add_command('calib', from_hub_fmt='b')
w = StopWatch()

FACTOR = 1
BASE_DC = 35 * FACTOR
D_BRAKE = 1.3
KP = 0.35 * FACTOR
KD = 0.55 * FACTOR
FOLLOW = 0
COUNTDOWN = 1
CALIBRATE = 2
mode = COUNTDOWN

while 1:
    if Button.LEFT in hub.buttons.pressed():
        mode = CALIBRATE

    if mode == FOLLOW:
        pos,der,shape = pr.call('lines')
        print(pos, der, chr(shape))
        if chr(shape) in '|<>T':
            lpwr = BASE_DC - abs(der)*D_BRAKE - pos*KP - der*KD
            rpwr = BASE_DC - abs(der)*D_BRAKE + pos*KP + der*KD
            lmotor.dc(lpwr)
            rmotor.dc(rpwr)
        else:
            lmotor.dc(25)
            rmotor.dc(20)
    if mode == CALIBRATE:
        lmotor.dc(0)
        rmotor.dc(0)
        pr.call('calib',1)
        for i in range(5):
            hub.display.char('+')
            wait(500)
            hub.display.char('x')
            wait(500)
        pr.call('calib',0)
        mode = COUNTDOWN

    if mode == COUNTDOWN:
        hub.display.char(str(3))
        for i in range(2,-1,-1):
            wait(1000)
            hub.display.char(str(i))
            
        mode = FOLLOW



