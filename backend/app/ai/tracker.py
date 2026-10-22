"""Anonymous Multi-Object Tracker (Centroid & IOU tracking).

Assigns temporary, non-identifying tracker IDs (e.g. 'TRK-001') that persist
only during an active observation session. Tracker IDs are never stored as profiles.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class TrackedObject:
    track_id: str
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    centroid: Tuple[int, int]
    disappeared_count: int = 0
    first_seen_timestamp: float = 0.0
    last_seen_timestamp: float = 0.0
    verified_person_id: Optional[str] = None
    verified_name: Optional[str] = None
    match_confidence: float = 0.0
    last_verified_timestamp: float = 0.0


class AnonymousTracker:
    def __init__(self, max_disappeared: int = 45, max_distance: float = 140.0):
        self.next_track_num = 1
        self.objects: Dict[str, TrackedObject] = {}
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance

    def _generate_track_id(self) -> str:
        tid = f"TRK-{self.next_track_num:03d}"
        self.next_track_num += 1
        return tid

    @staticmethod
    def _calc_centroid(bbox: Tuple[int, int, int, int]) -> Tuple[int, int]:
        x, y, w, h = bbox
        return (int(x + w / 2), int(y + h / 2))

    @staticmethod
    def _smooth_bbox(
        prev_box: Tuple[int, int, int, int],
        new_box: Tuple[int, int, int, int],
        alpha: float = 0.75,
    ) -> Tuple[int, int, int, int]:
        """Smooth box transitions using exponential moving average to eliminate jitter."""
        px, py, pw, ph = prev_box
        nx, ny, nw, nh = new_box
        sx = int(alpha * nx + (1 - alpha) * px)
        sy = int(alpha * ny + (1 - alpha) * py)
        sw = int(alpha * nw + (1 - alpha) * pw)
        sh = int(alpha * nh + (1 - alpha) * ph)
        return (sx, sy, sw, sh)

    def update(self, detected_boxes: List[Tuple[int, int, int, int]], timestamp: float) -> List[TrackedObject]:
        """Update tracker state with new bounding boxes detected in the current frame."""
        if not detected_boxes:
            # Mark existing tracks as disappeared
            for tid in list(self.objects.keys()):
                self.objects[tid].disappeared_count += 1
                if self.objects[tid].disappeared_count > self.max_disappeared:
                    del self.objects[tid]
            return list(self.objects.values())

        input_centroids = [self._calc_centroid(box) for box in detected_boxes]

        # If no tracks exist yet, register all
        if not self.objects:
            for box, centroid in zip(detected_boxes, input_centroids):
                tid = self._generate_track_id()
                self.objects[tid] = TrackedObject(
                    track_id=tid,
                    bbox=box,
                    centroid=centroid,
                    first_seen_timestamp=timestamp,
                    last_seen_timestamp=timestamp,
                )
            return list(self.objects.values())

        # Match existing centroids to new centroids using Euclidean distance
        track_ids = list(self.objects.keys())
        existing_centroids = [self.objects[tid].centroid for tid in track_ids]

        # Compute distance matrix
        distances: List[Tuple[float, int, int]] = []
        for row_idx, e_c in enumerate(existing_centroids):
            for col_idx, i_c in enumerate(input_centroids):
                dist = math.hypot(e_c[0] - i_c[0], e_c[1] - i_c[1])
                distances.append((dist, row_idx, col_idx))

        distances.sort(key=lambda x: x[0])

        used_rows = set()
        used_cols = set()

        for dist, row, col in distances:
            if row in used_rows or col in used_cols:
                continue
            if dist > self.max_distance:
                continue

            tid = track_ids[row]
            obj = self.objects[tid]
            # Smooth bounding box to prevent visual jitter
            obj.bbox = self._smooth_bbox(obj.bbox, detected_boxes[col])
            obj.centroid = self._calc_centroid(obj.bbox)
            obj.disappeared_count = 0
            obj.last_seen_timestamp = timestamp

            used_rows.add(row)
            used_cols.add(col)

        # Handle disappeared tracks
        unused_rows = set(range(len(track_ids))) - used_rows
        for row in unused_rows:
            tid = track_ids[row]
            self.objects[tid].disappeared_count += 1
            if self.objects[tid].disappeared_count > self.max_disappeared:
                del self.objects[tid]

        # Handle newly appeared tracks
        unused_cols = set(range(len(detected_boxes))) - used_cols
        for col in unused_cols:
            tid = self._generate_track_id()
            self.objects[tid] = TrackedObject(
                track_id=tid,
                bbox=detected_boxes[col],
                centroid=input_centroids[col],
                first_seen_timestamp=timestamp,
                last_seen_timestamp=timestamp,
            )

        # Deduplicate active tracks: if two tracks overlap heavily or one is contained in another,
        # retain the verified track, or the one with earlier first_seen_timestamp
        active_ids = list(self.objects.keys())
        to_remove = set()
        for i in range(len(active_ids)):
            id_a = active_ids[i]
            if id_a in to_remove:
                continue
            xa1, ya1, wa, ha = self.objects[id_a].bbox
            xa2, ya2 = xa1 + wa, ya1 + ha
            area_a = max(1, wa * ha)

            for j in range(i + 1, len(active_ids)):
                id_b = active_ids[j]
                if id_b in to_remove:
                    continue
                xb1, yb1, wb, hb = self.objects[id_b].bbox
                xb2, yb2 = xb1 + wb, yb1 + hb
                area_b = max(1, wb * hb)

                ix1 = max(xa1, xb1)
                iy1 = max(ya1, yb1)
                ix2 = min(xa2, xb2)
                iy2 = min(ya2, yb2)

                inter_w = max(0, ix2 - ix1)
                inter_h = max(0, iy2 - iy1)
                inter = inter_w * inter_h

                min_area = min(area_a, area_b)
                containment = inter / min_area
                iou = inter / max(1, area_a + area_b - inter)

                if containment > 0.38 or iou > 0.30:
                    obj_a = self.objects[id_a]
                    obj_b = self.objects[id_b]
                    if obj_a.verified_name and not obj_b.verified_name:
                        to_remove.add(id_b)
                    elif obj_b.verified_name and not obj_a.verified_name:
                        to_remove.add(id_a)
                        break
                    elif obj_a.first_seen_timestamp <= obj_b.first_seen_timestamp:
                        to_remove.add(id_b)
                    else:
                        to_remove.add(id_a)
                        break

        for tid in to_remove:
            if tid in self.objects:
                del self.objects[tid]

        return list(self.objects.values())
