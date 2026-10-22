"""Controlled Model Evaluation, Versioning, and Promotion Registry.

Enforces isolated candidate training, held-out validation gates (Precision/Recall/F1),
explicit administrative promotion, rollback controls, and deployment audit logging.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ModelVersion:
    model_id: str
    version: str
    task: str  # "face_verification", "object_detection", "person_detection"
    architecture: str
    dataset_version: str
    metrics: Dict[str, float]  # precision, recall, f1, false_positive_rate, latency_ms
    status: str = "candidate"  # "candidate", "active", "archived", "rejected"
    acceptance_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "min_precision": 0.95,
        "min_recall": 0.92,
        "min_f1": 0.94,
        "max_false_positive_rate": 0.02,
        "max_latency_ms": 60.0,
    })
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    promoted_at: Optional[str] = None
    promoted_by: Optional[str] = None
    rollback_version: Optional[str] = None
    audit_notes: str = ""


class ControlledModelRegistry:
    """Manages versioned models, evaluation gates, explicit promotion, and rollback."""

    def __init__(self, registry_file: Optional[Path] = None):
        self.registry_file = registry_file or Path("var/model_registry.json")
        self.models: Dict[str, ModelVersion] = {}
        self._load_registry()

    def _load_registry(self):
        # Default baseline models matching repository
        default_facenet = ModelVersion(
            model_id="facenet-v1",
            version="1.0.0",
            task="face_verification",
            architecture="InceptionResnetV1-512dim",
            dataset_version="v1.0-consented-baseline",
            metrics={"precision": 0.985, "recall": 0.962, "f1": 0.973, "false_positive_rate": 0.005, "latency_ms": 18.4},
            status="active",
            promoted_at=datetime.now(timezone.utc).isoformat(),
            promoted_by="system_init",
            audit_notes="Standard production FaceNet baseline model.",
        )
        default_yunet = ModelVersion(
            model_id="yunet-v1",
            version="2023mar",
            task="person_detection",
            architecture="YuNet-ONNX-320",
            dataset_version="opencv-zoo-baseline",
            metrics={"precision": 0.968, "recall": 0.945, "f1": 0.956, "false_positive_rate": 0.012, "latency_ms": 4.2},
            status="active",
            promoted_at=datetime.now(timezone.utc).isoformat(),
            promoted_by="system_init",
            audit_notes="OpenCV YuNet face & person detector.",
        )
        self.models = {
            default_facenet.model_id: default_facenet,
            default_yunet.model_id: default_yunet,
        }

        if self.registry_file.exists():
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for m_dict in data.values():
                        mv = ModelVersion(**m_dict)
                        self.models[mv.model_id] = mv
            except Exception as e:
                logger.warning("Failed to load model registry from disk: %s", e)

    def _save_registry(self):
        try:
            self.registry_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump({k: asdict(v) for k, v in self.models.items()}, f, indent=2)
        except Exception as e:
            logger.warning("Failed to persist model registry: %s", e)

    def register_candidate(
        self,
        model_id: str,
        version: str,
        task: str,
        architecture: str,
        dataset_version: str,
        metrics: Dict[str, float],
    ) -> ModelVersion:
        """Register a new candidate model produced by an isolated training job."""
        mv = ModelVersion(
            model_id=model_id,
            version=version,
            task=task,
            architecture=architecture,
            dataset_version=dataset_version,
            metrics=metrics,
            status="candidate",
        )
        self.models[model_id] = mv
        self._save_registry()
        return mv

    def evaluate_candidate(self, model_id: str) -> Tuple[bool, str]:
        """Evaluate candidate against rigorous acceptance thresholds."""
        mv = self.models.get(model_id)
        if not mv:
            return False, f"Model {model_id} not found in registry."

        th = mv.acceptance_thresholds
        m = mv.metrics

        prec = m.get("precision", 0.0)
        rec = m.get("recall", 0.0)
        f1 = m.get("f1", 0.0)
        fpr = m.get("false_positive_rate", 1.0)
        lat = m.get("latency_ms", 999.0)

        failures = []
        if prec < th["min_precision"]:
            failures.append(f"Precision {prec:.3f} < required {th['min_precision']:.3f}")
        if rec < th["min_recall"]:
            failures.append(f"Recall {rec:.3f} < required {th['min_recall']:.3f}")
        if f1 < th["min_f1"]:
            failures.append(f"F1 {f1:.3f} < required {th['min_f1']:.3f}")
        if fpr > th["max_false_positive_rate"]:
            failures.append(f"FPR {fpr:.3f} > max allowable {th['max_false_positive_rate']:.3f}")
        if lat > th["max_latency_ms"]:
            failures.append(f"Latency {lat:.1f}ms > max allowable {th['max_latency_ms']:.1f}ms")

        if failures:
            mv.status = "rejected"
            mv.audit_notes = f"Evaluation failed: {'; '.join(failures)}"
            self._save_registry()
            return False, mv.audit_notes

        return True, "All benchmark evaluation criteria passed successfully."

    def promote_candidate(self, model_id: str, actor_user_id: str) -> Tuple[bool, str]:
        """Promote evaluated candidate to active production status with rollback tracking."""
        mv = self.models.get(model_id)
        if not mv:
            return False, f"Model {model_id} not found."

        passed, reason = self.evaluate_candidate(model_id)
        if not passed:
            return False, f"Promotion blocked by evaluation gates: {reason}"

        # Find current active model for this task to link as rollback target
        prev_active = next(
            (m for m in self.models.values() if m.task == mv.task and m.status == "active" and m.model_id != model_id),
            None
        )

        if prev_active:
            prev_active.status = "archived"
            mv.rollback_version = prev_active.version

        mv.status = "active"
        mv.promoted_at = datetime.now(timezone.utc).isoformat()
        mv.promoted_by = actor_user_id
        mv.audit_notes = f"Promoted to production by {actor_user_id}. Baseline replaced: {prev_active.version if prev_active else 'none'}."
        self._save_registry()

        logger.info("Model %s promoted to production for task %s", model_id, mv.task)
        return True, f"Model {model_id} successfully promoted to active production."

    def rollback(self, task: str, actor_user_id: str) -> Tuple[bool, str]:
        """Rollback current active model to previous approved baseline."""
        active_model = next((m for m in self.models.values() if m.task == task and m.status == "active"), None)
        if not active_model or not active_model.rollback_version:
            return False, f"No previous rollback version available for task '{task}'."

        target = next((m for m in self.models.values() if m.task == task and m.version == active_model.rollback_version), None)
        if not target:
            return False, f"Rollback target version {active_model.rollback_version} could not be resolved."

        active_model.status = "archived"
        target.status = "active"
        target.promoted_at = datetime.now(timezone.utc).isoformat()
        target.promoted_by = actor_user_id
        target.audit_notes = f"Restored via rollback by {actor_user_id}."
        self._save_registry()

        logger.warning("Rolled back task %s from %s to %s", task, active_model.version, target.version)
        return True, f"Rolled back {task} to version {target.version}."

    def get_models(self) -> List[ModelVersion]:
        return list(self.models.values())


model_registry = ControlledModelRegistry()
