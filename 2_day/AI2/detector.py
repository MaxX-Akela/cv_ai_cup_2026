
import cv2
from ultralytics import YOLOWorld

W, H = 320, 240

class OpenVocabDetector:
    def __init__(self, use_clip=True):
        print("Загружаю YOLO-World...")
        self.model = YOLOWorld("yolov8s-world.pt")
        self.current_prompt = None

    def detect(self, frame, prompt):
        if not prompt:
            return {"box": None, "conf": 0.0}

        # Обновляем текстовую цель только при её изменении
        if prompt != self.current_prompt:
            self.model.set_classes([prompt])
            self.current_prompt = prompt
            print("Новая цель:", prompt)

        # Все координаты приводим к 320x240
        img = cv2.resize(frame, (W, H))

        results = self.model.predict(
            source=img,
            imgsz=320,
            conf=0.10,
            verbose=False
        )

        boxes = results[0].boxes

        if boxes is None or len(boxes) == 0:
            return {"box": None, "conf": 0.0}

        best = int(boxes.conf.argmax().item())

        conf = float(boxes.conf[best].item())
        box = boxes.xyxy[best].cpu().numpy()

        x1, y1, x2, y2 = map(int, box)

        return {
            "box": (x1, y1, x2, y2),
            "conf": conf
        }
