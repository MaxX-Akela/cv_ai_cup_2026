import os
import signal
import time
import pigpio

STOP = 1500
STRAIGHT = 90
LEFT = 80
RIGHT = 100
SPEED = 1540

ROUTE_E3 = [
    (SPEED, STRAIGHT, 2.0),
    (SPEED, LEFT, 1.0),
    (SPEED, RIGHT, 0.8),
    (SPEED, STRAIGHT, 2.5),
]


def setup_gpio():
    os.system("sudo pigpiod")
    time.sleep(1)
    ESC = 17
    STEER = 18
    pi = pigpio.pi()
    pi.set_servo_pulsewidth(ESC, 0)
    pi.set_servo_pulsewidth(STEER, 0)
    time.sleep(1)
    return (pi, ESC, STEER)


def control(pi, ESC, speed, STEER, angle):
    speed = max(1350, min(1650, speed))
    angle = max(70, min(110, angle))
    pi.set_servo_pulsewidth(ESC, speed)
    pi.set_servo_pulsewidth(STEER, int(11.1 * angle + 500))


def drive(pi, ESC, STEER, speed, angle, duration, brake=0.3):
    control(pi, ESC, speed, STEER, angle)
    time.sleep(duration)
    control(pi, ESC, STOP, STEER, angle)
    time.sleep(brake)


def run_route(pi, ESC, STEER, route):
    for speed, angle, duration in route:
        drive(pi, ESC, STEER, speed, angle, duration)


if __name__ == "__main__":
    pi, ESC, STEER = setup_gpio()
    signal.signal(signal.SIGHUP, signal.default_int_handler)

    try:
        control(pi, ESC, STOP, STEER, STRAIGHT)
        print("Start")
        time.sleep(2)
        run_route(pi, ESC, STEER, ROUTE_E3)
    finally:
        control(pi, ESC, STOP, STEER, STRAIGHT)
        time.sleep(0.5)
        pi.set_servo_pulsewidth(ESC, 0)
        pi.set_servo_pulsewidth(STEER, 0)
        pi.stop()
