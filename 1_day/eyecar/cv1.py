import os
import signal
import sys
import time
import pigpio

STOP = 1500
STRAIGHT = 90
LEFT = 80
RIGHT = 100
SPEED = 1540

SLOW_SPEED = 1520
SIGN_DIR = "signs"
SIGN_THRESHOLD = 0.72
SIGN_COOLDOWN = 4.0
MAX_RUN_SECONDS = 60

SIGN_ACTIONS = {
    "stop": ("pause", 3.0),
    "no_entry": ("halt", 0),
    "road_works": ("slow", 3.0),
    "speed_bump": ("slow", 3.0),
    "crosswalk": ("pause", 1.0),
    "yield": ("pause", 1.0),
    "parking": ("halt", 0),
}


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


def load_templates(cv2, names):
    templates = {}
    for name in names:
        path = os.path.join(SIGN_DIR, name + ".png")
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise RuntimeError("Нет шаблона " + path)
        templates[name] = img
    return templates


def match_sign(cv2, gray, template):
    best = 0.0
    for scale in (0.5, 0.65, 0.8, 1.0, 1.25, 1.5):
        resized = cv2.resize(template, None, fx=scale, fy=scale)
        if resized.shape[0] > gray.shape[0] or resized.shape[1] > gray.shape[1]:
            continue
        score = cv2.matchTemplate(gray, resized, cv2.TM_CCOEFF_NORMED).max()
        if score > best:
            best = score
    return best


def detect_sign(cv2, frame, templates):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    found = None
    best = SIGN_THRESHOLD
    for name, template in templates.items():
        score = match_sign(cv2, gray, template)
        if score > best:
            best = score
            found = name
    return found


def run_signs(pi, ESC, STEER, names):
    import cv2

    templates = load_templates(cv2, names)
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Камера не открылась")
    start = time.time()
    speed = SPEED
    slow_until = 0.0
    ignore_until = 0.0
    try:
        control(pi, ESC, speed, STEER, STRAIGHT)
        while time.time() - start < MAX_RUN_SECONDS:
            ok, frame = cap.read()
            if not ok:
                continue
            now = time.time()
            if now > slow_until and speed != SPEED:
                speed = SPEED
                control(pi, ESC, speed, STEER, STRAIGHT)
            if now < ignore_until:
                continue
            name = detect_sign(cv2, frame, templates)
            if name is None:
                continue
            action, value = SIGN_ACTIONS[name]
            print(name, action)
            if action == "slow":
                speed = SLOW_SPEED
                slow_until = now + value
                ignore_until = now + 1.0
                control(pi, ESC, speed, STEER, STRAIGHT)
            elif action == "pause":
                control(pi, ESC, STOP, STEER, STRAIGHT)
                time.sleep(value)
                cap.grab()
                control(pi, ESC, speed, STEER, STRAIGHT)
                ignore_until = time.time() + SIGN_COOLDOWN
            else:
                control(pi, ESC, STOP, STEER, STRAIGHT)
                break
    finally:
        control(pi, ESC, STOP, STEER, STRAIGHT)
        cap.release()


if __name__ == "__main__":
    sign_names = sys.argv[1:3]
    if len(sign_names) != 2 or any(n not in SIGN_ACTIONS for n in sign_names):
        print("python3 cv1.py <знак1> <знак2>:", ", ".join(SIGN_ACTIONS))
        sys.exit(1)

    pi, ESC, STEER = setup_gpio()
    signal.signal(signal.SIGHUP, signal.default_int_handler)

    try:
        control(pi, ESC, STOP, STEER, STRAIGHT)
        print("Start")
        time.sleep(2)
        run_signs(pi, ESC, STEER, sign_names)
    finally:
        control(pi, ESC, STOP, STEER, STRAIGHT)
        time.sleep(0.5)
        pi.set_servo_pulsewidth(ESC, 0)
        pi.set_servo_pulsewidth(STEER, 0)
        pi.stop()
