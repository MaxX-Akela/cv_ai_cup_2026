import io
import socket
import sys
import time

import cv2 as cv
import pymurapi as mur

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

SERVER_IP = "10.3.141.100"
PORT = 9001
CAMERA_ID = 0
WIDTH, HEIGHT = 320, 240
JPEG_QUALITY = 90

WATER_CONF = 0.6
WATER_FRAMES = 3
MAX_AGE = 2.0
START_TIMEOUT = 15

DEPTH = 0.3
DEPTH_KP = 60
DEPTH_KD = 40
TICK = 0.05

PROGRAM = [
    (0, 0, -30, 3.0),
    (30, 0, None, 4.0),
    (0, 30, None, 2.0),
    (30, 0, None, 4.0),
    (0, -30, None, 2.0),
    (0, 0, None, 1.0),
]


class WaterGuard:
    def __init__(self, camera, sock):
        self.camera = camera
        self.sock = sock
        self.answers = sock.makefile("rb")
        self.streak = 0
        self.ok_time = 0.0
        self.label = "?"

    def update(self):
        self.camera.grab()
        self.camera.grab()
        ok, img = self.camera.read()
        if not ok or img is None:
            self.streak = 0
            return self.allowed()
        ok, jpg = cv.imencode(".jpg", img, [cv.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        jpg = jpg.tobytes()
        try:
            self.sock.sendall(("%d\n" % len(jpg)).encode())
            self.sock.sendall(jpg)
            line = self.answers.readline().decode().strip()
        except (socket.error, socket.timeout):
            line = ""
        parts = line.split()
        if len(parts) == 2 and parts[0] == "water" and float(parts[1]) >= WATER_CONF:
            self.streak += 1
            self.ok_time = time.time()
            self.label = "water"
        else:
            self.streak = 0
            self.label = parts[0] if parts else "no link"
        return self.allowed()

    def allowed(self):
        return self.streak >= WATER_FRAMES and time.time() - self.ok_time < MAX_AGE


class PD:
    def __init__(self, kp, kd):
        self.kp, self.kd = kp, kd
        self.prev_e, self.prev_t = None, None

    def __call__(self, e):
        t = time.time()
        d = 0.0
        if self.prev_t is not None and t > self.prev_t:
            d = (e - self.prev_e) / (t - self.prev_t)
        self.prev_e, self.prev_t = e, t
        return self.kp * e + self.kd * d


def clamp(x, lim=50):
    return max(-lim, min(lim, int(x)))


def stop(auv):
    for i in range(4):
        auv.set_motor_power(i, 0)


def block(auv):
    stop(auv)
    auv.set_rgb_color(50, 0, 0)
    print("Двигатели заблокированы")


def drive(auv, guard, forward, turn, up):
    if not guard.update():
        block(auv)
        return False
    auv.set_motor_power(0, clamp(up))
    auv.set_motor_power(1, clamp(-forward + turn))
    auv.set_motor_power(2, clamp(-forward - turn))
    auv.set_motor_power(3, clamp(up))
    return True


def setup():
    auv = mur.mur_init()

    class NoSend:
        def send(self, *args, **kwargs):
            pass

        def poll(self, *args, **kwargs):
            return 0

    auv.control_v2_socket = NoSend()
    time.sleep(1)
    return auv



def connect():

    while True:

        try:
            sock = socket.create_connection((SERVER_IP, PORT), timeout=10)

            sock.settimeout(10)

            print("Подключился к ноутбуку", SERVER_IP)

            return sock
        
        except (socket.error, socket.timeout) as e:

            print("Нет связи с ноутбуком")
            
            time.sleep(2)


def wait_for_water(auv, guard):
    t0 = time.time()
    while time.time() - t0 < START_TIMEOUT:
        if guard.update():
            return True
    return False


def main():

    camera = cv.VideoCapture(CAMERA_ID)
    camera.set(cv.CAP_PROP_FRAME_WIDTH, WIDTH)
    camera.set(cv.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    camera.set(cv.CAP_PROP_BUFFERSIZE, 1)
    auv = setup()

    guard = WaterGuard(camera, connect())

    depth_pd = PD(DEPTH_KP, DEPTH_KD)

    print("Start")

    try:

        if not wait_for_water(auv, guard):

            block(auv)

            return
        
        auv.set_rgb_color(0, 50, 0)

        for forward, turn, up, duration in PROGRAM:

            t0 = time.time()

            while time.time() - t0 < duration:

                lift = depth_pd(auv.get_depth() - DEPTH) if up is None else up

                if not drive(auv, guard, forward, turn, lift):

                    return
                
                time.sleep(TICK)

        stop(auv)
        print("Программа выполнена")

    finally:
        
        stop(auv)
        time.sleep(0.5)


main()
