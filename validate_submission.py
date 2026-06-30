#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


def load_json_files(path: Path) -> tuple[list[tuple[str, dict]], list[str]]:
    if path.is_dir():
        files = sorted(path.glob("*.json"), key=lambda p: int(p.stem.split("_")[-1]) if p.stem.split("_")[-1].isdigit() else p.stem)
        return [(p.name, json.loads(p.read_text(encoding="utf-8"))) for p in files], []
    if path.suffix.lower() == ".zip":
        items: list[tuple[str, dict]] = []
        errors: list[str] = []
        with zipfile.ZipFile(path) as zf:
            names = sorted(name for name in zf.namelist() if name.endswith(".json"))
            for name in names:
                if not name.startswith("submit/submit_"):
                    errors.append(f"zip JSON is not under submit/submit_*.json: {name}")
            for name in names:
                items.append((name, json.loads(zf.read(name).decode("utf-8"))))
        return items, errors
    raise ValueError(f"Unsupported path: {path}")


def validate_graph(name: str, graph: dict) -> tuple[list[str], tuple[int, int, int]]:
    errors: list[str] = []
    entities = graph.get("entities")
    relations = graph.get("relations")
    if not isinstance(entities, list):
        errors.append(f"{name}: entities is not a list")
        entities = []
    if not isinstance(relations, list):
        errors.append(f"{name}: relations is not a list")
        relations = []

    entity_names: set[str] = set()
    attributed = 0
    for index, entity in enumerate(entities):
        if not isinstance(entity, dict):
            errors.append(f"{name}: entity #{index} is not an object")
            continue
        entity_name = str(entity.get("name", "")).strip()
        entity_type = str(entity.get("type", "")).strip()
        attrs = entity.get("attributes", {})
        if not entity_name:
            errors.append(f"{name}: entity #{index} has empty name")
        if not entity_type:
            errors.append(f"{name}: entity {entity_name} has empty type")
        if not isinstance(attrs, dict):
            errors.append(f"{name}: entity {entity_name} attributes is not an object")
        elif attrs:
            attributed += 1
        if entity_name in entity_names:
            errors.append(f"{name}: duplicate entity {entity_name}")
        entity_names.add(entity_name)

    seen_relations: set[tuple[str, str, str]] = set()
    for index, relation in enumerate(relations):
        if not (isinstance(relation, list) and len(relation) == 3):
            errors.append(f"{name}: relation #{index} is not [source, relation, target]")
            continue
        source, rel_type, target = [str(x).strip() for x in relation]
        if not source or not rel_type or not target:
            errors.append(f"{name}: relation #{index} contains empty field")
            continue
        if source == target:
            errors.append(f"{name}: self-loop relation {relation}")
        if source not in entity_names:
            errors.append(f"{name}: relation source not found: {source}")
        if target not in entity_names:
            errors.append(f"{name}: relation target not found: {target}")
        key = (source, rel_type, target)
        if key in seen_relations:
            errors.append(f"{name}: duplicate relation {relation}")
        seen_relations.add(key)

    return errors, (len(entities), len(relations), attributed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Lenovo KG JSON files or final zip package.")
    parser.add_argument("path", type=Path, help="Directory with JSON files or final submission zip.")
    parser.add_argument("--expected-count", type=int, default=25)
    args = parser.parse_args()

    items, all_errors = load_json_files(args.path)
    totals = [0, 0, 0]
    for name, graph in items:
        errors, counts = validate_graph(name, graph)
        all_errors.extend(errors)
        totals[0] += counts[0]
        totals[1] += counts[1]
        totals[2] += counts[2]
        print(f"{name}: E={counts[0]} R={counts[1]} A={counts[2]}")

    if len(items) != args.expected_count:
        all_errors.append(f"expected {args.expected_count} JSON files, got {len(items)}")

    print(f"TOTAL: files={len(items)} entities={totals[0]} relations={totals[1]} attributed_entities={totals[2]}")
    if all_errors:
        print("INVALID:")
        for error in all_errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("VALID")


if __name__ == "__main__":
    main()
