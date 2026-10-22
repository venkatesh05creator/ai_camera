"""Unified Core Face Recognition & Datastore Engine.

Combines detection, TFLite inference, datastore management,
and multi-model support (FaceNet / MobileFaceNet) in a single clean architecture.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np

from config import MODEL_CONFIGS
from models.model_manager import ModelManager
from utils.face_utils import load_face_cascade


@dataclass
class FaceMatchResult:
    """Detection & recognition result for a single face."""
    name: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    is_known: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "confidence": round(self.confidence, 4),
            "position": {
                "x": self.bbox[0],
                "y": self.bbox[1],
                "width": self.bbox[2],
                "height": self.bbox[3],
            },
            "is_known": self.is_known,
        }


class FaceEngine:
    """Unified engine for Face Detection, Feature Extraction, and Matching."""

    def __init__(self, model_name: str = "facenet"):
        self.model_name = model_name
        self._cascade: Optional[cv2.CascadeClassifier] = None
        self._model_managers: Dict[str, ModelManager] = {}
        self.set_model(model_name)

    # -------------------------------------------------------------------------
    # Model & Component Management
    # -------------------------------------------------------------------------
    @property
    def cascade(self) -> cv2.CascadeClassifier:
        if self._cascade is None:
            self._cascade = load_face_cascade()
        return self._cascade

    @property
    def config(self) -> Dict[str, Any]:
        if self.model_name not in MODEL_CONFIGS:
            raise ValueError(f"Unknown model: '{self.model_name}'. Available: {list(MODEL_CONFIGS.keys())}")
        return MODEL_CONFIGS[self.model_name]

    @property
    def manager(self) -> ModelManager:
        if self.model_name not in self._model_managers:
            self._model_managers[self.model_name] = ModelManager(self.config)
        return self._model_managers[self.model_name]

    def set_model(self, model_name: str) -> None:
        """Switch active model (e.g., 'facenet' or 'mobile_facenet')."""
        if model_name not in MODEL_CONFIGS:
            raise ValueError(f"Unknown model: {model_name}. Valid: {list(MODEL_CONFIGS.keys())}")
        self.model_name = model_name
        # Pre-warm manager
        _ = self.manager

    # -------------------------------------------------------------------------
    # Detection & Extraction
    # -------------------------------------------------------------------------
    def detect_faces(
        self,
        frame: np.ndarray,
        scale_factor: float = 1.1,
        min_neighbors: int = 5,
        min_size: Tuple[int, int] = (30, 30),
    ) -> List[Tuple[int, int, int, int]]:
        """Detect faces in BGR image, returning list of (x, y, w, h)."""
        if frame is None or frame.size == 0:
            return []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.cascade.detectMultiScale(
            gray,
            scaleFactor=scale_factor,
            minNeighbors=min_neighbors,
            minSize=min_size,
        )
        return [tuple(map(int, f)) for f in faces]

    def preprocess_face(self, face_roi: np.ndarray) -> Optional[np.ndarray]:
        """Preprocess face crop to model input dimensions and normalization."""
        if face_roi is None or face_roi.size == 0:
            return None
        cfg = self.config
        input_size = cfg["input_size"]
        image_mean = cfg["image_mean"]
        image_std = cfg["image_std"]

        resized = cv2.resize(face_roi, (input_size, input_size))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        normalized = (rgb.astype(np.float32) - image_mean) / image_std
        input_data = np.expand_dims(normalized, axis=0)

        input_dtype = self.manager.input_details[0]["dtype"]
        if input_data.dtype != input_dtype:
            input_data = input_data.astype(input_dtype)
        return input_data

    def extract_embedding(self, face_roi: np.ndarray) -> Optional[np.ndarray]:
        """Extract a 1D normalized float32 embedding vector for a face ROI."""
        input_data = self.preprocess_face(face_roi)
        if input_data is None:
            return None

        interpreter = self.manager.interpreter
        input_idx = self.manager.input_details[0]["index"]
        output_idx = self.manager.output_details[0]["index"]

        interpreter.set_tensor(input_idx, input_data)
        interpreter.invoke()

        raw_output = interpreter.get_tensor(output_idx)
        vec = np.asarray(raw_output, dtype=np.float32).reshape(-1)

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    # -------------------------------------------------------------------------
    # Matching
    # -------------------------------------------------------------------------
    def match_embedding(
        self,
        embedding: np.ndarray,
        threshold: Optional[float] = None,
        datastore: Optional[Dict[str, np.ndarray]] = None,
    ) -> Tuple[str, float, bool]:
        """Match 1D embedding against datastore. Returns (name, confidence, is_known)."""
        if threshold is None:
            threshold = float(self.config.get("recognition_threshold", 0.5))

        if datastore is None:
            datastore = self.load_datastore()

        if not datastore:
            return "Unknown", 0.0, False

        curr_vec = np.asarray(embedding, dtype=np.float32).reshape(-1)
        expected_dim = int(self.config["output_size"])

        if curr_vec.shape[0] != expected_dim:
            return "Unknown", 0.0, False

        curr_norm = np.linalg.norm(curr_vec)
        if curr_norm > 0:
            curr_vec = curr_vec / curr_norm

        best_name = "Unknown"
        best_score = 0.0

        for name, stored in datastore.items():
            stored_vec = np.asarray(stored, dtype=np.float32).reshape(-1)
            if stored_vec.shape[0] != expected_dim:
                continue

            stored_norm = np.linalg.norm(stored_vec)
            if stored_norm > 0:
                stored_vec = stored_vec / stored_norm

            sim = float(np.dot(curr_vec, stored_vec))
            if sim > best_score:
                best_score = sim
                best_name = name

        is_known = bool(best_score >= threshold and best_name != "Unknown")
        final_name = best_name if is_known else "Unknown"
        return final_name, best_score, is_known

    def process_frame(
        self,
        frame: np.ndarray,
        threshold: Optional[float] = None,
        datastore: Optional[Dict[str, np.ndarray]] = None,
    ) -> List[FaceMatchResult]:
        """Detect and match all faces in a frame."""
        faces = self.detect_faces(frame)
        if not faces:
            return []

        if datastore is None:
            datastore = self.load_datastore()

        results: List[FaceMatchResult] = []
        for (x, y, w, h) in faces:
            face_roi = frame[y : y + h, x : x + w]
            emb = self.extract_embedding(face_roi)
            if emb is None:
                continue

            name, conf, is_known = self.match_embedding(emb, threshold=threshold, datastore=datastore)
            results.append(
                FaceMatchResult(
                    name=name,
                    confidence=conf,
                    bbox=(x, y, w, h),
                    is_known=is_known,
                )
            )
        return results

    def draw_results(
        self,
        frame: np.ndarray,
        results: List[FaceMatchResult],
        fps: Optional[float] = None,
    ) -> np.ndarray:
        """Render high-contrast bounding boxes, labels, and stats overlay on frame."""
        canvas = frame.copy()

        for res in results:
            x, y, w, h = res.bbox
            color = (46, 204, 113) if res.is_known else (70, 70, 235)  # Green if known, Red if unknown

            # Rounded/corner rectangle styling
            cv2.rectangle(canvas, (x, y), (x + w, y + h), color, 2)

            # Label banner
            label = f"{res.name} ({res.confidence * 100:.1f}%)" if res.is_known else f"Unknown ({res.confidence * 100:.1f}%)"
            (text_w, text_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_DUPLEX, 0.55, 1)

            # Draw background capsule for text
            label_y = max(y - 8, text_h + 10)
            cv2.rectangle(
                canvas,
                (x, label_y - text_h - 6),
                (x + text_w + 12, label_y + baseline),
                color,
                cv2.FILLED,
            )
            cv2.putText(
                canvas,
                label,
                (x + 6, label_y - 2),
                cv2.FONT_HERSHEY_DUPLEX,
                0.55,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        # Header HUD
        hud_text = f"Model: {self.model_name.upper()} | Faces: {len(results)}"
        if fps is not None and fps > 0:
            hud_text += f" | {fps:.1f} FPS"
        cv2.rectangle(canvas, (10, 10), (320, 38), (20, 20, 20), cv2.FILLED)
        cv2.putText(
            canvas,
            hud_text,
            (18, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (220, 220, 220),
            1,
            cv2.LINE_AA,
        )

        return canvas

    # -------------------------------------------------------------------------
    # Datastore Management
    # -------------------------------------------------------------------------
    def get_datastore_path(self) -> Path:
        return Path(self.config["datastore_path"])

    def load_datastore(self) -> Dict[str, np.ndarray]:
        """Safely load face embeddings datastore into {name: np.ndarray}."""
        path = self.get_datastore_path()
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {}
                data = json.loads(content)
            return {k: np.asarray(v, dtype=np.float32) for k, v in data.items()}
        except Exception as exc:
            print(f"[FaceEngine] Error loading datastore from {path}: {exc}")
            return {}

    def save_datastore(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """Save datastore atomically to disk."""
        path = self.get_datastore_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Format vectors nicely
            formatted: Dict[str, Any] = {}
            for k, v in data.items():
                if isinstance(v, np.ndarray):
                    formatted[k] = v.tolist()
                else:
                    formatted[k] = v

            temp_path = path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(formatted, f, indent=2)
            temp_path.replace(path)
            return True, f"Saved {len(formatted)} identities to {path.name}"
        except Exception as exc:
            return False, f"Failed saving datastore: {exc}"

    def enroll_embedding(self, name: str, embedding: np.ndarray) -> Tuple[bool, str, str]:
        """Enroll a 1D embedding with unique identity name."""
        name = name.strip()
        if not name:
            return False, "", "Name cannot be empty"

        datastore = self.load_datastore()
        unique_name = name
        counter = 1
        while unique_name in datastore:
            unique_name = f"{name}_{counter}"
            counter += 1

        vec = np.asarray(embedding, dtype=np.float32).reshape(-1)
        expected_dim = int(self.config["output_size"])
        if vec.shape[0] != expected_dim:
            return False, "", f"Vector dimension mismatch ({vec.shape[0]} != {expected_dim})"

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm

        datastore[unique_name] = vec
        ok, msg = self.save_datastore(datastore)
        if ok:
            return True, unique_name, f"Successfully enrolled '{unique_name}' ({expected_dim}-dim)"
        return False, unique_name, msg

    def enroll_from_image(self, image_input: Union[str, np.ndarray], name: str) -> Tuple[bool, str, str]:
        """Enroll face from image path or numpy BGR image."""
        if isinstance(image_input, (str, Path)):
            frame = cv2.imread(str(image_input))
            if frame is None:
                return False, "", f"Could not read image from {image_input}"
        else:
            frame = image_input

        faces = self.detect_faces(frame)
        if not faces:
            return False, "", "No face detected in the image"

        # Use largest face
        faces.sort(key=lambda b: b[2] * b[3], reverse=True)
        x, y, w, h = faces[0]
        face_roi = frame[y : y + h, x : x + w]

        emb = self.extract_embedding(face_roi)
        if emb is None:
            return False, "", "Failed to extract embedding from detected face"

        return self.enroll_embedding(name, emb)

    def enroll_from_multiple_images(self, image_paths: List[str], name: str) -> Tuple[bool, str, str]:
        """Extract embeddings from multiple images and enroll the normalized average vector."""
        all_embeddings: List[np.ndarray] = []

        for p in image_paths:
            img = cv2.imread(str(p))
            if img is None:
                continue
            faces = self.detect_faces(img)
            if not faces:
                continue
            faces.sort(key=lambda b: b[2] * b[3], reverse=True)
            x, y, w, h = faces[0]
            emb = self.extract_embedding(img[y : y + h, x : x + w])
            if emb is not None:
                all_embeddings.append(emb)

        if not all_embeddings:
            return False, "", "No valid faces could be extracted from the provided images"

        avg_vec = np.mean(all_embeddings, axis=0)
        norm = np.linalg.norm(avg_vec)
        if norm > 0:
            avg_vec = avg_vec / norm

        return self.enroll_embedding(name, avg_vec)

    def remove_identity(self, name: str) -> Tuple[bool, str]:
        """Remove identity by name from current datastore."""
        datastore = self.load_datastore()
        if name not in datastore:
            return False, f"Identity '{name}' not found in datastore"

        del datastore[name]
        ok, msg = self.save_datastore(datastore)
        if ok:
            return True, f"Removed '{name}' from datastore"
        return False, msg

    def list_identities(self) -> List[Dict[str, Any]]:
        """List all enrolled identities and dimensions."""
        datastore = self.load_datastore()
        items = []
        for name, emb in sorted(datastore.items()):
            vec = np.asarray(emb).reshape(-1)
            items.append({
                "name": name,
                "dimension": int(vec.shape[0]),
            })
        return items

    def recognize_image_file(
        self,
        image_path: str,
        threshold: Optional[float] = None,
    ) -> Tuple[List[FaceMatchResult], Optional[np.ndarray], str]:
        """Process an image file from disk and return detection results and annotated image."""
        if not os.path.exists(image_path):
            return [], None, f"File not found: {image_path}"

        frame = cv2.imread(image_path)
        if frame is None:
            return [], None, f"Unable to decode image file: {image_path}"

        results = self.process_frame(frame, threshold=threshold)
        annotated = self.draw_results(frame, results)
        return results, annotated, "OK"
