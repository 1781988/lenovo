from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def graph_counts(graph: dict[str, Any]) -> tuple[int, int, int]:
    entities = graph.get("entities", []) or []
    relations = graph.get("relations", []) or []
    attr_entities = sum(1 for entity in entities if isinstance(entity, dict) and entity.get("attributes"))
    return len(entities), len(relations), attr_entities


def entity_names(graph: dict[str, Any]) -> set[str]:
    return {
        str(entity.get("name", "")).strip()
        for entity in graph.get("entities", []) or []
        if isinstance(entity, dict) and str(entity.get("name", "")).strip()
    }


def relation_set(graph: dict[str, Any]) -> set[tuple[str, str, str]]:
    return {
        (str(rel[0]).strip(), str(rel[1]).strip(), str(rel[2]).strip())
        for rel in graph.get("relations", []) or []
        if isinstance(rel, list) and len(rel) >= 3 and all(str(value).strip() for value in rel[:3])
    }


def resolve_reference_dir(path: Path) -> Path:
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    if any(path.glob("[0-9]*.json")):
        return path
    nested = [child for child in path.iterdir() if child.is_dir() and any(child.glob("[0-9]*.json"))]
    if len(nested) == 1:
        return nested[0]
    raise FileNotFoundError(
        f"{path} does not contain numbered JSON files; pass the inner package directory "
        "or keep exactly one numbered-JSON child directory"
    )


def load_graph(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        graph = json.load(handle)
    if not isinstance(graph, dict):
        raise ValueError(f"{path} is not a JSON object")
    graph.setdefault("entities", [])
    graph.setdefault("relations", [])
    return graph


def load_reference_graph(reference_dir: Path | None, stem: str) -> dict[str, Any] | None:
    if reference_dir is None:
        return None
    package = resolve_reference_dir(reference_dir)
    path = package / f"{stem}.json"
    if not path.exists():
        return None
    return load_graph(path)


def selection_metrics(candidate: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    ref_entities = entity_names(reference)
    cand_entities = entity_names(candidate)
    ref_relations = relation_set(reference)
    cand_relations = relation_set(candidate)
    ref_e, ref_r, ref_a = graph_counts(reference)
    cand_e, cand_r, cand_a = graph_counts(candidate)
    entity_overlap = len(ref_entities & cand_entities)
    relation_overlap = len(ref_relations & cand_relations)
    return {
        "reference_counts": [ref_e, ref_r, ref_a],
        "candidate_counts": [cand_e, cand_r, cand_a],
        "entity_overlap": entity_overlap,
        "relation_overlap": relation_overlap,
        "entity_overlap_ratio": entity_overlap / max(1, len(ref_entities)),
        "relation_overlap_ratio": relation_overlap / max(1, len(ref_relations)),
        "relation_count_ratio": cand_r / max(1, ref_r),
        "entity_count_ratio": cand_e / max(1, ref_e),
        "attribute_gain": cand_a - ref_a,
        "same_entities": ref_entities == cand_entities,
        "same_relations": ref_relations == cand_relations,
    }


def low_attribute_rescue(metrics: dict[str, Any]) -> bool:
    ref_e, ref_r, ref_a = metrics["reference_counts"]
    _cand_e, _cand_r, cand_a = metrics["candidate_counts"]
    reference_is_attribute_poor = ref_a <= max(8, int(ref_e * 0.2))
    large_attribute_gain = cand_a >= ref_a + max(12, int(ref_e * 0.45))
    keeps_entity_shape = metrics["entity_overlap_ratio"] >= 0.78
    keeps_relation_scale = 0.55 <= metrics["relation_count_ratio"] <= 1.15
    keeps_some_relation_spine = metrics["relation_overlap_ratio"] >= 0.35 or ref_r <= 20
    return (
        reference_is_attribute_poor
        and large_attribute_gain
        and keeps_entity_shape
        and keeps_relation_scale
        and keeps_some_relation_spine
    )


def balanced_accept(metrics: dict[str, Any]) -> bool:
    _ref_e, _ref_r, ref_a = metrics["reference_counts"]
    _cand_e, _cand_r, cand_a = metrics["candidate_counts"]
    return (
        metrics["entity_overlap_ratio"] >= 0.94
        and metrics["relation_overlap_ratio"] >= 0.92
        and 0.85 <= metrics["entity_count_ratio"] <= 1.08
        and 0.85 <= metrics["relation_count_ratio"] <= 1.08
        and cand_a >= ref_a
    )


def select_graph_with_reference(
    *,
    stem: str,
    candidate: dict[str, Any],
    reference: dict[str, Any] | None,
    policy: str,
    accept_stems: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not reference or policy == "none":
        return candidate, {"policy": policy, "decision": "candidate", "reason": "no_reference_or_disabled"}

    accept_stems = accept_stems or set()
    metrics = selection_metrics(candidate, reference)

    if str(stem) in accept_stems:
        return candidate, {"policy": policy, "decision": "candidate", "reason": "forced_accept", **metrics}

    if policy == "locked":
        return reference, {"policy": policy, "decision": "reference", "reason": "locked", **metrics}

    if low_attribute_rescue(metrics):
        return candidate, {"policy": policy, "decision": "candidate", "reason": "low_attribute_rescue", **metrics}

    if policy == "balanced" and balanced_accept(metrics):
        return candidate, {"policy": policy, "decision": "candidate", "reason": "balanced_accept", **metrics}

    return reference, {"policy": policy, "decision": "reference", "reason": "safety_fallback", **metrics}
