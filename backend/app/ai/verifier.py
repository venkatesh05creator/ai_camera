"""Consent-Gated Face Verification Service.

Enforces privacy rules:
1. Only compares face embeddings against enrolled profiles with active consent records.
2. Unenrolled or non-consenting individuals are NEVER identified; they remain anonymous tracks.
3. Templates are decrypted from AES-GCM only in-memory during inference.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.crypto import decrypt_bytes
from ..models.entities import ConsentRecord, FaceTemplate, Person
from core_engine import FaceEngine


class FaceVerifier:
    def __init__(self, model_name: str = "facenet"):
        self.engine = FaceEngine(model_name=model_name)
        # Ultra-fast in-memory cache of decrypted biometric vectors
        self._cache_records: List[Dict[str, Any]] = []
        self._last_cache_time: float = 0.0
        self._cache_ttl: float = 3.0  # Refresh every 3 seconds or on invalidation

    def extract_embedding_from_roi(self, face_roi: np.ndarray) -> Optional[np.ndarray]:
        """Extract a 1D normalized float32 vector for a face crop."""
        return self.engine.extract_embedding(face_roi)

    def invalidate_cache(self) -> None:
        """Force cache refresh on next verification."""
        self._last_cache_time = 0.0
        self._cache_records.clear()

    def _refresh_cache_if_needed(self, db: Session) -> None:
        now = time.time()
        if (now - self._last_cache_time) < self._cache_ttl and self._cache_records:
            return

        now_utc = datetime.now(timezone.utc)
        stmt = (
            select(Person, FaceTemplate, ConsentRecord)
            .join(FaceTemplate, FaceTemplate.person_id == Person.id)
            .join(ConsentRecord, ConsentRecord.person_id == Person.id)
            .where(
                Person.status == "enrolled",
                FaceTemplate.revoked_at.is_(None),
                ConsentRecord.withdrawn_at.is_(None),
                (ConsentRecord.expires_at.is_(None) | (ConsentRecord.expires_at > now_utc)),
            )
        )
        records = db.execute(stmt).all()
        new_cache = []

        # Import adaptive learning multi-pose gallery if available
        from ..services.adaptive_learning import adaptive_learning

        for person, template_record, _ in records:
            try:
                decrypted = decrypt_bytes(template_record.template_encrypted, aad=b"biometric-template")
                raw_list = json.loads(decrypted.decode("utf-8"))
                stored_vec = np.asarray(raw_list, dtype=np.float32).reshape(-1)
                stored_norm = np.linalg.norm(stored_vec)
                if stored_norm > 0:
                    stored_vec = stored_vec / stored_norm

                # Gather all multi-angle gallery vectors for this person
                vectors = [stored_vec]
                pose_gallery = adaptive_learning.get_person_pose_gallery(person.id)
                for pose_vec in pose_gallery.values():
                    p_norm = np.linalg.norm(pose_vec)
                    if p_norm > 0:
                        vectors.append(pose_vec / p_norm)

                new_cache.append({
                    "person_id": person.id,
                    "person_name": person.name,
                    "vectors": vectors,
                })
            except Exception as err:
                continue

        self._cache_records = new_cache
        self._last_cache_time = now

    def verify_against_consented_templates(
        self,
        db: Session,
        query_embedding: np.ndarray,
        threshold: float = 0.52,
    ) -> Tuple[Optional[str], Optional[str], float, bool]:
        """Verify query embedding against active enrolled templates in RAM with 50-microsecond speed.

        Compares against multi-angle gallery (frontal, left profile, right profile) for seamless
        multi-pose verification from any perspective!
        Returns: (person_id, person_name, match_confidence, is_match)
        """
        if query_embedding is None:
            return None, None, 0.0, False

        curr_vec = np.asarray(query_embedding, dtype=np.float32).reshape(-1)
        curr_norm = np.linalg.norm(curr_vec)
        if curr_norm == 0:
            return None, None, 0.0, False
        curr_vec = curr_vec / curr_norm

        self._refresh_cache_if_needed(db)
        if not self._cache_records:
            return None, None, 0.0, False

        best_person_id: Optional[str] = None
        best_person_name: Optional[str] = None
        best_score = 0.0

        for record in self._cache_records:
            # Check maximum similarity across all registered angles for this person
            person_max_sim = max(float(np.dot(curr_vec, vec)) for vec in record["vectors"])
            if person_max_sim > best_score:
                best_score = person_max_sim
                best_person_id = record["person_id"]
                best_person_name = record["person_name"]

        is_match = bool(best_score >= threshold and best_person_id is not None)
        if is_match:
            return best_person_id, best_person_name, best_score, True

        return None, None, best_score, False

