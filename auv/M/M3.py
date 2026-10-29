import io
import sys
import time
import pymurapi as mur

YAW_SIGN = 1
COURSE_1 = 0
COURSE_2 = 90
LEG_1_TIME = 10
LEG_2_TIME = 10
CRUISE = 25
DEPTH = 0.22
TURN_TIMEOUT = 10
TURN_TOLERANCE = 5
SURFACE_TIMEOUT = 8
SURFACE_DEPTH = 0.1
YAW_KP = 0.8
YAW_KD = 0.25
DEPTH_KP = 60
DEPTH_KD = 40


class PD:
    def __init__(self, kp, kd):
        self.kp = kp
        self.kd = kd
        self.prev_e = None
        self.prev_t = None

    def __call__(self, e):
        t = time.time()
        d = 0.0
        if self.prev_t is not None and t > self.prev_t:
            d = (e - self.prev_e) / (t - self.prev_t)
        self.prev_e, self.prev_t = e, t
        return self.kp * e + self.kd * d


def angle_diff(target, current):
    return (target - current + 180) % 360 - 180


def setup():

    if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":

        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

    auv = mur.mur_init()

    class NoSend:

        def send(self, *args, **kwargs):

            pass


        def poll(self, *args, **kwargs):

            return 0

    auv.control_v2_socket = NoSend()

    time.sleep(1)

    return auv


def clamp(x, lim=50):
    return max(-lim, min(lim, int(x)))


def drive(auv, forward, turn, up):

    auv.set_motor_power(0, clamp(up))
    auv.set_motor_power(1, clamp(-forward + turn))
    auv.set_motor_power(2, clamp(-forward - turn))
    auv.set_motor_power(3, clamp(up))


def stop(auv):
    for i in range(4):
        auv.set_motor_power(i, 0)


def hold_course(auv, target, duration, forward, yaw_pd, depth_pd, depth_target, log):

    start = time.time()

    max_err = 0.0

    while time.time() - start < duration:

        err = angle_diff(target, auv.get_yaw())

        turn = YAW_SIGN * yaw_pd(err)

        fwd = forward if abs(err) < 30 else 0

        up = depth_pd(auv.get_depth() - depth_target)

        drive(auv, fwd, turn, up)

        max_err = max(max_err, abs(err))

        log(err)

        time.sleep(0.05)

    return max_err



def turn_to(auv, target, yaw_pd, depth_pd, depth_target, log):
    start = time.time()

    ok_since = None

    while time.time() - start < TURN_TIMEOUT:

        err = angle_diff(target, auv.get_yaw())

        turn = YAW_SIGN * yaw_pd(err)

        up = depth_pd(auv.get_depth() - depth_target)

        drive(auv, 0, turn, up)

        log(err)

        if abs(err) < TURN_TOLERANCE:

            if ok_since is None:

                ok_since = time.time()

            elif time.time() - ok_since > 0.5:

                break
        else:

            ok_since = None

        time.sleep(0.05)


def surface(auv):

    stop(auv)

    time.sleep(0.5)

    start = time.time()

    while time.time() - start < SURFACE_TIMEOUT and auv.get_depth() > SURFACE_DEPTH:

        drive(auv, 0, 0, 30)

        time.sleep(0.05)

    stop(auv)



if __name__ == "__main__":
    auv = setup()
    print("Start")

    try:
        auv.set_rgb_color(0, 50, 0)

        yaw_pd = PD(YAW_KP, YAW_KD)
        depth_pd = PD(DEPTH_KP, DEPTH_KD)

        base = auv.get_yaw()
        course1 = (base + COURSE_1) % 360
        course2 = (base + COURSE_2) % 360

        last = [0.0]

        def log(err):
            now = time.time()
            if now - last[0] > 0.5:
                last[0] = now
                print("Курс:", round(auv.get_yaw(), 1))

        t0 = time.time()

        while time.time() - t0 < 6 and auv.get_depth() < DEPTH - 0.05:

            drive(auv, 0, 0, -30)

            time.sleep(0.05)

        print("Выход на курс 1 и движение")
        turn_to(auv, course1, yaw_pd, depth_pd, DEPTH, log)
        m1 = hold_course(auv, course1, LEG_1_TIME, CRUISE, yaw_pd, depth_pd, DEPTH, log)

        print("Поворот на курс 2")
        turn_to(auv, course2, yaw_pd, depth_pd, DEPTH, log)

        print("Движение по курсу 2")
        m2 = hold_course(auv, course2, LEG_2_TIME, CRUISE, yaw_pd, depth_pd, DEPTH, log)

        print("Остановка и всплытие")
        surface(auv)

        print("Готово")

    finally:

        stop(auv)

        auv.set_rgb_color(0, 0, 0)

        time.sleep(0.5)






        