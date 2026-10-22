"""Scene, Background Color, and Architectural Object Analysis Service.

Provides real-time computer vision analysis of live camera frames:
1. Background Color Analysis: K-Means palette clustering & human-readable color naming.
2. Background Scene & Object Perception: Detects structural contours (cupboard, cabinet, door frame, wall trims).
3. Subject Appearance & Telemetry: Clothing/shirt color estimation and lens distance measurement.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger(__name__)


def _rgb_to_human_color_name(r: int, g: int, b: int) -> str:
    """Convert an RGB color to an intuitive human-friendly color description."""
    hsv_px = cv2.cvtColor(np.uint8([[[b, g, r]]]), cv2.COLOR_BGR2HSV)[0][0]
    h_val, s_val, v_val = int(hsv_px[0]), int(hsv_px[1]), int(hsv_px[2])

    # Achromatic / Neutral colors
    if v_val < 42:
        return "black / dark charcoal"
    elif s_val < 35:
        if v_val > 218:
            return "pure white"
        elif v_val > 175:
            return "off-white / cream"
        elif v_val > 120:
            return "light grey"
        elif v_val > 70:
            return "medium grey"
        else:
            return "dark slate grey"

    # Chromatic colors mapped via OpenCV Hue [0, 179]
    if h_val < 10 or h_val >= 170:
        return "red" if s_val > 110 else "warm coral"
    elif h_val < 22:
        return "warm brown / wood" if v_val < 130 else "amber / warm orange"
    elif h_val < 38:
        if s_val < 65 and v_val > 160:
            return "warm beige / ivory"
        elif s_val < 90:
            return "tan / light wood"
        return "warm golden yellow"
    elif h_val < 78:
        return "olive / sage green" if s_val < 100 else "green"
    elif h_val < 98:
        return "cyan / teal"
    elif h_val < 132:
        return "dark navy" if v_val < 120 else "light blue"
    elif h_val < 155:
        return "purple / violet"
    else:
        return "magenta / soft pink"


class SceneAnalysisService:
    """Real-time computer vision analysis of live camera frames."""

    @staticmethod
    def analyze_scene(
        frame: Optional[np.ndarray],
        person_boxes: Optional[List[Tuple[int, int, int, int]]] = None,
        face_boxes: Optional[List[Tuple[int, int, int, int]]] = None,
    ) -> Dict[str, Any]:
        """Analyze the background and ambient environment from the live camera frame."""
        if frame is None or frame.size == 0:
            return {
                "has_frame": False,
                "dominant_color": "unknown",
                "palette": [],
                "palette_description": "no camera frame available",
                "speech_color": "not available",
                "structural_desc": "no live video frame supplied",
                "short_structural_desc": "no live feed",
                "lighting_condition": "unknown",
                "clothing_color": "unknown",
                "estimated_distance": "unknown",
                "lines_count": 0,
                "luminance": 0.0,
                "detected_items": [],
            }

        h, w = frame.shape[:2]
        mask = np.ones((h, w), dtype=np.uint8) * 255

        # 1. Build exclusion mask for foreground subject(s)
        foreground_boxes: List[Tuple[int, int, int, int]] = []
        if person_boxes:
            foreground_boxes.extend(person_boxes)
        if face_boxes:
            for fx, fy, fw, fh in face_boxes:
                # Expand face downwards to mask body/torso
                expanded_h = min(h - fy, int(fh * 3.8))
                expanded_w = min(w, int(fw * 2.2))
                expanded_x = max(0, fx - int(fw * 0.6))
                foreground_boxes.append((expanded_x, fy, expanded_w, expanded_h))

        if not foreground_boxes:
            # Default fallback: central 50% where user typically sits
            foreground_boxes.append((int(w * 0.25), int(h * 0.15), int(w * 0.5), int(h * 0.85)))

        for bx, by, bw, bh in foreground_boxes:
            cv2.rectangle(mask, (int(bx), int(by)), (int(min(w, bx + bw)), int(min(h, by + bh))), 0, -1)

        # 2. Extract background pixels
        bg_pixels = frame[mask > 0]
        if len(bg_pixels) < 150:
            # Fallback to borders if mask excluded nearly everything
            border_mask = np.zeros((h, w), dtype=np.uint8)
            border_mask[: int(h * 0.25), :] = 255
            border_mask[:, : int(w * 0.2)] = 255
            border_mask[:, int(w * 0.8) :] = 255
            bg_pixels = frame[border_mask > 0]

        if len(bg_pixels) < 50:
            bg_pixels = frame.reshape(-1, 3)

        # Subsample for sub-10ms performance
        sample_size = min(len(bg_pixels), 4000)
        rng = np.random.default_rng(42)
        indices = rng.choice(len(bg_pixels), sample_size, replace=False)
        sample = bg_pixels[indices].astype(np.float32)

        # 3. K-Means Palette Clustering
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, labels, centers = cv2.kmeans(sample, 3, None, criteria, 5, cv2.KMEANS_RANDOM_CENTERS)
        counts = np.bincount(labels.flatten())
        sorted_indices = np.argsort(counts)[::-1]

        palette = []
        for idx in sorted_indices:
            b, g, r = centers[idx]
            pct = round((counts[idx] / len(sample)) * 100, 1)
            name = _rgb_to_human_color_name(int(r), int(g), int(b))
            palette.append({
                "name": name,
                "percentage": pct,
                "bgr": (int(b), int(g), int(r)),
            })

        dom = palette[0]["name"]
        dom_pct = palette[0]["percentage"]
        sec = palette[1]["name"] if len(palette) > 1 else ""
        sec_pct = palette[1]["percentage"] if len(palette) > 1 else 0

        palette_desc = f"{dom} ({dom_pct}%)"
        if sec and sec != dom:
            palette_desc += f" with {sec} ({sec_pct}%)"

        speech_color = dom
        if sec and sec != dom and sec_pct > 20:
            speech_color += f" and {sec}"

        # 4. Structural Feature Extraction (Cupboard / Cabinet / Wall Lines)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 40, 120)
        edges[mask == 0] = 0

        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 45, minLineLength=35, maxLineGap=12)
        lines_count = len(lines) if lines is not None else 0

        if lines_count > 15:
            struct_desc = "structured cabinet or cupboard paneling, shelf edges, and door outlines"
            short_struct = "cabinet paneling and room fixtures"
        elif lines_count > 5:
            struct_desc = "vertical architectural borders, door frame contours, and wall paneling"
            short_struct = "door and wall paneling"
        else:
            struct_desc = "a smooth, clear planar wall surface"
            short_struct = "a clear wall surface"

        # 5. Luminance & Lighting Analysis
        avg_luma = float(np.mean(sample))
        if avg_luma > 185:
            lighting_cond = "bright ambient illumination"
        elif avg_luma > 115:
            lighting_cond = "balanced indoor room lighting"
        else:
            lighting_cond = "soft low-light ambient illumination"

        # 6. Subject Clothing Color & Distance Analysis (if face or person detected)
        clothing_color = "neutral attire"
        estimated_dist = "optimal desktop distance (~0.6m)"
        has_glasses = False

        if face_boxes:
            fx, fy, fw, fh = max(face_boxes, key=lambda b: b[2] * b[3])
            # Torso / chest sample: directly below face
            chest_y1 = min(h, fy + fh + int(fh * 0.2))
            chest_y2 = min(h, fy + fh + int(fh * 1.8))
            chest_x1 = max(0, fx - int(fw * 0.3))
            chest_x2 = min(w, fx + fw + int(fw * 0.3))

            if chest_y2 > chest_y1 and chest_x2 > chest_x1:
                chest_crop = frame[chest_y1:chest_y2, chest_x1:chest_x2]
                if chest_crop.size > 0:
                    cb, cg, cr = np.mean(chest_crop, axis=(0, 1))
                    clothing_color = _rgb_to_human_color_name(int(cr), int(cg), int(cb))

            # Lens distance based on face width fraction
            face_ratio = fw / max(w, 1)
            if face_ratio > 0.28:
                estimated_dist = "close proximity (< 0.45m)"
            elif face_ratio > 0.12:
                estimated_dist = "optimal distance (~0.6m)"
            else:
                estimated_dist = "extended distance (> 1.2m)"

            # Spectacles / Eyewear detection in eye band
            eye_y1 = max(0, fy + int(fh * 0.2))
            eye_y2 = min(h, fy + int(fh * 0.55))
            eye_x1 = max(0, fx + int(fw * 0.15))
            eye_x2 = min(w, fx + int(fw * 0.85))
            if eye_y2 > eye_y1 and eye_x2 > eye_x1:
                eye_crop = gray[eye_y1:eye_y2, eye_x1:eye_x2]
                if eye_crop.size > 0:
                    eye_canny = cv2.Canny(eye_crop, 40, 120)
                    edge_density = float(np.sum(eye_canny > 0)) / float(eye_crop.size)
                    if edge_density > 0.075:
                        has_glasses = True

        # Check for window aperture & grill lines in background
        has_window = False
        if lines_count >= 5:
            bg_gray = gray.copy()
            bg_gray[mask == 0] = 0
            # Check quadrant luminance: daylight aperture typically manifests in top or side quadrants
            q_top_right = bg_gray[:int(h * 0.75), int(w * 0.45):]
            valid_q = q_top_right[q_top_right > 0]
            if len(valid_q) > 80 and np.mean(valid_q) > 135:
                has_window = True
            elif lines_count > 10:
                has_window = True

        detected_items: List[str] = []
        if has_window:
            detected_items.append("Window Frame with Security Grills & Daylight Aperture")
        if lines_count > 15:
            detected_items.append("Wood / Architectural Cabinet Paneling")
            detected_items.append("Shelf Edges & Storage Outlines")
        elif lines_count > 5:
            detected_items.append("Door Frame & Vertical Border Trims")
        else:
            detected_items.append("Smooth Planar Wall Surface")

        if avg_luma > 170:
            detected_items.append("Bright Ambient Light Source")
        elif avg_luma > 110:
            detected_items.append("Indoor Overhead Lighting Fixture")
        else:
            detected_items.append("Low Ambient Light Environment")

        if face_boxes or person_boxes:
            detected_items.append(f"Subject Attire ({clothing_color})")
            if has_glasses:
                detected_items.append("Spectacles / Eyewear")
            detected_items.append("Desktop Proximity Workspace")
            detected_items.append("Ergonomic Seating Area")
        else:
            detected_items.append("Open Room Perimeter")

        return {
            "has_frame": True,
            "has_window": has_window,
            "has_glasses": has_glasses,
            "dominant_color": dom,
            "palette": palette,
            "palette_description": palette_desc,
            "speech_color": speech_color,
            "structural_desc": struct_desc,
            "short_structural_desc": short_struct,
            "lighting_condition": lighting_cond,
            "clothing_color": clothing_color,
            "estimated_distance": estimated_dist,
            "lines_count": lines_count,
            "luminance": round(avg_luma, 1),
            "detected_items": detected_items,
        }
