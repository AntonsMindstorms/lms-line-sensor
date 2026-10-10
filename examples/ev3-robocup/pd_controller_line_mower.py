# Run this one the EV3 Core Line Mower model with lms-line-sensor-v1.0

from pybricks.hubs import EV3Brick
from pybricks.parameters import Button, Color, Direction, Port, Side, Stop
from pybricks.ev3devices import Motor
from pybricks.robotics import DriveBase
from pybricks.tools import wait, StopWatch
from line_sensor_pybricks import LineSensorUR as LineSensor
hub = EV3Brick()

mb=Motor(Port.B, Direction.COUNTERCLOCKWISE)
mc=Motor(Port.C, Direction.COUNTERCLOCKWISE)
ls = LineSensor(Port.S1)

KP = 0.7
KD = 0.5
BASE_DC = 60 # DC=Direct Current. Or % of max power routed to the motor.

def show_instructions():
    hub.screen.clear()
    hub.screen.draw_text(0,10,'Press middle button to\nstart calibration.')

def calibrate():
    hub.screen.clear()
    hub.screen.draw_text(0,25,'Calibrating...\n\nMove sensor over line\nuntil blue light stops\nblinking.')
    ls.calibrate()
    show_instructions()
    
try:
    ls.load_calibration()
except:
    # Firmware 5.6 balks if you load_calibration without calibrating first.
    calibrate()

show_instructions()
ls.ir_power(True)
ls.mode_calibrated()

while True:
    pos, der, shape = ls.data(ls.POSITION, ls.DERIVATIVE, ls.SHAPE)
    
    if Button.CENTER in hub.buttons.pressed():
        calibrate()
    if shape == " ": # Stop on white
        left_dc = right_dc = 0
    else:
        steer = pos*KP + der*KD
        left_dc = BASE_DC + steer 
        right_dc = BASE_DC - steer
    mb.dc(left_dc)
    mc.dc(right_dc)

