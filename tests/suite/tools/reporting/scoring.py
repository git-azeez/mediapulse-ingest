from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .results import CheckResult, Outcome, ScoreReport


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate obligation-contract key: {key!r}")
        value[key] = item
    return value


def load_obligations(path: Path) -> dict[str, Any]:
    # JSON is a strict subset of YAML.  Keeping this file JSON-compatible avoids
    # adding a PyYAML dependency to the disposable verifier image.
    data = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_unique_object,
    )
    obligations = data.get("obligations", [])
    identifiers = [item["id"] for item in obligations]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("obligation ids must be unique")
    if sum(int(item["weight"]) for item in obligations) != int(data["total_points"]):
        raise ValueError("obligation weights do not equal total_points")
    categories = data.get("categories", [])
    category_ids = [item["id"] for item in categories]
    if len(set(category_ids)) != len(category_ids):
        raise ValueError("score category ids must be unique")
    if sum(int(item["weight"]) for item in categories) != int(data["total_points"]):
        raise ValueError("score category weights do not equal total_points")
    assigned = [identifier for category in categories for identifier in category["obligations"]]
    if len(set(assigned)) != len(assigned):
        raise ValueError("each obligation must belong to exactly one score category")
    if set(assigned) != set(identifiers):
        raise ValueError("score categories must contain every obligation exactly once")
    weights = {item["id"]: int(item["weight"]) for item in obligations}
    for category in categories:
        actual = sum(weights[identifier] for identifier in category["obligations"])
        if actual != int(category["weight"]):
            raise ValueError(
                f"score category {category['id']!r}: expected {category['weight']}, found {actual}"
            )
    for plane, expected in data["planes"].items():
        actual = sum(int(item["weight"]) for item in obligations if item["plane"] == plane)
        if actual != int(expected):
            raise ValueError(f"plane {plane!r}: expected {expected}, found {actual}")
    return data


def score_results(
    spec: dict[str, Any],
    results: Iterable[CheckResult],
    *,
    gate_overrides: dict[str, bool] | None = None,
) -> ScoreReport:
    result_list = list(results)
    by_id = {result.obligation_id: result for result in result_list}
    required = {item["id"] for item in spec["obligations"]}
    unknown = set(by_id) - required
    if unknown:
        raise ValueError(f"unknown obligation results: {sorted(unknown)}")

    trial_valid = True
    raw_score = 0
    plane_scores = {plane: {"earned": 0, "possible": int(weight)} for plane, weight in spec["planes"].items()}
    category_scores = {
        item["id"]: {
            "label": item["label"],
            "earned": 0,
            "possible": int(item["weight"]),
        }
        for item in spec["categories"]
    }
    category_by_obligation = {
        identifier: category["id"]
        for category in spec["categories"]
        for identifier in category["obligations"]
    }
    obligation_scores: dict[str, dict[str, Any]] = {}
    hard_gates = {gate: True for gate in spec.get("hard_gates", [])}
    # Integrity is established by the orchestrator and has no weighted row.
    hard_gates["trial.integrity"] = True
    hard_gates.update(gate_overrides or {})
    caps: list[str] = []

    for item in spec["obligations"]:
        result = by_id.get(item["id"])
        category = category_by_obligation[item["id"]]
        earned = 0
        if result is None:
            trial_valid = False
            outcome = "missing"
        else:
            outcome = result.outcome.value
        if result is not None and (result.outcome is Outcome.INVALID or result.outcome is Outcome.NOT_RUN):
            trial_valid = False
        if result is not None and result.outcome is Outcome.PASS:
            weight = int(item["weight"])
            earned = weight
            raw_score += weight
            plane_scores[item["plane"]]["earned"] += weight
            category_scores[category]["earned"] += weight
        obligation_scores[item["id"]] = {
            "category": category,
            "plane": item["plane"],
            "earned": earned,
            "possible": int(item["weight"]),
            "outcome": outcome,
            "experiments": list(item["then"]),
        }
        gate = (result.hard_gate if result is not None else None) or item.get("hard_gate")
        if gate and (result is None or result.outcome is not Outcome.PASS):
            hard_gates[gate] = False
        if result is not None and result.cap_reason:
            caps.append(result.cap_reason)

    score = raw_score
    caps_config = spec.get("score_caps", {})
    if "accepted_write_loss_or_corruption" in caps:
        score = min(score, int(caps_config["accepted_write_loss_or_corruption"]))
    if "critical_auth_escalation" in caps:
        score = min(score, int(caps_config["critical_auth_escalation"]))
    if "cleanup_leak" in caps:
        score = min(score, int(caps_config["cleanup_leak"]))

    total = int(spec["total_points"])
    # Harbor rewards are normalized to [0.0, 1.0]. Keep partial credit visible:
    # 8 earned points out of 100 must be reported as 0.08, not collapsed to 0.
    # A failed integrity check still invalidates reward, while failed rubric hard
    # gates remain visible in the report and in the earned point total.
    reward = score / total if trial_valid and hard_gates["trial.integrity"] else 0.0
    return ScoreReport(
        score=score,
        raw_score=raw_score,
        total=total,
        threshold=int(spec["pass_threshold"]),
        reward=reward,
        trial_valid=trial_valid,
        hard_gates=hard_gates,
        plane_scores=plane_scores,
        category_scores=category_scores,
        obligation_scores=obligation_scores,
        results=result_list,
        caps_applied=sorted(set(caps)),
    )
