import socket
import time

import cv2
import numpy as np


def serve(port, handle, window):
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen(1)
    print("Жду робота на порту", port)
    conn, addr = server.accept()
    robot = conn.makefile("rb")
    print("Робот подключился:", addr[0])
    n, t0, n0 = 0, time.time(), 0
    while True:
        line = robot.readline()
        if not line:
            break
        jpg = robot.read(int(line))
        frame = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            conn.sendall(b"error\n")
            continue
        n += 1
        answer, vis = handle(frame)
        conn.sendall((answer + "\n").encode())
        cv2.imshow(window, vis)
        if cv2.waitKey(1) == ord("q"):
            break
        if time.time() - t0 >= 1:
            print("FPS: %.1f  | кадр %d: %s" % ((n - n0) / (time.time() - t0), n, answer))
            t0, n0 = time.time(), n
    print("Связь закончилась, принято кадров:", n)
