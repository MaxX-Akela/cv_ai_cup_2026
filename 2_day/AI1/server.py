import argparse
import cv2 as cv
import numpy as np
from ultralytics import YOLO
from common import H, ROOT, W, preprocess
from robot_link import serve

ap = argparse.ArgumentParser()
ap.add_argument("--conf", type=float, default=0.5)
ap.add_argument("--port", type=int, default=9000)
ap.add_argument("--model", default=str(ROOT / "models/hammer.pt"))
ap.add_argument("--norm", action="store_true")
a = ap.parse_args()

model = YOLO(a.model)

model.predict(np.zeros((H, W, 3), np.uint8), imgsz=320, verbose=False)


def handle(frame):
    
    img = preprocess(frame)
    
    r = model.predict(img, imgsz=320, conf=a.conf, verbose=False)[0]
    
    vis = img.copy()
    
    if len(r.boxes) == 0:
     
        cv.putText(vis, "no hummer", (8, 30), 0, 0.8, (0, 0, 255), 2)
    
        return "0", cv.resize(vis, (W * 2, H * 2))
    
    i = int(r.boxes.conf.argmax())
    
    cx, cy, w, h = r.boxes.xywh[i].tolist()
    
    conf = float(r.boxes.conf[i])
    
    cv.rectangle(vis, (int(cx - w / 2), int(cy - h / 2)), (int(cx + w / 2), int(cy + h / 2)), (0, 255, 0), 2)
    
    cv.putText(vis, "tool %.2f" % conf, (8, 30), 0, 0.8, (0, 255, 0), 2)

    if a.norm:


        ans = "1 %.4f %.4f %.4f %.4f %.2f" % (cx / W, cy / H, w / W, h / H, conf)
    else:

        ans = "1 %d %d %d %d %.2f" % (cx, cy, w, h, conf)
    return ans, cv.resize(vis, (W * 2, H * 2))


serve(a.port, handle, "ai1")






