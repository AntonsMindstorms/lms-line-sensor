# Async version of p_controller_line_mower.py for the EV3 Core Line Mower.
#
# Two tasks run at the same time under multitask():
#   follow()  steers the robot with a P controller, reading the line sensor.
#   animate() draws a face on the EV3 screen. Its eyes look where the line is.
#
# Inside run_task() every LineSensorUR call is awaitable: put `await` in front
# of the sensor calls and the screen keeps animating while the robot waits for
# the sensor, even during the multi-second calibration.
#
# Needs a Pybricks firmware with run_task()/multitask() and the generated
# line_sensor_pybricks.py from this repository.

from pybricks.hubs import EV3Brick
from pybricks.parameters import Button, Color, Direction, Port
from pybricks.ev3devices import Motor
from pybricks.tools import StopWatch, multitask, run_task, wait
from line_sensor_pybricks import LineSensorUR as LineSensor

hub = EV3Brick()

mb = Motor(Port.B, Direction.COUNTERCLOCKWISE)
mc = Motor(Port.C, Direction.COUNTERCLOCKWISE)
ls = LineSensor(Port.S1)

KP = 0.8
BASE_DC = 30  # DC=Direct Current. Or % of max power routed to the motor.

# What the two tasks share. follow() writes it, animate() only reads it.
state = {"pos": 0, "shape": "|", "calibrating": False}


async def calibrate():
    mb.stop()
    mc.stop()
    state["calibrating"] = True
    await ls.calibrate()  # The face keeps animating while we wait here.
    state["calibrating"] = False


async def follow():
    try:
        try:
            await ls.load_calibration()
        except Exception:
            # Firmware 5.6 balks if you load_calibration without calibrating first.
            await calibrate()

        await ls.ir_power(True)
        await ls.mode_calibrated()

        while True:
            if Button.CENTER in hub.buttons.pressed():
                await calibrate()

            pos, shape = await ls.data(ls.POSITION, ls.SHAPE)
            state["pos"] = pos
            state["shape"] = shape

            if shape == " ":  # Stop on white
                left_dc = right_dc = 0
            else:
                steer = pos * KP
                left_dc = BASE_DC + steer
                right_dc = BASE_DC - steer
            mb.dc(left_dc)
            mc.dc(right_dc)
    finally:
        mb.stop()
        mc.stop()


# --- The face ----------------------------------------------------------------
# The EV3 screen is 178 x 128 pixels. The face is only redrawn when something
# visible changes, so the screen does not flicker.

LEFT_EYE = (59, 52)
RIGHT_EYE = (119, 52)
EYE_R = 25
PUPIL_R = 12
LOOK_RANGE = 25  # How far the pupils move sideways, in pixels.

BAR_Y = 118
BAR_RANGE = 80  # The position dot moves this many pixels left and right.

# A smile is a parabola: the corners of the mouth are higher than the middle.
SMILE = [(x, 100 - (x - 89) ** 2 // 50) for x in range(64, 115, 5)]
# A wobbly mouth for when the robot is dizzy.
WOBBLE = [(64 + 5 * i, 96 + (4 if i % 2 else -4)) for i in range(11)]


def draw_line_through(points):
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        hub.screen.draw_line(x1, y1, x2, y2, 3)


def draw_eye(center, look, blinking, dizzy):
    x, y = center
    if dizzy:  # An X for each eye.
        hub.screen.draw_line(x - 12, y - 12, x + 12, y + 12, 3)
        hub.screen.draw_line(x - 12, y + 12, x + 12, y - 12, 3)
    elif blinking:
        hub.screen.draw_line(x - EYE_R, y, x + EYE_R, y, 3)
    else:
        hub.screen.draw_circle(x, y, EYE_R)
        hub.screen.draw_circle(x, y, EYE_R+1)
        hub.screen.draw_circle(x + look, y, PUPIL_R, True)


def draw_face(look, bar_x, blinking, mood):
    hub.screen.clear()
    if mood == "calibrating":
        hub.screen.draw_text(0, 0, "Calibrating... sweep\nover the line")
    else:
        hub.screen.draw_text(0, 0, "CENTER = calibrate")

    draw_eye(LEFT_EYE, look, blinking, mood == "calibrating")
    draw_eye(RIGHT_EYE, look, blinking, mood == "calibrating")

    if mood == "lost":  # No line under the sensor: surprised "oh!"
        hub.screen.draw_circle(89, 98, 10)
    elif mood == "calibrating":
        draw_line_through(WOBBLE)
    else:
        draw_line_through(SMILE)

    # Where the sensor sees the line, as a dot on a track.
    hub.screen.draw_line(89 - BAR_RANGE, BAR_Y, 89 + BAR_RANGE, BAR_Y)
    hub.screen.draw_circle(bar_x, BAR_Y, 4, True)


async def animate():
    watch = StopWatch()
    shown = None
    while True:
        pos = state["pos"]
        if state["calibrating"]:
            mood = "calibrating"
        elif state["shape"] == " ":
            mood = "lost"
        else:
            mood = "happy"

        look = pos * LOOK_RANGE // 128
        bar_x = 89 + pos * BAR_RANGE // 128
        blinking = watch.time() % 3000 < 150  # A quick blink every 3 seconds.

        frame = (look, bar_x, blinking, mood)
        if frame != shown:
            draw_face(look, bar_x, blinking, mood)
            shown = frame
        await wait(40)


async def main():
    # race=True: if follow() ever fails, stop everything instead of leaving the
    # face animating next to a robot that no longer drives.
    await multitask(follow(), animate(), race=True)


run_task(main())
