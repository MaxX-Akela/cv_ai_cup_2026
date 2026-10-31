import random
import shutil

import cv2

from common import H, ROOT, W, dedup, preprocess

OUT = ROOT / "work/yolo"
BLOCK, GAP, NEG_SHARE = 8, 1, 0.25


def read_box(txt):
    for ln in txt.read_text().split("\n"):
        if ln.strip():
            _, cx, cy, w, h = map(float, ln.split())
            return [(cx - w / 2) * W, (cy - h / 2) * H, (cx + w / 2) * W, (cy + h / 2) * H]
    return None


def split_by_time(names):
    out = {n: ("val" if (i // BLOCK) % 5 == 4 else "train") for i, n in enumerate(names)}
    for i, n in enumerate(names):
        if out[n] == "train":
            for j in range(max(0, i - GAP), min(len(names), i + GAP + 1)):
                if out[names[j]] == "val":
                    out[n] = None
                    break
    return out


def random_crop(img, box, rng):
    for _ in range(50):
        w = rng.randint(110, 190)
        h = w * 3 // 4
        x = rng.randint(0, W - w)
        y = rng.randint(14, H - h)
        if box is None or (x + w < box[0] - 8 or x > box[2] + 8 or y + h < box[1] - 8 or y > box[3] + 8):
            return cv2.resize(img[y:y + h, x:x + w], (W, H), interpolation=cv2.INTER_LINEAR)
    return None


def save(split, name, img, text):
    (OUT / "images" / split).mkdir(parents=True, exist_ok=True)
    (OUT / "labels" / split).mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT / "images" / split / (name + ".png")), img)
    (OUT / "labels" / split / (name + ".txt")).write_text(text)


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    rng = random.Random(0)
    labels = ROOT / "labels"
    names = [p.stem for p in sorted((ROOT / "hummer").glob("*.png")) if (labels / (p.stem + ".txt")).exists()]
    sp = split_by_time(names)
    pos, neg_real = [], []
    for n in names:
        if sp[n] is None:
            continue
        img = preprocess(cv2.imread(str(ROOT / "hummer" / (n + ".png"))))
        lab = labels / (n + ".txt")
        box = read_box(lab)
        if box is None:
            neg_real.append((sp[n], "hum_" + n, img, ""))
        else:
            pos.append((sp[n], "hum_" + n, img, lab.read_text(), box))
    total = 0
    for s, n, img, txt, box in pos:
        save(s, n, img, txt)
        total += 1
        if s == "train":
            _, cx, cy, w, h = map(float, txt.split())
            save(s, n + "_r90", cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE), "0 %.6f %.6f %.6f %.6f\n" % (1 - cy, cx, h, w))
            save(s, n + "_r270", cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE), "0 %.6f %.6f %.6f %.6f\n" % (cy, 1 - cx, h, w))
            total += 2
    for i, p in enumerate(dedup(sorted((ROOT / "no_hammer").glob("*.png")))):
        neg_real.append(("val" if i % 5 == 4 else "train", "neg_" + p.stem, preprocess(cv2.imread(str(p))), ""))
    for s, n, img, txt in neg_real:
        save(s, n, img, txt)
    need = max(0, round(total * NEG_SHARE / (1 - NEG_SHARE)) - len(neg_real))
    by_split = {s: [p for p in pos if p[0] == s] for s in ("train", "val")}
    made, k = 0, 0
    while made < need and pos and k <= 20 * len(pos):
        s = "val" if made % 5 == 4 and by_split["val"] else "train"
        _, n, img, _, box = by_split[s][k % len(by_split[s])]
        k += 1
        c = random_crop(img, box, rng)
        if c is not None:
            save(s, "crop_%d_%s" % (k, n), c, "")
            made += 1
    (OUT / "data.yaml").write_text(
        "path: %s\ntrain: images/train\nval: images/val\nnames:\n  0: tool\n" % OUT.as_posix())
    for s in ("train", "val"):
        n_img = len(list((OUT / "images" / s).glob("*.png")))
        n_pos = sum(1 for t in (OUT / "labels" / s).glob("*.txt") if t.read_text().strip())
        print("%s: %d кадров, с инструментом %d, без %d" % (s, n_img, n_pos, n_img - n_pos))


if __name__ == "__main__":
    main()
