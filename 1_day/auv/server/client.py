import socket
import time
import cv2

SERVER_IP = "10.3.141.50"
PORT = 9000
CAMERA_ID = 0

camera = cv2.VideoCapture(CAMERA_ID)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)


def take_frame():

    ok, img = camera.read()

    ok, jpg = cv2.imencode(".jpg", img)

    return jpg.tobytes()


sock = socket.create_connection((SERVER_IP, PORT))
answers = sock.makefile("rb")

print("Подключился к ноутбуку", SERVER_IP)

while True:

    jpg = take_frame()

    sock.sendall(str(len(jpg)).encode() + b"\n")

    sock.sendall(jpg)

    answer = answers.readline().decode().strip()

    if not answer:

        print("Ноутбук отключился")

        break

    print("Ноутбук ответил:", answer)

    time.sleep(0.5)
