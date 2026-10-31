import argparse
from pathlib import Path

import cv2
import numpy as np
from catboost import CatBoostClassifier
from sklearn.metrics import accuracy_score, confusion_matrix

from common import ROOT, dedup
from features import FEATURE_NAMES, features

BLOCK, GAP = 8, 1


def time_split(files):
    is_val = [(i // BLOCK) % 5 == 4 for i in range(len(files))]
    va = [p for p, v in zip(files, is_val) if v]
    tr = [p for i, p in enumerate(files) if not any(is_val[max(0, i - GAP):i + GAP + 1])]
    return tr, va


def folder_files(d):
    return dedup(sorted(Path(d).glob("*.png")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--water", nargs="*", default=[str(ROOT / "water/hummer"), str(ROOT / "water/air_wattre")])
    ap.add_argument("--air", nargs="*", default=[str(ROOT / "air")])
    a = ap.parse_args()
    groups = [(0, folder_files(d)) for d in a.water] + [(1, folder_files(d)) for d in a.air]
    data = {"train": ([], []), "val": ([], [])}
    for y, files in groups:
        tr, va = time_split(files)
        for name, fs in (("train", tr), ("val", va)):
            for p in fs:
                data[name][0].append(features(cv2.imread(str(p))))
                data[name][1].append(y)
    Xtr, ytr = np.array(data["train"][0]), np.array(data["train"][1])
    Xva, yva = np.array(data["val"][0]), np.array(data["val"][1])
    print("train: %d (air %d), val: %d (air %d)" % (len(ytr), ytr.sum(), len(yva), yva.sum()))
    model = CatBoostClassifier(iterations=300, depth=5, learning_rate=0.08, verbose=50,
                               auto_class_weights="Balanced", random_seed=0)
    model.fit(Xtr, ytr, eval_set=(Xva, yva))
    pred = model.predict(Xva).astype(int).ravel()
    print("accuracy val: %.3f" % accuracy_score(yva, pred))
    print(confusion_matrix(yva, pred, labels=[0, 1]))
    for n, v in sorted(zip(FEATURE_NAMES, model.get_feature_importance()), key=lambda t: -t[1])[:12]:
        print("  %-12s %.1f" % (n, v))
    (ROOT / "models").mkdir(exist_ok=True)
    model.save_model(str(ROOT / "models/water_air.cbm"))


if __name__ == "__main__":
    main()
