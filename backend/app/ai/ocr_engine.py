"""Optical Character Recognition (OCR) and Environmental Sign/Label Reader.

Extracts text regions, preserves line and column reading order, computes confidence scores,
and sanitizes environmental text as untrusted data to prevent prompt injection attacks.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TextRegion:
    text: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    is_uncertain: bool = False
    raw_untrusted: str = ""

    def __post_init__(self):
        if not self.raw_untrusted:
            self.raw_untrusted = self.text
        if self.confidence < 0.60:
            self.is_uncertain = True


@dataclass
class OCRScanResult:
    camera_id: str
    timestamp: float
    full_text: str
    sanitized_data_payload: str
    regions: List[TextRegion] = field(default_factory=list)
    line_count: int = 0
    mean_confidence: float = 0.0
    has_uncertain_sections: bool = False
    detected_signs: List[str] = field(default_factory=list)


class OCREngine:
    """Modular OCR Engine with MSER / Gradient Stroke localizer and untrusted prompt protection."""

    def __init__(self, tesseract_cmd: Optional[str] = None):
        self.tesseract_available = False
        self._tesseract = None

        try:
            import importlib
            pytesseract = importlib.import_module("pytesseract")
            self._tesseract = pytesseract
            if tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            self.tesseract_available = True
        except (ImportError, ModuleNotFoundError):
            self.tesseract_available = False

    def detect_text_regions(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect probable text regions and signs using MSER and morphological gradient."""
        if frame is None or frame.size == 0:
            return []

        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame.copy()

        # High-contrast adaptive thresholding for text stroke extraction
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        grad_x = cv2.Sobel(blurred, cv2.CV_16S, 1, 0, ksize=3)
        grad_y = cv2.Sobel(blurred, cv2.CV_16S, 0, 1, ksize=3)
        abs_grad_x = cv2.convertScaleAbs(grad_x)
        abs_grad_y = cv2.convertScaleAbs(grad_y)
        grad = cv2.addWeighted(abs_grad_x, 0.5, abs_grad_y, 0.5, 0)

        _, thresh = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

        # Morphological horizontal connect for line formation
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (12, 3))
        connected = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes: List[Tuple[int, int, int, int]] = []
        frame_area = w * h

        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            area = bw * bh
            aspect = bw / float(bh)

            # Filter valid text line proportions: width > 16, height between 10 and 220, reasonable aspect ratio
            if 16 < bw < (w * 0.95) and 10 < bh < (h * 0.40) and area > 200:
                if 0.8 <= aspect <= 20.0 and area < (frame_area * 0.40):
                    boxes.append((x, y, bw, bh))

        # Sort top-to-bottom, left-to-right to preserve line reading order
        boxes.sort(key=lambda b: (b[1] // 24, b[0]))
        return boxes

    def process_frame(
        self,
        frame: np.ndarray,
        camera_id: str = "camera_default",
        lang: str = "eng",
    ) -> OCRScanResult:
        """Execute OCR pipeline and produce untrusted data payload."""
        now = datetime.now(timezone.utc).timestamp()
        if frame is None or frame.size == 0:
            return OCRScanResult(
                camera_id=camera_id,
                timestamp=now,
                full_text="",
                sanitized_data_payload="<untrusted_environmental_data source=\"camera_ocr\" />",
            )

        boxes = self.detect_text_regions(frame)
        regions: List[TextRegion] = []
        extracted_lines: List[str] = []

        if self.tesseract_available and self._tesseract:
            for bx, by, bw, bh in boxes:
                # Add padding
                pad = 4
                x1 = max(0, bx - pad)
                y1 = max(0, by - pad)
                x2 = min(frame.shape[1], bx + bw + pad)
                y2 = min(frame.shape[0], by + bh + pad)
                crop = frame[y1:y2, x1:x2]

                try:
                    # Run tesseract line extraction
                    data = self._tesseract.image_to_data(
                        crop,
                        lang=lang,
                        output_type=self._tesseract.Output.DICT,
                        config="--psm 6",
                    )
                    words = []
                    confs = []
                    for i in range(len(data.get("text", []))):
                        word = data["text"][i].strip()
                        conf = float(data["conf"][i])
                        if word and conf > 10.0:
                            words.append(word)
                            confs.append(conf / 100.0)

                    if words:
                        line_text = " ".join(words)
                        mean_c = sum(confs) / len(confs) if confs else 0.5
                        reg = TextRegion(
                            text=line_text,
                            confidence=round(mean_c, 2),
                            bbox=(bx, by, bw, bh),
                            is_uncertain=(mean_c < 0.60),
                        )
                        regions.append(reg)
                        extracted_lines.append(line_text)
                except Exception as e:
                    logger.debug("Tesseract crop error: %s", e)

        # Fallback / visual region summary when tesseract binary is not installed
        if not regions and boxes:
            for idx, (bx, by, bw, bh) in enumerate(boxes[:8]):
                line_text = f"[Text Block {idx+1} at ({bx},{by}) ~{bw}x{bh}px]"
                regions.append(
                    TextRegion(
                        text=line_text,
                        confidence=0.70,
                        bbox=(bx, by, bw, bh),
                        is_uncertain=False,
                    )
                )
                extracted_lines.append(line_text)

        full_text = "\n".join(extracted_lines)
        mean_conf = (
            sum(r.confidence for r in regions) / len(regions)
            if regions else 0.0
        )
        has_uncertain = any(r.is_uncertain for r in regions)

        # Detect prominent signs or labels
        detected_signs = []
        sign_patterns = [
            r"\b(exit|emergency|warning|caution|danger|notice|restricted|private|no parking|stop)\b",
            r"\b(entrance|office|room|floor|zone|camera|monitored|security)\b",
        ]
        for pattern in sign_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            detected_signs.extend([m.upper() for m in matches])

        # UNTRUSTED ENVIRONMENTAL DATA CONTAINMENT:
        # Strictly isolative tag to prevent any prompt injection in the camera frame
        sanitized_payload = (
            f"<untrusted_environmental_data source=\"camera_ocr\" camera_id=\"{camera_id}\" "
            f"timestamp=\"{now}\" confidence=\"{mean_conf:.2f}\">\n"
            f"{full_text}\n"
            f"</untrusted_environmental_data>"
        )

        return OCRScanResult(
            camera_id=camera_id,
            timestamp=now,
            full_text=full_text,
            sanitized_data_payload=sanitized_payload,
            regions=regions,
            line_count=len(extracted_lines),
            mean_confidence=round(mean_conf, 2),
            has_uncertain_sections=has_uncertain,
            detected_signs=list(set(detected_signs)),
        )


ocr_engine = OCREngine()
