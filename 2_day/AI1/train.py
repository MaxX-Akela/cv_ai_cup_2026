import argparse
import shutil

import torch
from ultralytics import YOLO

from common import ROOT

DATA = ROOT / "work/yolo"


def false_positives(model, split, conf=0.5):
    empty = [p for p in sorted((DATA / "images" / split).glob("*.png"))
             if not (DATA / "labels" / split / (p.stem + ".txt")).read_text().strip()]
    if not empty:
        return 0, 0
    res = model.predict([str(p) for p in empty], imgsz=320, conf=conf, verbose=False)
    return sum(1 for r in res if len(r.boxes)), len(empty)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=str(ROOT / "yolo11n.pt"))
    ap.add_argument("--epochs", type=int, default=300)
    ap.add_argument("--patience", type=int, default=60)
    a = ap.parse_args()
    device = 0 if torch.cuda.is_available() else "cpu"
    YOLO(a.model).train(
        data=str(DATA / "data.yaml"), imgsz=320, epochs=a.epochs, patience=a.patience,
        batch=16, device=device, workers=2, seed=0,
        project=str(ROOT / "runs"), name="tool", exist_ok=True,
        hsv_h=0.05, hsv_s=0.8, hsv_v=0.5,
        flipud=0.5, fliplr=0.5, degrees=15, translate=0.1, scale=0.4, mosaic=1.0,
    )
    best = ROOT / "runs/tool/weights/best.pt"
    (ROOT / "models").mkdir(exist_ok=True)
    shutil.copy(best, ROOT / "models/hammer.pt")
    m = YOLO(str(best))
    r = m.val(data=str(DATA / "data.yaml"), imgsz=320, device=device, verbose=False)
    print("mAP50 val: %.3f  mAP50-95: %.3f" % (r.box.map50, r.box.map))
    for split in ("val", "train"):
        bad, n = false_positives(m, split)
        print("ложные срабатывания на пустых кадрах %s: %d из %d" % (split, bad, n))


if __name__ == "__main__":
    main()
