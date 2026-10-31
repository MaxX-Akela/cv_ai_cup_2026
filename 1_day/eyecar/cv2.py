import os
import signal
import sys
import time
import pigpio

STOP = 1500
STRAIGHT = 90
LEFT = 80
RIGHT = 100
SPEED = 1600
SLOW_SPEED = 1520
CAMERA_ID = 0
WIDTH = 320
HEIGHT = 240
STOP_Y = 0.86
SLOW_Y = 0.60
MAX_RUN_SECONDS = 60


def setup_gpio():
    os.system("sudo pigpiod")
    time.sleep(1)
    ESC = 17
    STEER = 18
    pi = pigpio.pi()
    if not pi.connected:
        raise RuntimeError("Нет связи с pigpiod")
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


def find_stop(cv2, np, frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    yellow = cv2.inRange(hsv, (18, 85, 65), (40, 255, 255))
    black = cv2.inRange(hsv, (0, 0, 0), (179, 255, 65))
    mask = cv2.morphologyEx(yellow, cv2.MORPH_CLOSE, np.ones((3, 21), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if y < HEIGHT * 0.35 or w < WIDTH * 0.25 or w < h * 2:
            continue
        roi = yellow[y:y+h, x:x+w]
        dark = black[y:y+h, x:x+w]
        if np.mean(roi > 0) < 0.15 or np.mean(dark > 0) < 0.12:
            continue
        if best is None or y + h > best[1] + best[3]:
            best = (x, y, w, h)
    return best


def run_stop(pi, ESC, STEER):
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(CAMERA_ID)
    try:
        if not cap.isOpened():
            raise RuntimeError("Камера не открылась")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        start = time.monotonic()
        while time.monotonic() - start < MAX_RUN_SECONDS:
            ok, frame = cap.read()
            if not ok or frame is None:
                raise RuntimeError("Нет изображения с камеры")
            frame = cv2.resize(frame, (WIDTH, HEIGHT))
            line = find_stop(cv2, np, frame)
            speed = SPEED
            if line is not None:
                x, y, w, h = line
                if y + h >= HEIGHT * STOP_Y:
                    control(pi, ESC, STOP, STEER, STRAIGHT)
                    print("Стоп-линия")
                    return
                if y + h >= HEIGHT * SLOW_Y:
                    speed = SLOW_SPEED
            control(pi, ESC, speed, STEER, STRAIGHT)
        raise RuntimeError("Время вышло, стоп-линия не найдена")
    finally:
        control(pi, ESC, STOP, STEER, STRAIGHT)
        cap.release()


if __name__ == "__main__":
    pi, ESC, STEER = setup_gpio()
    signal.signal(signal.SIGHUP, signal.default_int_handler)
    signal.signal(signal.SIGTERM, signal.default_int_handler)

    try:
        control(pi, ESC, STOP, STEER, STRAIGHT)
        print("Start")
        time.sleep(2)
        run_stop(pi, ESC, STEER)
    finally:
        control(pi, ESC, STOP, STEER, STRAIGHT)
        time.sleep(0.5)
        pi.set_servo_pulsewidth(ESC, 0)
        pi.set_servo_pulsewidth(STEER, 0)
        pi.stop()







