import time
import pigpio

pi = None
ESC = 17
STEER = 18
FORWARD = 1600
BACKWARD = 1400
LEFT = 70
RIGHT = 110


def setup():

    global pi

    pi = pigpio.pi()

    if not pi.connected:

        pi.stop()

        raise RuntimeError("Запусти sudo pigpiod на машинке")
    
    move("stop")

    time.sleep(3)


def move(skill):

    values = {"forward": (FORWARD, 90), "backward": (BACKWARD, 90), "left": (FORWARD, LEFT), "right": (FORWARD, RIGHT), "circle": (FORWARD, LEFT), "stop": (1500, 90)}
    speed, angle = values[skill]

    speed = max(1350, min(1650, speed))
    angle = max(70, min(110, angle))

    if pi.set_servo_pulsewidth(ESC, speed) < 0:

        raise RuntimeError("Ошибка управления газом")
    
    if pi.set_servo_pulsewidth(STEER, int(11.1 * angle + 500)) < 0:

        pi.set_servo_pulsewidth(ESC, 1500)

        raise RuntimeError("Ошибка управления рулем")


def close():

    try:

        move("stop")

    finally:

        pi.stop()




