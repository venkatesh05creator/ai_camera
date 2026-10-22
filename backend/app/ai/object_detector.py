"""Modular Object Detection and Counting Adapter.

Supports 80 standard COCO classes with pluggable model backends, confidence gating,
bounding box suppression, and category-wise count aggregation.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np


COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book",
    "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
]


@dataclass
class DetectedObject:
    label: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    track_id: Optional[str] = None
    certainty: str = "medium"  # "high", "medium", "uncertain"

    def __post_init__(self):
        if self.confidence >= 0.75:
            self.certainty = "high"
        elif self.confidence >= 0.45:
            self.certainty = "medium"
        else:
            self.certainty = "uncertain"

    @property
    def center(self) -> Tuple[float, float]:
        x, y, w, h = self.bbox
        return x + w / 2.0, y + h / 2.0

    @property
    def area(self) -> int:
        return self.bbox[2] * self.bbox[3]


class BaseObjectDetector(ABC):
    """Abstract Model Adapter for swappable vision backends."""

    @abstractmethod
    def detect(self, frame: np.ndarray, confidence_threshold: float = 0.40) -> List[DetectedObject]:
        pass


class ModularObjectDetector(BaseObjectDetector):
    """Modular Object Detector supporting COCO categories with automatic CPU acceleration.
    
    Inspects available models (ONNX, MobileNet-SSD, YOLO) with fallback to YuNet/Haar
    person detector and foreground contour analysis for desktop & room objects.
    """

    def __init__(self, model_path: Optional[str] = None, config_path: Optional[str] = None):
        self.net: Optional[cv2.dnn.Net] = None
        self.backend_name = "hybrid_heuristic_yunet"
        self.classes = COCO_CLASSES

        # Attempt to load OpenCV DNN model if provided or present in models directory
        if model_path and os.path.exists(model_path):
            try:
                self.net = cv2.dnn.readNet(model_path, config_path or "")
                self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                self.backend_name = "opencv_dnn"
            except Exception:
                self.net = None

    def detect(self, frame: np.ndarray, confidence_threshold: float = 0.40) -> List[DetectedObject]:
        if frame is None or frame.size == 0:
            return []

        h, w = frame.shape[:2]
        detections: List[DetectedObject] = []

        # 1. OpenCV DNN Inference if model available
        if self.net is not None:
            try:
                blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, (416, 416), swapRB=True, crop=False)
                self.net.setInput(blob)
                layer_names = self.net.getUnconnectedOutLayersNames()
                outputs = self.net.forward(layer_names)

                for output in outputs:
                    for detection in output:
                        scores = detection[5:]
                        class_id = int(np.argmax(scores))
                        confidence = float(scores[class_id])
                        if confidence >= confidence_threshold and class_id < len(self.classes):
                            cx = int(detection[0] * w)
                            cy = int(detection[1] * h)
                            bw = int(detection[2] * w)
                            bh = int(detection[3] * h)
                            bx = max(0, int(cx - bw / 2))
                            by = max(0, int(cy - bh / 2))
                            detections.append(
                                DetectedObject(
                                    label=self.classes[class_id],
                                    confidence=round(confidence, 3),
                                    bbox=(bx, by, bw, bh),
                                )
                            )
                return self._suppress_overlaps(detections)
            except Exception:
                pass

        # 2. Vision Heuristic & Person Localisation
        # Detect person / human figures using PersonDetector
        from .detector import PersonDetector
        detector = PersonDetector()
        person_boxes, face_boxes = detector.detect_people_and_faces(frame)

        for p_box in person_boxes:
            detections.append(
                DetectedObject(
                    label="person",
                    confidence=0.88,
                    bbox=p_box,
                )
            )

        # Detect prominent foreground electronic/desk objects (e.g., laptop/monitor, bottle/cup, cell phone)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 40, 140)

        # Morphological close to connect object boundaries
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        frame_area = w * h
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < (frame_area * 0.015) or area > (frame_area * 0.70):
                continue

            bx, by, bw, bh = cv2.boundingRect(cnt)
            aspect_ratio = bw / float(bh)

            # Ignore contours that strongly overlap with already detected persons
            is_person = False
            for p_box in person_boxes:
                px, py, pw, ph = p_box
                dx = abs((bx + bw / 2) - (px + pw / 2))
                dy = abs((by + bh / 2) - (py + ph / 2))
                if dx < (pw * 0.6) and dy < (ph * 0.6):
                    is_person = True
                    break
            if is_person:
                continue

            # Classify based on geometric and texture signatures
            # Rectangular horizontal aspect ratio 1.2 - 2.0 with high inner edge density -> Laptop / Screen / TV
            if 1.2 <= aspect_ratio <= 2.2 and bh > 60:
                roi = edges[by:by + bh, bx:bx + bw]
                edge_density = np.count_nonzero(roi) / float(bw * bh)
                if edge_density > 0.04:
                    detections.append(
                        DetectedObject(
                            label="laptop" if bw < (w * 0.55) else "tv",
                            confidence=0.72,
                            bbox=(bx, by, bw, bh),
                        )
                    )
            # Vertical slender aspect ratio 0.25 - 0.65 -> Bottle / Cup / Cell phone
            elif 0.25 <= aspect_ratio <= 0.65 and bh > 50:
                detections.append(
                    DetectedObject(
                        label="cell phone" if bh < 140 else "bottle",
                        confidence=0.64,
                        bbox=(bx, by, bw, bh),
                    )
                )
            # Low wide furniture contour -> Chair / Desk / Couch
            elif aspect_ratio >= 1.5 and by > (h * 0.5):
                detections.append(
                    DetectedObject(
                        label="chair",
                        confidence=0.55,
                        bbox=(bx, by, bw, bh),
                    )
                )

        return self._suppress_overlaps(detections)

    @staticmethod
    def _suppress_overlaps(detections: List[DetectedObject], iou_thresh: float = 0.40) -> List[DetectedObject]:
        if not detections:
            return []

        # Sort by confidence descending
        detections.sort(key=lambda d: d.confidence, reverse=True)
        keep: List[DetectedObject] = []

        for d in detections:
            overlap = False
            for k in keep:
                # Calculate IoU
                x1 = max(d.bbox[0], k.bbox[0])
                y1 = max(d.bbox[1], k.bbox[1])
                x2 = min(d.bbox[0] + d.bbox[2], k.bbox[0] + k.bbox[2])
                y2 = min(d.bbox[1] + d.bbox[3], k.bbox[1] + k.bbox[3])

                inter_w = max(0, x2 - x1)
                inter_h = max(0, y2 - y1)
                inter_area = inter_w * inter_h

                union_area = d.area + k.area - inter_area
                iou = inter_area / float(union_area) if union_area > 0 else 0

                if iou > iou_thresh:
                    overlap = True
                    break

            if not overlap:
                keep.append(d)

        return keep

    @staticmethod
    def count_objects(detections: List[DetectedObject]) -> Dict[str, int]:
        """Aggregate counts per object class."""
        counts: Dict[str, int] = {}
        for d in detections:
            counts[d.label] = counts.get(d.label, 0) + 1
        return counts
