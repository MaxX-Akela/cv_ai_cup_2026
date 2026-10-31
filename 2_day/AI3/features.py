import cv2
import numpy as np

from common import preprocess

HUE_BINS, SAT_BINS = 16, 8


def _ms(ch, name):
    return {name + "_mean": float(ch.mean()), name + "_std": float(ch.std())}


def feature_dict(img):
    img = preprocess(img)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    f = {}
    for i, n in enumerate("HSV"):
        f.update(_ms(hsv[..., i], n))
    for i, n in enumerate(["L", "a", "b"]):
        f.update(_ms(lab[..., i], n))
    hh = np.bincount((hsv[..., 0].astype(int) * HUE_BINS // 180).ravel(), minlength=HUE_BINS)[:HUE_BINS]
    sh = np.bincount((hsv[..., 1].astype(int) * SAT_BINS // 256).ravel(), minlength=SAT_BINS)[:SAT_BINS]
    for i, v in enumerate(hh / hh.sum()):
        f["hue_%02d" % i] = float(v)
    for i, v in enumerate(sh / sh.sum()):
        f["sat_%d" % i] = float(v)
    f["sharpness"] = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    f["contrast"] = float(gray.std())
    f["overexposed"] = float((gray >= 250).mean())
    b, g, r = [img[..., i].astype(np.float32).mean() for i in range(3)]
    f["b_over_r"] = float(b / (r + 1e-3))
    f["g_over_r"] = float(g / (r + 1e-3))
    return f


FEATURE_NAMES = list(feature_dict(np.zeros((240, 320, 3), np.uint8)))


def features(img):
    d = feature_dict(img)
    return np.array([d[n] for n in FEATURE_NAMES], dtype=np.float32)
