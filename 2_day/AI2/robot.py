import io
import socket
import sys
import time
import cv2 as cv
import pymurapi as mur

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)

SERVER_IP = '10.3.141.50'
PORT = 9000

CAMERA_ID = 0
WIDTH, HEIGHT = (320, 240)
JPEG_QUALITY = 90
TURN_SIGN = 1
SEARCH_POWER = 18
MAX_POWER = 25
MIN_POWER = 10
KP = 40.0
TOLERANCE = 0.1
HOLD_FRAMES = 4
LOST_SECONDS = 1.5
SEARCH_TIMEOUT = 240
LIGHT_SECONDS = 10
DEPTH = 0.22
DEPTH_KP = 60
DEPTH_KD = 40
LIGHT = (50, 50, 50)

class PD:

    def __init__(self, kp, kd):
        self.kp, self.kd = (kp, kd)
        self.prev_e, self.prev_t = (None, None)

    def __call__(self, e):
        t = time.time()
        d = 0.0
        if self.prev_t is not None and t > self.prev_t:
            d = (e - self.prev_e) / (t - self.prev_t)
        self.prev_e, self.prev_t = (e, t)
        return self.kp * e + self.kd * d

def clamp(x, lim=50):
    return max(-lim, min(lim, int(x)))

def drive(auv, turn, up, forward=0):
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
        return (False, 0.0, 0.0)
    ok, jpg = cv.imencode('.jpg', img, [cv.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    jpg = jpg.tobytes()
    sock.sendall(('%d\n' % len(jpg)).encode())
    sock.sendall(jpg)
    line = answers.readline().decode().strip()
    if not line:
        return None
    parts = line.split()
    if parts[0] == '1' and len(parts) >= 6:
        cx = float(parts[2])
        return (True, float(parts[1]), (cx - WIDTH / 2.0) / (WIDTH / 2.0))
    return (False, float(parts[1]) if len(parts) > 1 else 0.0, 0.0)

def main():
    camera = cv.VideoCapture(CAMERA_ID)
    camera.set(cv.CAP_PROP_FRAME_WIDTH, WIDTH)
    camera.set(cv.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    camera.set(cv.CAP_PROP_BUFFERSIZE, 1)
    auv = setup()
    sock = connect()
    answers = sock.makefile('rb')
    depth_pd = PD(DEPTH_KP, DEPTH_KD)
    print('Start: ищу предмет по описанию, введённому на ноутбуке')
    ok_frames = 0
    last_seen = None
    last_err = 0.0
    last_dir = 1.0
    found_light = False
    t0 = time.time()
    try:
        auv.set_rgb_color(0, 50, 0)
        while time.time() - t0 < SEARCH_TIMEOUT:
            res = ask(camera, sock, answers)
            if res is None:
                print('Ноутбук отключился')
                break
            found, conf, err = res
            up = depth_pd(auv.get_depth() - DEPTH)
            now = time.time()
            if found:
                last_seen, last_err = (now, err)
                last_dir = 1.0 if err > 0 else -1.0
                if abs(err) < TOLERANCE:
                    ok_frames += 1
                    drive(auv, 0, up)
                    if ok_frames >= HOLD_FRAMES:
                        found_light = True
                        break
                    continue
                ok_frames = 0
                power = max(MIN_POWER, min(MAX_POWER, KP * abs(err)))
                drive(auv, TURN_SIGN * last_dir * power, up)
            else:
                ok_frames = 0
                if last_seen is not None and now - last_seen < LOST_SECONDS:
                    drive(auv, TURN_SIGN * (1.0 if last_err > 0 else -1.0) * MIN_POWER, up)
                else:
                    drive(auv, TURN_SIGN * SEARCH_POWER, up)
            print('найден=%s conf=%.2f ошибка=%.2f' % (found, conf, err))
        stop(auv)
        if found_light:
            print('Предмет в центре: стоп, подсветка включена')
            auv.set_rgb_color(*LIGHT)
            t1 = time.time()
            while time.time() - t1 < LIGHT_SECONDS:
                drive(auv, 0, depth_pd(auv.get_depth() - DEPTH))
                time.sleep(0.05)
            stop(auv)
        else:
            print('Предмет не найден, останавливаюсь')
            auv.set_rgb_color(0, 0, 0)
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
