import io
import socket
import sys
import time

import cv2 as cv
import pymurapi as mur

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

SERVER_IP = "10.3.141.100"
PORT = 9000
CAMERA_ID = 0
WIDTH, HEIGHT = 320, 240
JPEG_QUALITY = 90

DEPTH = 0.3
DEPTH_KP = 60
DEPTH_KD = 40
TURN_SIGN = 1
FWD_SIGN = 1
CRUISE = 25
SEARCH_TURN_POWER = 20
SEARCH_TURN_SECONDS = 2.0
LEG_BASE = 4.0
LEG_STEP = 3.0
MAX_LEG = 14.0
MAX_LEGS = 8
SEARCH_TIMEOUT = 300
CONFIRM = 2
LOST_SECONDS = 2.0
KX = 35.0
KY = 35.0
MAX_POWER = 25
MIN_POWER = 10
TOL_X = 0.12
TOL_Y = 0.15
APPROACH_X = 0.4
HOLD_FRAMES = 4
LIGHT_SECONDS = 15
LIGHT = (50, 50, 50)


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


def power(e, k):
    return (1 if e > 0 else -1) * max(MIN_POWER, min(MAX_POWER, k * abs(e)))


def drive(auv, forward, turn, up):
    auv.set_motor_power(0, clamp(up))
    auv.set_motor_power(1, clamp(-forward + turn))
    auv.set_motor_power(2, clamp(-forward - turn))
    auv.set_motor_power(3, clamp(up))


def stop(auv):
    for i in range(4):
        auv.set_motor_power(i, 0)


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


def ask(camera, sock, answers):

    camera.grab()
    camera.grab()
    ok, img = camera.read()

    if not ok or img is None:
        return (False, 0.0, 0.0, 0.0)
    
    ok, jpg = cv.imencode(".jpg", img, [cv.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])

    jpg = jpg.tobytes()

    sock.sendall(("%d\n" % len(jpg)).encode())

    sock.sendall(jpg)

    line = answers.readline().decode().strip()

    if not line:

        return None
    
    parts = line.split()

    if parts[0] == "1" and len(parts) >= 6:

        cx, cy = float(parts[1]), float(parts[2])

        return (True, float(parts[5]), (cx - WIDTH / 2.0) / (WIDTH / 2.0), (cy - HEIGHT / 2.0) / (HEIGHT / 2.0))
    
    return (False, 0.0, 0.0, 0.0)


class SearchPath:
    def __init__(self):
        self.k = 0
        self.phase = "go"
        self.t = time.time()

    def command(self):
        now = time.time()
        if self.phase == "turn":
            if now - self.t < SEARCH_TURN_SECONDS:
                return 0, TURN_SIGN * SEARCH_TURN_POWER
            self.phase = "go"
            self.t = now
        if now - self.t >= min(MAX_LEG, LEG_BASE + LEG_STEP * (self.k // 2)):
            self.k = (self.k + 1) % MAX_LEGS
            self.phase = "turn"
            self.t = now
            return 0, TURN_SIGN * SEARCH_TURN_POWER
        return CRUISE, 0


def main():
    camera = cv.VideoCapture(CAMERA_ID)
    camera.set(cv.CAP_PROP_FRAME_WIDTH, WIDTH)
    camera.set(cv.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    camera.set(cv.CAP_PROP_BUFFERSIZE, 1)
    auv = setup()
    sock = connect()
    answers = sock.makefile("rb")
    depth_pd = PD(DEPTH_KP, DEPTH_KD)
    path = SearchPath()
    mode = "search"
    hits = 0
    last_seen = 0.0
    ok_frames = 0
    arrived = False
    t0 = time.time()
    print("Поиск молотка")
    try:
        while time.time() - t0 < SEARCH_TIMEOUT:
            res = ask(camera, sock, answers)
            if res is None:
                print("Ноутбук отключился")
                break
            found, conf, ex, ey = res
            now = time.time()
            up = depth_pd(auv.get_depth() - DEPTH)
            if found:
                last_seen = now
            if mode == "search":
                hits = hits + 1 if found else 0
                if hits >= CONFIRM:
                    mode = "track"
                    ok_frames = 0
                    print("молоток найден")
                    continue
                forward, turn = path.command()
                drive(auv, forward, turn, up)
                continue
            if not found:
                if now - last_seen > LOST_SECONDS:
                    print("малаток потерян")
                    mode, hits = "search", 0
                    path = SearchPath()
                else:
                    drive(auv, 0, 0, up)
                continue
            turn = TURN_SIGN * power(ex, KX) if abs(ex) > TOL_X else 0
            forward = FWD_SIGN * power(-ey, KY) if abs(ey) > TOL_Y and abs(ex) < APPROACH_X else 0
            if turn == 0 and forward == 0 and abs(ex) <= TOL_X and abs(ey) <= TOL_Y:
                ok_frames += 1
                drive(auv, 0, 0, up)
                if ok_frames >= HOLD_FRAMES:
                    arrived = True
                    break
                continue
            ok_frames = 0
            drive(auv, forward, turn, up)
        stop(auv)
        if arrived:
            auv.set_rgb_color(*LIGHT)
            print("Над vjkjnjrjv")
            t1 = time.time()
            while time.time() - t1 < LIGHT_SECONDS:
                drive(auv, 0, 0, depth_pd(auv.get_depth() - DEPTH))
                time.sleep(0.05)
        else:
            print("vjkjnjr не найден")
    except BaseException:
        auv.set_rgb_color(0, 0, 0)
        raise
    finally:
        stop(auv)
        try:
            sock.close()
        except Exception:
            pass


main()
