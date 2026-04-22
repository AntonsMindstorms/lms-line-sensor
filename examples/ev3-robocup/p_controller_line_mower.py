# Run this one the EV3 Core Line Mower model with lms-line-sensor-v1.0

from pybricks.hubs import EV3Brick
from pybricks.parameters import Button, Color, Direction, Port, Side, Stop
from pybricks.ev3devices import Motor
from line_sensor import LineSensorUR as LineSensor
hub = EV3Brick()

mb=Motor(Port.B, Direction.COUNTERCLOCKWISE)
mc=Motor(Port.C, Direction.COUNTERCLOCKWISE)
ls = LineSensor(Port.S1)

KP = 0.8
BASE_DC = 60 # DC=Direct Current. Or % of max power routed to the motor.

ls.load_calibration()
ls.ir_power(True)
ls.mode_calibrated()

while True:
    pos, shape = ls.data(ls.POSITION, ls.SHAPE)
    
    if shape is " ": # Stop on white
        left_dc = right_dc = 0
    else:
        steer = pos*KP
        left_dc = BASE_DC + steer 
        right_dc = BASE_DC - steer
    mb.dc(left_dc)
    mc.dc(right_dc)

