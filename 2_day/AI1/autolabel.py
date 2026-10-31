import argparse
import shutil

import cv2
import torch
import torchvision
from PIL import Image
from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

from common import H, ROOT, W, dedup, preprocess

PROMPTS = ["hammer", "black hammer with red handle", "hammer on pool floor", "tool", "tool on pool floor"]
MODEL = "IDEA-Research/grounding-dino-tiny"


def detect(proc, model, dev, img):
    boxes, scores = [], []
    for pr in PROMPTS:
        inp = proc(images=img, text=pr + ".", return_tensors="pt").to(dev)
        with torch.no_grad():
            res = model(**inp)
        r = proc.post_process_grounded_object_detection(
            res, inp.input_ids, threshold=0.2, text_threshold=0.2, target_sizes=[img.size[::-1]])[0]
        boxes += r["boxes"].tolist()
        scores += r["scores"].tolist()
    if not boxes:
        return []
    b, s = torch.tensor(boxes), torch.tensor(scores)
    keep = torchvision.ops.nms(b, s, 0.5)
    return sorted(zip(s[keep].tolist(), b[keep].tolist()), reverse=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default="hummer")
    ap.add_argument("--thr", type=float, default=0.4)
    a = ap.parse_args()
    frames = ROOT / a.folder
    labels = ROOT / "labels"
    preview = ROOT / "work/preview"
    labels.mkdir(exist_ok=True)
    shutil.rmtree(preview, ignore_errors=True)
    preview.mkdir(parents=True)
    todo = [p for p in sorted(frames.glob("*.png")) if not (labels / (p.stem + ".txt")).exists()]
    todo = dedup(todo)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    proc = AutoProcessor.from_pretrained(MODEL)
    model = AutoModelForZeroShotObjectDetection.from_pretrained(MODEL).to(dev).eval()
    doubtful = []
    for p in todo:
        img = preprocess(cv2.imread(str(p)))
        dets = detect(proc, model, dev, Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
        text = ""
        if dets and dets[0][0] >= a.thr:
            x1, y1, x2, y2 = dets[0][1]
            text = "0 %.6f %.6f %.6f %.6f\n" % ((x1 + x2) / 2 / W, (y1 + y2) / 2 / H, (x2 - x1) / W, (y2 - y1) / H)
            cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
        else:
            doubtful.append(p.name)
        (labels / (p.stem + ".txt")).write_text(text)
        cv2.imwrite(str(preview / (p.stem + ".jpg")), img)
    (ROOT / "work/doubtful.txt").write_text("\n".join(doubtful))
    print("размечено: %d, без бокса: %d (список work/doubtful.txt, кадры work/preview)" % (len(todo), len(doubtful)))


if __name__ == "__main__":
    main()
