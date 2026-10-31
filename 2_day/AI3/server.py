import argparse

import cv2 as cv
from catboost import CatBoostClassifier

from common import H, ROOT, W, preprocess
from features import features
from robot_link import serve

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=9001)
ap.add_argument("--model", default=str(ROOT / "models/water_air.cbm"))
a = ap.parse_args()

cb = CatBoostClassifier()
cb.load_model(a.model)


def handle(frame):

    img = preprocess(frame)

    pa = float(cb.predict_proba(features(img).reshape(1, -1))[0][1])

    label, conf = ("air", pa) if pa >= 0.5 else ("water", 1 - pa)

    vis = img.copy()
    
    
    
    cv.putText(vis, "%s %.2f" % (label, conf), (8, 40), 0, 1.0,(0, 200, 255) if label == "air" else (255, 200, 0), 2)
    return "%s %.2f" % (label, conf), cv.resize(vis, (W * 2, H * 2))



serve(a.port, handle, "ai3")
