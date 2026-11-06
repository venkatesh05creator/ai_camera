"""Grounding eval runner: 30/30 cases must pass (M2 gate)."""

from __future__ import annotations

from backend.app.services import evidence
from tests.grounding_cases import CASES


def test_case_count_is_thirty():
    assert len(CASES) == 30, (
        f"eval corpus must stay at 30 cases, found {len(CASES)}")


def test_grounding_eval_all_cases():
    failures = []
    for idx, (texts, reply, exp_valid, exp_invalid) in enumerate(CASES, 1):
        pack = evidence.EvidencePack([
            evidence.EvidenceItem(f"E{i + 1}", "eval", "case", t)
            for i, t in enumerate(texts)
        ])
        verdict = evidence.verify_reply(reply, pack)
        problems = []
        if verdict["valid_badges"] != exp_valid:
            problems.append(
                f"valid_badges={verdict['valid_badges']} expected {exp_valid}")
        if verdict["invalid_badges"] != exp_invalid:
            problems.append(
                f"invalid_badges={verdict['invalid_badges']} expected {exp_invalid}")
        # sentences with only hallucinated badges (no valid badge) are
        # honestly unsourced: cases 13, 14, 15 and bare-fact claims 19-23
        if idx in (13, 14, 15, 19, 20, 21, 22, 23):
            if not verdict["unsupported_sentences"]:
                problems.append("expected unsupported sentence(s), found none")
        elif verdict["unsupported_sentences"]:
            problems.append(
                f"false positive flags: {verdict['unsupported_sentences']}")
        # hallucinated badges must never survive into cleaned text
        for bad in exp_invalid:
            if f"[{bad}]" in verdict["cleaned_text"]:
                problems.append(f"cleaned text still contains [{bad}]")
        if problems:
            failures.append(f"case {idx}: " + "; ".join(problems))
    assert not failures, (
        f"{len(CASES) - len(failures)}/{len(CASES)} grounded cases passed; "
        + "\n".join(failures[:8]))
