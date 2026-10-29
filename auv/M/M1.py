import io
import sys
import time
import pymurapi as mur

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

DEPTH = 0.3
HOLD_TIME = 11
DIVE_TIMEOUT = 15
SURFACE_TIMEOUT = 10
SURFACE_DEPTH = 0.1
DEPTH_KP = 80
DEPTH_KD = 60
DEPTH_KI = 15


def set_vertical(auv, up):

    up = max(-50, min(50, int(up)))

    auv.set_motor_power(0, up)

    auv.set_motor_power(3, up)



def stop(auv):

    for i in range(4):

        auv.set_motor_power(i, 0)


def hold_depth(auv, target, duration):
    start = time.time()

    prev_e, prev_t = None, None
    
    integral = 0.0
    
    max_err = 0.0
    
    last_print = 0.0
    
    while time.time() - start < duration:
    
        now = time.time()
    
        err = auv.get_depth() - target
    
        dt = 0.0 if prev_t is None else now - prev_t
    
        d = (err - prev_e) / dt if dt > 0 else 0.0
    
        if abs(err) < 0.2:
    
            integral = max(-2.0, min(2.0, integral + err * dt))
    
        prev_e, prev_t = err, now
    
        set_vertical(auv, DEPTH_KP * err + DEPTH_KD * d + DEPTH_KI * integral)
    
        max_err = max(max_err, abs(err))
    
        if now - last_print > 0.5:
    
            last_print = now
    
            print("Глубина:", round(auv.get_depth(), 2), "ошибка:", round(err, 3))
    
        time.sleep(0.05)
    
    return max_err


if __name__ == "__main__":
    auv = setup()
    
    print("Start")

    try:

        auv.set_rgb_color(0, 50, 0)

        print("Погружение")
        
        t0 = time.time()
        
        while time.time() - t0 < DIVE_TIMEOUT and auv.get_depth() < DEPTH - 0.1:
        
            set_vertical(auv, -35)
        
            time.sleep(0.05)

        print("Удержание глубины")
        
        m = hold_depth(auv, DEPTH, HOLD_TIME)
        
        print("Всплытие")
        
        t0 = time.time()
        
        while time.time() - t0 < SURFACE_TIMEOUT and auv.get_depth() > SURFACE_DEPTH:
        
            set_vertical(auv, 35)
        
            time.sleep(0.05)

        stop(auv)
        
        print("Всплыли")
    
    finally:

        stop(auv)
        
        auv.set_rgb_color(0, 0, 0)
        
        time.sleep(0.5)





        