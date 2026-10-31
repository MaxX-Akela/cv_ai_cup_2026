from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
W, H = 320, 240
TELEMETRY_ROWS = 12


def preprocess(img):
    if img.shape[1] != W or img.shape[0] != H:
        img = cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)
    else:
        img = img.copy()
    img[:TELEMETRY_ROWS] = img[TELEMETRY_ROWS]
    return img


def thumb(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.resize(g, (32, 24), interpolation=cv2.INTER_AREA).astype(np.float32)


def dedup(paths, thr=6):
    kept, last = [], None
    for p in paths:
        t = thumb(preprocess(cv2.imread(str(p))))
        if last is None or np.abs(t - last).mean() >= thr:
            kept.append(p)
            last = t
    return kept
