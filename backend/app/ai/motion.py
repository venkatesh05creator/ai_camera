"""Motion detection using background subtraction and frame differencing."""

from __future__ import annotations

from typing import List, Tuple
import cv2
import numpy as np


class MotionDetector:
    def __init__(self, history: int = 500, var_threshold: int = 25, min_area: int = 600):
        self.subtractor = cv2.createBackgroundSubtractorMOG2(
            history=history,
            varThreshold=var_threshold,
            detectShadows=False,
        )
        self.min_area = min_area
        self.prev_gray: np.ndarray | None = None

    def process(self, frame: np.ndarray) -> Tuple[bool, float, List[Tuple[int, int, int, int]]]:
        """Detect motion in frame. Returns (has_motion, motion_ratio, list of bounding boxes)."""
        if frame is None or frame.size == 0:
            return False, 0.0, []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        fg_mask = self.subtractor.apply(gray)
        # Morphological opening to remove noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
        fg_mask = cv2.dilate(fg_mask, kernel, iterations=2)

        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        motion_boxes = []
        total_motion_area = 0

        for c in contours:
            area = cv2.contourArea(c)
            if area > self.min_area:
                x, y, w, h = cv2.boundingRect(c)
                motion_boxes.append((int(x), int(y), int(w), int(h)))
                total_motion_area += area

        frame_area = frame.shape[0] * frame.shape[1]
        motion_ratio = total_motion_area / max(frame_area, 1)
        has_motion = len(motion_boxes) > 0 and motion_ratio > 0.01

        return has_motion, float(motion_ratio), motion_boxes
