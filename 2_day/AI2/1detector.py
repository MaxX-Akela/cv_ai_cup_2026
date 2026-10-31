import cv2
import numpy as np
import torch
from PIL import Image
from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor, CLIPModel, CLIPProcessor
W, H = (320, 240)
DINO = 'IDEA-Research/grounding-dino-tiny'
CLIP = 'openai/clip-vit-base-patch32'
DISTRACTORS = ['a photo of the empty pool floor', 'a photo of a hammer', 'a photo of a wire or a cable', 'a photo of a hand']

def _clip_text(prompt):
    p = prompt.strip().lower()
    return 'a photo of ' + (p if p.split(' ')[0] in ('a', 'an', 'the') else 'a ' + p)

class OpenVocabDetector:

    def __init__(self, use_clip=True):
        self.dev = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.dino_proc = AutoProcessor.from_pretrained(DINO)
        self.dino = AutoModelForZeroShotObjectDetection.from_pretrained(DINO).to(self.dev).eval()
        self.use_clip = use_clip
        if use_clip:
            self.clip_proc = CLIPProcessor.from_pretrained(CLIP)
            self.clip = CLIPModel.from_pretrained(CLIP).to(self.dev).eval()

    @torch.no_grad()
    def detect(self, bgr, prompt):
        if bgr.shape[1] != W or bgr.shape[0] != H:
            bgr = cv2.resize(bgr, (W, H), interpolation=cv2.INTER_AREA)
        img = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        text = prompt.strip().lower().rstrip('.') + '.'
        inp = self.dino_proc(images=img, text=text, return_tensors='pt').to(self.dev)
        res = self.dino(**inp)
        r = self.dino_proc.post_process_grounded_object_detection(res, inp.input_ids, threshold=0.15, text_threshold=0.15, target_sizes=[(H, W)])[0]
        if len(r['scores']) == 0:
            return dict(conf=0.0, det=0.0, clip=0.0, box=None)
        i = int(r['scores'].argmax())
        det = float(r['scores'][i])
        box = [float(v) for v in r['boxes'][i]]
        clip_p = 1.0
        if self.use_clip:
            mx, my = (0.1 * (box[2] - box[0]), 0.1 * (box[3] - box[1]))
            x1, y1 = (max(0, int(box[0] - mx)), max(0, int(box[1] - my)))
            x2, y2 = (min(W, int(box[2] + mx) + 1), min(H, int(box[3] + my) + 1))
            crop = img.crop((x1, y1, max(x2, x1 + 2), max(y2, y1 + 2)))
            ci = self.clip_proc(text=[_clip_text(prompt)] + DISTRACTORS, images=crop, return_tensors='pt', padding=True).to(self.dev)
            logits = self.clip(**ci).logits_per_image[0]
            clip_p = float(logits.softmax(-1)[0])
        return dict(conf=float(np.sqrt(det * clip_p)), det=det, clip=clip_p, box=box)
