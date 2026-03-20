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

FACTOR = 1
BASE_DC = 45 * FACTOR
KP = 0.34 * FACTOR
KD = 0.4 * FACTOR

while 1:
    pos,der,shape = pr.call('lines')
    print(pos, der, chr(shape))
    if chr(shape) in '|<>T':
        lmotor.dc(BASE_DC-(abs(pos)*0.0+abs(der)*1.3) - pos*KP -der*KD)
        rmotor.dc(BASE_DC-(abs(pos)*0.0+abs(der)*1.3) + pos*KP +der*KD)
    # else:
    #     lmotor.stop()
    #     rmotor.dc(30)



