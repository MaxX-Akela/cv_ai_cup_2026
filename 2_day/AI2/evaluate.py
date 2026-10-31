import argparse
from pathlib import Path
import cv2
import numpy as np
from detector import OpenVocabDetector
ap = argparse.ArgumentParser()
ap.add_argument('dir')
ap.add_argument('--prompt', action='append', required=True, help='папка=описание')
ap.add_argument('--no-clip', action='store_true')
ap.add_argument('--thr', type=float, default=0.35)
a = ap.parse_args()
root = Path(a.dir)
files = {}
for d in sorted((p for p in root.iterdir() if p.is_dir())):
    files[d.name] = sorted((p for p in d.iterdir() if p.suffix.lower() in ('.jpg', '.jpeg', '.png')))
print({k: len(v) for k, v in files.items()})
det = OpenVocabDetector(use_clip=not a.no_clip)
for item in a.prompt:
    cls, text = item.split('=', 1)
    rows = []
    for k, fs in files.items():
        for f in fs:
            rows.append((det.detect(cv2.imread(str(f)), text)['conf'], k == cls, f))
    pos = np.array([r[0] for r in rows if r[1]])
    neg = np.array([r[0] for r in rows if not r[1]])
    print("\n=== '%s' (папка %s): свои %d, чужие %d" % (text, cls, len(pos), len(neg)))
    if len(pos) == 0 or len(neg) == 0:
        print('нужны кадры и с предметом, и без')
        continue
    print('уверенность на своих: медиана %.2f (min %.2f)   на чужих: медиана %.2f (max %.2f)' % (np.median(pos), pos.min(), np.median(neg), neg.max()))
    best = max(np.arange(0.05, 0.95, 0.01), key=lambda t: (pos >= t).sum() + (neg < t).sum())
    for name, t in (('порог по умолчанию', a.thr), ('лучший порог', best)):
        tp, tn = ((pos >= t).sum(), (neg < t).sum())
        print('%s %.2f: найдено %d/%d, правильно отвергнуто %d/%d, accuracy %.3f' % (name, t, tp, len(pos), tn, len(neg), (tp + tn) / (len(pos) + len(neg))))
    wrong = [(c, p) for c, ispos, p in rows if (c >= a.thr) != ispos]
    for c, p in sorted(wrong, key=lambda t: -t[0])[:10]:
        print('  ошибка %.2f  %s/%s' % (c, p.parent.name, p.name))
