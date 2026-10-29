import socket

import cv2
import numpy as np

PORT = 9000

server = socket.socket()
server.bind(("0.0.0.0", PORT))
server.listen(1)

print("Жду робота на порту", PORT, "(адрес ноутбука: ipconfig)")

conn, addr = server.accept()
robot = conn.makefile("rb")

print("Робот подключился:", addr[0])

n = 0
while True:

    line = robot.readline()

    if not line:
        break

    jpg = robot.read(int(line))
    frame = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
    n += 1

    cv2.imshow("robot", frame)

    if cv2.waitKey(1) == ord("q"):
        break

    answer = "кадр %d, %dx%d" % (n, frame.shape[1], frame.shape[0])
    conn.sendall((answer + "\n").encode())
    
print("Связь закончилась, принято кадров:", n)
