import cv2
import numpy as np
import face_recognition
import json
from ultralytics import YOLO

class OmegaAI:
    def __init__(self):
        self.model = YOLO("models/yolov8n.pt")
        self.target_classes = [0, 2, 3, 7] # Personne, Voiture, Moto, Bus
        self.track_history = {} # Pour le calcul du passage de ligne

    def get_face_signature(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        encodings = face_recognition.face_encodings(rgb)
        return encodings[0] if encodings else None

    def process_video(self, video_path, line_y_ratio=0.6):
        cap = cv2.VideoCapture(video_path)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        line_y = int(height * line_y_ratio)
        
        counts = {"person": 0, "car": 0, "motorcycle": 0, "bus": 0}
        crossed_ids = set()

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break

            # Tracking YOLO
            results = self.model.track(frame, persist=True, verbose=False)
            
            if results[0].boxes.id is not None:
                boxes = results[0].boxes.xyxy.cpu().numpy()
                ids = results[0].boxes.id.cpu().numpy().astype(int)
                clss = results[0].boxes.cls.cpu().numpy().astype(int)

                for box, obj_id, cls in zip(boxes, ids, clss):
                    center_y = int((box[1] + box[3]) / 2)
                    class_name = self.model.names[cls]

                    # Logique de comptage : si le centre passe la ligne
                    if center_y > line_y and obj_id not in crossed_ids:
                        if class_name in counts:
                            counts[class_name] += 1
                            crossed_ids.add(obj_id)

        cap.release()
        return counts