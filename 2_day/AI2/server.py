import argparse
import socket
import threading
import time
import cv2 as cv
import numpy as np
from ultralytics import YOLOWorld

W, H = 320, 240

class OpenVocabDetector:
    def __init__(self, use_clip=True):
        self.model = YOLOWorld("yolov8s-world.pt")
        self.current_prompt = None

    def detect(self, frame, prompt):
        if not prompt:
            return {"box": None, "conf": 0.0}

        if prompt != self.current_prompt:
            self.model.set_classes([prompt])
            self.current_prompt = prompt
            print("Новая цель:", prompt)

        img = cv.resize(frame, (W, H))

        results = self.model.predict(
            source=img,
            imgsz=320,
            conf=0.10,
            verbose=False
        )

        boxes = results[0].boxes

        if boxes is None or len(boxes) == 0:
            return {"box": None, "conf": 0.0}

        best = int(boxes.conf.argmax().item())

        conf = float(boxes.conf[best].item())
        box = boxes.xyxy[best].cpu().numpy()

        x1, y1, x2, y2 = map(int, box)

        return {
            "box": (x1, y1, x2, y2),
            "conf": conf
        }


ap = argparse.ArgumentParser()
ap.add_argument('--port', type=int, default=9000)
ap.add_argument('--thr', type=float, default=0.35)
ap.add_argument('--no-clip', action='store_true')
a = ap.parse_args()
state = dict(prompt='', thr=a.thr, quit=False)

def console():
    while not state['quit']:
        try:
            line = input('описание> ').strip()
        except EOFError:
            return
        if line == 'quit':
            state['quit'] = True
        elif line.startswith('thr '):
            state['thr'] = float(line[4:])
            print('порог =', state['thr'])
        elif line:
            state['prompt'] = line
            print('ищу:', line)

det = OpenVocabDetector(use_clip=not a.no_clip)
det.detect(np.zeros((H, W, 3), np.uint8), 'pliers')
state['prompt'] = 'pliers'
threading.Thread(target=console, daemon=True).start()
server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('0.0.0.0', a.port))
server.listen(1)
print('Жду робота на порту', a.port, '(адрес ноутбука: ipconfig)')
conn, addr = server.accept()
robot = conn.makefile('rb')
print('Робот подключился:', addr[0])
n, t0, n0 = (0, time.time(), 0)


while not state['quit']:

    line = robot.readline()

    if not line:
        break
    frame = cv.imdecode(np.frombuffer(robot.read(int(line)), np.uint8), cv.IMREAD_COLOR)

    n += 1

    prompt, thr = (state['prompt'], state['thr'])
    vis = cv.resize(frame, (W, H))

    if not prompt:
        answer = '0 0.00'
        cv.putText(vis, 'enter description in console', (6, 20), 0, 0.5, (0, 0, 255), 1)
    
    else:

        r = det.detect(frame, prompt)

        if r['box'] is not None and r['conf'] >= thr:

            x1, y1, x2, y2 = r['box']
            answer = '1 %.2f %d %d %d %d' % (r['conf'], (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1)
            cv.rectangle(vis, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            cv.putText(vis, '%s %.2f' % (prompt, r['conf']), (6, 20), 0, 0.55, (0, 255, 0), 2)
        
        else:

            answer = '0 %.2f' % r['conf']
            cv.putText(vis, 'not found (%.2f)' % r['conf'], (6, 20), 0, 0.55, (0, 0, 255), 2)
    
    conn.sendall((answer + '\n').encode())


    cv.line(vis, (W // 2, 0), (W // 2, H), (255, 255, 0), 1)
    cv.imshow('W-AI2', cv.resize(vis, (W * 2, H * 2)))

    if cv.waitKey(1) == ord('q'):
        break
    
    if time.time() - t0 >= 1:
        print('FPS: %.1f | %s | %s' % ((n - n0) / (time.time() - t0), prompt or '-', answer))
        t0, n0 = (time.time(), n)

print('Связь закончилась, принято кадров:', n)
