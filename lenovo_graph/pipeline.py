from __future__ import annotations

import json
import re
import shutil
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .config import ExtractConfig
from .file_postprocess import apply_file_postprocess
from .io import chunk_text, collect_input_files, detect_language, read_document
from .llm import generate_json
from .postprocess import (
    apply_profile_filters,
    clean_entity_display_name,
    default_entity_type,
    enrich_attributes_from_source,
    endpoint_is_atomic,
    inventory_for_prompt,
    iter_name_aliases,
    language_mismatch,
    merge_attribute_updates,
    normalize_attributes,
    normalize_name_key,
    normalize_competition_graph,
    normalize_entity_type,
    normalize_relation_type,
    parse_json_response,
    should_keep_relation_type,
)
from .profiles import DEFAULT_EN_PROFILE, DEFAULT_ZH_PROFILE, DocumentProfile, get_document_profile, get_final_round_profile
from .prompt import (
    build_attribute_prompt,
    build_extraction_prompt,
    build_inventory_prompt,
    build_reference_patch_prompt,
    build_reference_relation_rescue_prompt,
    build_relation_delta_prompt,
    build_relation_prompt,
)
from .selection import load_reference_graph, select_graph_with_reference


def _effective_prompt_variant(config: ExtractConfig, stem: str) -> str:
    if config.disable_numbered_profiles:
        return config.prompt_variant if config.prompt_variant != "auto" else "auto"
    if config.prompt_variant != "auto":
        return config.prompt_variant
    if stem == "6":
        return "recall"
    if stem == "22":
        return "attribute"
    if stem in {"1", "2", "3", "4", "5", "8", "9", "10", "11", "13", "14", "15", "17", "23", "25"}:
        return "precision"
    return "auto"


def extract_file(input_file: Path, config: ExtractConfig) -> Path:
    output_path = config.output_file or (config.output_dir / f"{input_file.stem}.json")
    patch_stems = set(config.reference_patch_stems)
    delta_stems = _resolve_relation_delta_stems(config.relation_delta_stems)
    if config.reference_dir and input_file.stem in delta_stems:
        reference_graph = load_reference_graph(config.reference_dir, input_file.stem)
        if reference_graph is not None:
            text = read_document(input_file)
            language = detect_language(text)
            profile = get_document_profile(input_file.stem, language)
            graph, delta_payload = _extract_relation_delta(
                text=text,
                language=language,
                config=config,
                profile=profile,
                reference_graph=reference_graph,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
            if config.keep_raw:
                raw_dir = config.output_dir / ".lenovo_graph_raw" / input_file.stem
                raw_dir.mkdir(parents=True, exist_ok=True)
                (raw_dir / "stages.json").write_text(
                    json.dumps(
                        {
                            "language": language,
                            "profile": {
                                "name": profile.name,
                                "target_entities": profile.target_entities,
                                "target_relations": profile.target_relations,
                            },
                            **delta_payload,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            return output_path

    if config.reference_dir and input_file.stem in patch_stems:
        reference_graph = load_reference_graph(config.reference_dir, input_file.stem)
        if reference_graph is not None:
            text = read_document(input_file)
            language = detect_language(text)
            profile = get_document_profile(input_file.stem, language)
            graph, patch_payload = _extract_reference_patch(
                text=text,
                language=language,
                config=config,
                profile=profile,
                reference_graph=reference_graph,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
            if config.keep_raw:
                raw_dir = config.output_dir / ".lenovo_graph_raw" / input_file.stem
                raw_dir.mkdir(parents=True, exist_ok=True)
                (raw_dir / "stages.json").write_text(
                    json.dumps(
                        {
                            "language": language,
                            "profile": {
                                "name": profile.name,
                                "target_entities": profile.target_entities,
                                "target_relations": profile.target_relations,
                            },
                            **patch_payload,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            return output_path

    candidate_stems = set(config.candidate_stems)
    if (
        config.pass_through_reference
        and
        config.reference_dir
        and (candidate_stems or patch_stems or delta_stems)
        and input_file.stem not in candidate_stems
        and input_file.stem not in patch_stems
        and input_file.stem not in delta_stems
    ):
        reference_graph = load_reference_graph(config.reference_dir, input_file.stem)
        if reference_graph is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(reference_graph, ensure_ascii=False, indent=2), encoding="utf-8")
            if config.keep_raw:
                raw_dir = config.output_dir / ".lenovo_graph_raw" / input_file.stem
                raw_dir.mkdir(parents=True, exist_ok=True)
                (raw_dir / "stages.json").write_text(
                    json.dumps(
                        {
                            "mode": "reference_passthrough",
                            "selection": {
                                "policy": config.selection_policy,
                                "decision": "reference",
                                "reason": "outside_candidate_patch_or_delta_stems",
                            },
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            return output_path

    text = read_document(input_file)
    language = detect_language(text)
    if config.final_round_profiles:
        profile = get_final_round_profile(input_file.stem, language)
    elif config.disable_numbered_profiles:
        profile = DEFAULT_ZH_PROFILE if language == "zh" else DEFAULT_EN_PROFILE
    else:
        profile = get_document_profile(input_file.stem, language)
    prompt_variant = _effective_prompt_variant(config, input_file.stem)
    reference_guidance = None
    if config.reference_guidance and config.reference_dir:
        reference_graph_for_guidance = load_reference_graph(config.reference_dir, input_file.stem)
        if reference_graph_for_guidance is not None:
            reference_guidance = _build_reference_guidance(reference_graph_for_guidance)
    chunks = chunk_text(text, config.chunk_chars, config.overlap_chars)
    if config.single_stage:
        graph, raw_payload = _extract_single_stage(chunks, language, config, profile, prompt_variant, reference_guidance)
    else:
        graph, raw_payload = _extract_multi_stage(text, chunks, language, config, profile, prompt_variant, reference_guidance)
    graph = enrich_attributes_from_source(graph, text, language)  # type: ignore[arg-type]
    graph = apply_profile_filters(graph, profile, language)  # type: ignore[arg-type]
    if not config.disable_file_postprocess:
        graph = apply_file_postprocess(input_file.stem, graph, text, language)  # type: ignore[arg-type]
    reference_graph = load_reference_graph(config.reference_dir, input_file.stem)
    rescue_payload = None
    rescue_stems = set(config.reference_relation_rescue_stems)
    should_rescue = config.reference_relation_rescue and (
        not rescue_stems or input_file.stem in rescue_stems
    )
    if should_rescue and reference_graph:
        graph, rescue_payload = _rescue_reference_relations(
            stem=input_file.stem,
            text=text,
            language=language,
            config=config,
            profile=profile,
            candidate_graph=graph,
            reference_graph=reference_graph,
        )
    graph, selection_payload = select_graph_with_reference(
        stem=input_file.stem,
        candidate=graph,
        reference=reference_graph,
        policy=config.selection_policy,
        accept_stems=set(config.selection_accept_stems),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")

    if config.keep_raw:
        raw_dir = config.output_dir / ".lenovo_graph_raw" / input_file.stem
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "stages.json").write_text(
            json.dumps(
                {
                    "language": language,
                    "profile": {
                        "name": profile.name,
                        "target_entities": profile.target_entities,
                        "target_relations": profile.target_relations,
                    },
                    "prompt_variant": prompt_variant,
                    "reference_guidance": bool(reference_guidance),
                    "reference_relation_rescue": rescue_payload,
                    "chunk_count": len(chunks),
                    "chunks": chunks,
                    "selection": selection_payload,
                    **raw_payload,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    return output_path


def _rescue_reference_relations(
    *,
    stem: str,
    text: str,
    language: str,
    config: ExtractConfig,
    profile: DocumentProfile,
    candidate_graph: dict,
    reference_graph: dict,
) -> tuple[dict, dict]:
    candidates = _missing_reference_relations(
        candidate_graph=candidate_graph,
        reference_graph=reference_graph,
        language=language,
        limit=config.rescue_relation_limit,
    )
    if not candidates:
        return candidate_graph, {
            "candidate_count": 0,
            "accepted_count": 0,
            "accepted": [],
            "batches": [],
        }
    accepted_all: list[list[str]] = []
    batches: list[dict] = []
    graph = candidate_graph
    batch_size = max(1, config.rescue_batch_size)
    for start in range(0, len(candidates), batch_size):
        batch = candidates[start:start + batch_size]
        prompt = build_reference_relation_rescue_prompt(
            text=text,
            language=language,
            candidate_graph=graph,
            relation_candidates=batch,
            profile=profile,
        )
        response = generate_json(prompt, config)
        parsed = parse_json_response(response)
        graph, accepted = _apply_reference_relation_rescue(
            candidate_graph=graph,
            confirmed_payload=parsed,
            relation_candidates=batch,
            language=language,
        )
        accepted_all.extend(accepted)
        batches.append(
            {
                "start": start,
                "candidate_count": len(batch),
                "accepted_count": len(accepted),
                "accepted": accepted,
                "parsed": parsed,
                "raw": response,
            }
        )
    graph = apply_profile_filters(graph, profile, language)  # type: ignore[arg-type]
    graph = apply_file_postprocess(stem, graph, text, language)  # type: ignore[arg-type]
    return graph, {
        "candidate_count": len(candidates),
        "accepted_count": len(accepted_all),
        "accepted": accepted_all,
        "batches": batches,
    }


def _missing_reference_relations(
    *,
    candidate_graph: dict,
    reference_graph: dict,
    language: str,
    limit: int,
) -> list[list[str]]:
    candidate_entities = {
        normalize_name_key(entity.get("name", ""))
        for entity in candidate_graph.get("entities", []) or []
        if isinstance(entity, dict) and entity.get("name")
    }
    candidate_relations = {
        tuple(normalize_name_key(value) if idx != 1 else str(value).strip() for idx, value in enumerate(relation[:3]))
        for relation in candidate_graph.get("relations", []) or []
        if isinstance(relation, list) and len(relation) >= 3
    }
    rows: list[tuple[int, list[str]]] = []
    for relation in reference_graph.get("relations", []) or []:
        if not isinstance(relation, list) or len(relation) < 3:
            continue
        source, relation_type, target = [str(value).strip() for value in relation[:3]]
        if not source or not relation_type or not target or source == target:
            continue
        if language_mismatch(source, language) or language_mismatch(target, language) or language_mismatch(relation_type, language):
            continue
        if not should_keep_relation_type(relation_type):
            continue
        relation_key = (normalize_name_key(source), relation_type, normalize_name_key(target))
        if relation_key in candidate_relations:
            continue
        source_present = normalize_name_key(source) in candidate_entities
        target_present = normalize_name_key(target) in candidate_entities
        score = 0
        if source_present:
            score += 3
        if target_present:
            score += 3
        if len(relation_type) <= (8 if language == "zh" else 18):
            score += 1
        if source_present and target_present:
            score += 3
        rows.append((score, [source, relation_type, target]))
    rows.sort(key=lambda item: (-item[0], item[1]))
    return [row for _, row in rows[: max(0, limit)]]


def _apply_reference_relation_rescue(
    *,
    candidate_graph: dict,
    confirmed_payload: dict,
    relation_candidates: list[list[str]],
    language: str,
) -> tuple[dict, list[list[str]]]:
    entities = [
        {
            "name": entity.get("name", ""),
            "type": entity.get("type", ""),
            "attributes": dict(entity.get("attributes") or {}),
        }
        for entity in candidate_graph.get("entities", []) or []
        if isinstance(entity, dict) and entity.get("name")
    ]
    relations = [
        [str(relation[0]).strip(), str(relation[1]).strip(), str(relation[2]).strip()]
        for relation in candidate_graph.get("relations", []) or []
        if isinstance(relation, list) and len(relation) >= 3 and all(str(value).strip() for value in relation[:3])
    ]
    candidate_set = {tuple(row) for row in relation_candidates}
    candidate_by_id = {idx + 1: row for idx, row in enumerate(relation_candidates)}
    existing = {tuple(row) for row in relations}
    by_key = {normalize_name_key(entity["name"]): entity for entity in entities}
    accepted: list[list[str]] = []
    confirmed_items = confirmed_payload.get("confirmed_relation_ids")
    if confirmed_items is None:
        confirmed_items = confirmed_payload.get("confirmed_relations", [])
    for item in confirmed_items or []:
        if not isinstance(item, dict):
            continue
        try:
            confidence = float(item.get("confidence", 0))
        except (TypeError, ValueError):
            confidence = 0
        if confidence < 8 or not str(item.get("evidence", "")).strip():
            continue
        row = None
        if "candidate_id" in item:
            try:
                row = candidate_by_id.get(int(item.get("candidate_id")))
            except (TypeError, ValueError):
                row = None
        if row is None:
            row = [
                str(item.get("source", "")).strip(),
                str(item.get("type", "")).strip(),
                str(item.get("target", "")).strip(),
            ]
        if tuple(row) not in candidate_set or tuple(row) in existing:
            continue
        if language_mismatch(row[0], language) or language_mismatch(row[1], language) or language_mismatch(row[2], language):
            continue
        if not should_keep_relation_type(row[1]):
            continue
        for endpoint in (row[0], row[2]):
            key = normalize_name_key(endpoint)
            if key not in by_key:
                by_key[key] = {
                    "name": endpoint,
                    "type": default_entity_type(language == "zh"),
                    "attributes": {},
                }
                entities.append(by_key[key])
        relations.append(row)
        existing.add(tuple(row))
        accepted.append(row)
    graph = {"entities": entities, "relations": relations}
    return normalize_competition_graph([graph], language), accepted  # type: ignore[arg-type]


def _build_reference_guidance(reference_graph: dict) -> dict:
    entities = [
        {
            "name": entity.get("name", ""),
            "type": entity.get("type", ""),
            "attributes": entity.get("attributes", {}),
        }
        for entity in reference_graph.get("entities", []) or []
        if isinstance(entity, dict) and entity.get("name")
    ]
    relations = [
        relation[:3]
        for relation in reference_graph.get("relations", []) or []
        if isinstance(relation, list) and len(relation) >= 3
    ]
    label_counts: dict[str, int] = {}
    for _, label, _ in relations:
        label_text = str(label).strip()
        if label_text:
            label_counts[label_text] = label_counts.get(label_text, 0) + 1
    relation_labels = [
        label
        for label, _ in sorted(label_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return {
        "counts": {
            "entities": len(entities),
            "relations": len(relations),
            "attributed_entities": sum(1 for entity in entities if entity.get("attributes")),
        },
        "entities": entities,
        "relations": relations,
        "relation_labels": relation_labels,
    }


def _extract_single_stage(
    chunks: list[str],
    language: str,
    config: ExtractConfig,
    profile: DocumentProfile,
    prompt_variant: str,
    reference_guidance: dict | None = None,
) -> tuple[dict, dict]:
    raw_results: list[dict] = []

    def run_chunk(index_and_text: tuple[int, str]) -> tuple[int, dict, str]:
        idx, chunk = index_and_text
        prompt = build_extraction_prompt(
            text=chunk,
            language=language,
            chunk_index=idx,
            chunk_count=len(chunks),
            profile=profile,
            prompt_variant=prompt_variant,
            reference_guidance=reference_guidance,
            strategy_note=config.strategy_note,
        )
        response = generate_json(prompt, config)
        return idx, parse_json_response(response), response

    workers = max(1, config.max_concurrent)
    raw_text_responses: list[tuple[int, str]] = []
    if workers == 1:
        for item in enumerate(chunks):
            idx, parsed, raw = run_chunk(item)
            raw_results.append(parsed)
            raw_text_responses.append((idx, raw))
    else:
        ordered: dict[int, dict] = {}
        ordered_raw: dict[int, str] = {}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(run_chunk, item) for item in enumerate(chunks)]
            for future in as_completed(futures):
                idx, parsed, raw = future.result()
                ordered[idx] = parsed
                ordered_raw[idx] = raw
        raw_results = [ordered[idx] for idx in sorted(ordered)]
        raw_text_responses = [(idx, ordered_raw[idx]) for idx in sorted(ordered_raw)]

    graph = normalize_competition_graph(  # type: ignore[arg-type]
        raw_results,
        language,
        preserve_source_relation_labels=config.preserve_source_relation_labels,
    )
    return graph, {
        "mode": "single_stage",
        "prompt_variant": prompt_variant,
        "parsed": raw_results,
        "raw": [{"chunk": idx, "response": raw} for idx, raw in raw_text_responses],
    }


def _extract_multi_stage(
    text: str,
    chunks: list[str],
    language: str,
    config: ExtractConfig,
    profile: DocumentProfile,
    prompt_variant: str,
    reference_guidance: dict | None = None,
) -> tuple[dict, dict]:
    inventory_results, inventory_raw = _run_inventory_stage(chunks, language, config, profile, prompt_variant, reference_guidance)
    inventory_graph = normalize_competition_graph(  # type: ignore[arg-type]
        inventory_results,
        language,
        preserve_source_relation_labels=config.preserve_source_relation_labels,
    )
    prompt_inventory = inventory_for_prompt(inventory_graph)

    relation_results, relation_raw = _run_relation_stage(
        chunks,
        language,
        config,
        prompt_inventory,
        profile,
        prompt_variant,
        reference_guidance,
    )
    relation_inputs = [{"entities": inventory_graph.get("entities", []), "relations": []}]
    relation_inputs.extend(relation_results)
    graph = normalize_competition_graph(  # type: ignore[arg-type]
        relation_inputs,
        language,
        preserve_source_relation_labels=config.preserve_source_relation_labels,
    )

    attribute_results, attribute_raw = _run_attribute_stage(text, graph, language, config, profile, prompt_variant, reference_guidance)
    graph = merge_attribute_updates(graph, attribute_results, language)  # type: ignore[arg-type]

    return graph, {
        "mode": "multi_stage",
        "prompt_variant": prompt_variant,
        "inventory": {
            "parsed": inventory_results,
            "raw": inventory_raw,
            "entity_count": len(inventory_graph.get("entities", [])),
        },
        "relations": {
            "parsed": relation_results,
            "raw": relation_raw,
        },
        "attributes": {
            "parsed": attribute_results,
            "raw": attribute_raw,
        },
    }


def _extract_reference_patch(
    *,
    text: str,
    language: str,
    config: ExtractConfig,
    profile: DocumentProfile,
    reference_graph: dict,
) -> tuple[dict, dict]:
    prompt = build_reference_patch_prompt(
        text=text,
        language=language,
        reference_graph=reference_graph,
        profile=profile,
        attribute_limit=config.patch_attribute_limit,
        relation_limit=config.patch_relation_limit,
    )
    response = generate_json(prompt, config)
    parsed = parse_json_response(response)
    graph, accepted = _apply_reference_patch(
        reference_graph=reference_graph,
        patch=parsed,
        language=language,
        attribute_limit=config.patch_attribute_limit,
        relation_limit=config.patch_relation_limit,
    )
    return graph, {
        "mode": "reference_patch",
        "patch": {
            "parsed": parsed,
            "accepted": accepted,
            "raw": response,
        },
    }


def _resolve_relation_delta_stems(stems: tuple[str, ...]) -> set[str]:
    values = {item.strip() for item in stems if item.strip()}
    if "auto" in values:
        values.remove("auto")
        values.update({"5", "10", "14", "15", "16"})
    return values


def _extract_relation_delta(
    *,
    text: str,
    language: str,
    config: ExtractConfig,
    profile: DocumentProfile,
    reference_graph: dict,
) -> tuple[dict, dict]:
    prompt = build_relation_delta_prompt(
        text=text,
        language=language,
        reference_graph=reference_graph,
        profile=profile,
        add_entity_limit=config.delta_add_entity_limit,
        add_relation_limit=config.delta_add_relation_limit,
        remove_relation_limit=config.delta_remove_relation_limit,
    )
    response = generate_json(prompt, config)
    parsed = parse_json_response(response)
    graph, accepted = _apply_relation_delta(
        reference_graph=reference_graph,
        delta=parsed,
        language=language,
        add_entity_limit=config.delta_add_entity_limit,
        add_relation_limit=config.delta_add_relation_limit,
        remove_relation_limit=config.delta_remove_relation_limit,
    )
    return graph, {
        "mode": "relation_spine_delta",
        "delta": {
            "parsed": parsed,
            "accepted": accepted,
            "raw": response,
        },
    }


def _apply_relation_delta(
    *,
    reference_graph: dict,
    delta: dict,
    language: str,
    add_entity_limit: int,
    add_relation_limit: int,
    remove_relation_limit: int,
) -> tuple[dict, dict]:
    zh = language == "zh"
    entities = [
        {
            "name": entity.get("name", ""),
            "type": entity.get("type", ""),
            "attributes": dict(entity.get("attributes") or {}),
        }
        for entity in reference_graph.get("entities", []) or []
        if isinstance(entity, dict) and entity.get("name")
    ]
    relations = [
        [str(relation[0]).strip(), str(relation[1]).strip(), str(relation[2]).strip()]
        for relation in reference_graph.get("relations", []) or []
        if isinstance(relation, list) and len(relation) >= 3 and all(str(value).strip() for value in relation[:3])
    ]
    by_key = {normalize_name_key(entity["name"]): entity for entity in entities}
    name_by_key = {normalize_name_key(entity["name"]): entity["name"] for entity in entities}
    existing_relations = {tuple(relation) for relation in relations}

    accepted_entities: list[dict] = []
    for item in delta.get("entity_additions", []) or []:
        if len(accepted_entities) >= max(0, add_entity_limit):
            break
        if not isinstance(item, dict) or not _delta_confident(item):
            continue
        name = clean_entity_display_name(item.get("name", ""), language)
        if not _safe_delta_endpoint(name, language):
            continue
        key = normalize_name_key(name)
        if not key or key in by_key:
            continue
        entity_type = normalize_entity_type(item.get("type", ""), name, zh, language)
        attrs = normalize_attributes(item.get("attributes", {}), language, entity_type)
        entity = {"name": name, "type": entity_type, "attributes": attrs}
        entities.append(entity)
        by_key[key] = entity
        name_by_key[key] = name
        for alias in iter_name_aliases(name):
            alias_key = normalize_name_key(alias)
            if alias_key:
                name_by_key[alias_key] = name
        accepted_entities.append(
            {
                "name": name,
                "type": entity_type,
                "change_type": item.get("change_type", ""),
                "evidence": item.get("evidence", ""),
            }
        )

    accepted_removals: list[list[str]] = []
    for item in delta.get("relation_removals", []) or []:
        if len(accepted_removals) >= max(0, remove_relation_limit):
            break
        if not isinstance(item, dict) or not _delta_confident(item):
            continue
        row = [
            str(item.get("source", "")).strip(),
            str(item.get("type", "")).strip(),
            str(item.get("target", "")).strip(),
        ]
        if tuple(row) not in existing_relations:
            continue
        relations = [relation for relation in relations if relation != row]
        existing_relations.discard(tuple(row))
        accepted_removals.append(row)

    accepted_relations: list[list[str]] = []
    for item in delta.get("relation_additions", []) or []:
        if len(accepted_relations) >= max(0, add_relation_limit):
            break
        if not isinstance(item, dict) or not _delta_confident(item):
            continue
        source = name_by_key.get(normalize_name_key(item.get("source", "")))
        target = name_by_key.get(normalize_name_key(item.get("target", "")))
        relation_type = str(item.get("type", "")).strip()
        if not source or not target or source == target:
            continue
        if language_mismatch(relation_type, language) or not should_keep_relation_type(relation_type):
            continue
        relation_type, invert = normalize_relation_type(relation_type, zh)
        if not should_keep_relation_type(relation_type):
            continue
        if invert:
            source, target = target, source
        row = [source, relation_type, target]
        if tuple(row) in existing_relations:
            continue
        relations.append(row)
        existing_relations.add(tuple(row))
        accepted_relations.append(row)

    return {"entities": entities, "relations": relations}, {
        "entity_additions": accepted_entities,
        "relation_additions": accepted_relations,
        "relation_removals": accepted_removals,
    }


def _delta_confident(item: dict) -> bool:
    confidence = item.get("confidence", 0)
    try:
        score = float(confidence)
    except (TypeError, ValueError):
        score = 0
    change_type = str(item.get("change_type", "")).strip()
    evidence = str(item.get("evidence", "")).strip()
    allowed = {
        "missing_core_entity",
        "missing_core_relation",
        "wrong_relation_label",
        "wrong_endpoint_granularity",
        "noisy_relation_removal",
    }
    return score >= 7 and change_type in allowed and bool(evidence)


def _safe_delta_endpoint(name: str, language: str) -> bool:
    if not name or language_mismatch(name, language):
        return False
    if not endpoint_is_atomic(name):
        return False
    if language == "zh" and len(name) > 32:
        return False
    if language == "en" and len(name.split()) > 5:
        return False
    bad_fragments = (
        "score", "confidence", "evidence", "change_type", "description",
        "说明", "描述", "证据", "置信", "评分",
    )
    lowered = name.lower()
    return not any(fragment in lowered for fragment in bad_fragments)


def _apply_reference_patch(
    *,
    reference_graph: dict,
    patch: dict,
    language: str,
    attribute_limit: int,
    relation_limit: int,
) -> tuple[dict, dict]:
    entities = [dict(entity) for entity in reference_graph.get("entities", []) or [] if isinstance(entity, dict)]
    relations = [relation[:3] for relation in reference_graph.get("relations", []) or [] if isinstance(relation, list) and len(relation) >= 3]
    by_key = {normalize_name_key(entity.get("name", "")): entity for entity in entities}
    name_by_key = {normalize_name_key(entity.get("name", "")): entity.get("name", "") for entity in entities}
    existing_relations = {tuple(relation) for relation in relations}

    accepted_attrs: list[dict] = []
    for item in patch.get("attribute_updates", []) or []:
        if len(accepted_attrs) >= max(0, attribute_limit):
            break
        if not isinstance(item, dict):
            continue
        key = normalize_name_key(item.get("name", ""))
        entity = by_key.get(key)
        if not entity:
            continue
        attrs = normalize_attributes(
            item.get("attributes", {}),
            language,
            entity.get("type", ""),
        )
        attrs = _filter_patch_attributes(entity.get("attributes") or {}, attrs)
        if not attrs:
            continue
        existing = dict(entity.get("attributes") or {})
        existing.update(attrs)
        entity["attributes"] = normalize_attributes(existing, language, entity.get("type", ""))
        accepted_attrs.append({"name": entity.get("name", ""), "attributes": attrs})

    accepted_relations: list[list[str]] = []
    for relation in patch.get("relation_additions", []) or []:
        if len(accepted_relations) >= max(0, relation_limit):
            break
        if not isinstance(relation, list) or len(relation) < 3:
            continue
        source = name_by_key.get(normalize_name_key(relation[0]))
        rel_type = str(relation[1] or "").strip()
        target = name_by_key.get(normalize_name_key(relation[2]))
        if not source or not target or source == target or not should_keep_relation_type(rel_type):
            continue
        row = [source, rel_type, target]
        if tuple(row) in existing_relations:
            continue
        relations.append(row)
        existing_relations.add(tuple(row))
        accepted_relations.append(row)

    return {"entities": entities, "relations": relations}, {
        "attribute_updates": accepted_attrs,
        "relation_additions": accepted_relations,
    }


def _filter_patch_attributes(existing: dict, attrs: dict) -> dict:
    if existing:
        return {}
    filtered = {}
    bad_keys = {
        "description", "Description", "简介", "说明", "描述", "定义",
        "依赖于", "依赖", "影响", "触发", "同步", "协同", "服务于", "配置",
        "监控", "contains", "supports", "collected_by", "features_character",
        "wrote_about", "reliance", "causes", "depends_on",
    }
    good_key_markers = (
        "别名", "全称", "学名", "功能", "用途", "特征", "特点", "示例", "位置",
        "原因", "材料", "标准", "协议", "类型", "角色", "领域", "来源", "发布方",
        "alias", "full_name", "scientific_name", "function", "use", "feature",
        "example", "location", "cause", "material", "standard", "role", "origin",
        "value", "impact", "consequence", "importance",
    )
    for key, value in attrs.items():
        if key in existing:
            continue
        if key in bad_keys:
            continue
        if "_" in str(key) and str(key) not in {"full_name", "scientific_name"}:
            continue
        if not any(marker in str(key) for marker in good_key_markers):
            continue
        value_text = str(value).strip()
        if not value_text:
            continue
        if key in bad_keys and len(value_text) > 36:
            continue
        if len(value_text) > 80:
            continue
        if any(marker in value_text for marker in ("\n", "。", "；", ";", "[", "]", "{", "}")):
            continue
        if value_text.count(",") >= 2 or value_text.count("，") >= 2 or value_text.count("、") >= 2:
            continue
        filtered[key] = value
    return filtered


def _run_inventory_stage(
    chunks: list[str],
    language: str,
    config: ExtractConfig,
    profile: DocumentProfile,
    prompt_variant: str,
    reference_guidance: dict | None = None,
) -> tuple[list[dict], list[dict]]:
    parsed: list[dict] = []
    raw_items: list[dict] = []
    for idx, chunk in enumerate(chunks):
        prompt = build_inventory_prompt(
            text=chunk,
            language=language,
            chunk_index=idx,
            chunk_count=len(chunks),
            profile=profile,
            prompt_variant=prompt_variant,
            reference_guidance=reference_guidance,
            strategy_note=config.strategy_note,
        )
        response = generate_json(prompt, config)
        parsed.append(parse_json_response(response))
        raw_items.append({"chunk": idx, "response": response})
    return parsed, raw_items


def _run_relation_stage(
    chunks: list[str],
    language: str,
    config: ExtractConfig,
    prompt_inventory: list[dict],
    profile: DocumentProfile,
    prompt_variant: str,
    reference_guidance: dict | None = None,
) -> tuple[list[dict], list[dict]]:
    parsed: list[dict] = []
    raw_items: list[dict] = []
    for idx, chunk in enumerate(chunks):
        prompt = build_relation_prompt(
            text=chunk,
            language=language,
            chunk_index=idx,
            chunk_count=len(chunks),
            inventory_entities=prompt_inventory,
            profile=profile,
            prompt_variant=prompt_variant,
            reference_guidance=reference_guidance,
            strategy_note=config.strategy_note,
        )
        response = generate_json(prompt, config)
        parsed.append(parse_json_response(response))
        raw_items.append({"chunk": idx, "response": response})
    return parsed, raw_items


def _run_attribute_stage(
    text: str,
    graph: dict,
    language: str,
    config: ExtractConfig,
    profile: DocumentProfile,
    prompt_variant: str,
    reference_guidance: dict | None = None,
) -> tuple[list[dict], list[dict]]:
    entities = graph.get("entities", []) or []
    parsed: list[dict] = []
    raw_items: list[dict] = []
    batch_size = max(1, config.attribute_batch_size)
    for start in range(0, len(entities), batch_size):
        batch = entities[start : start + batch_size]
        text_window = _attribute_context_for_batch(text, batch, config.attribute_text_chars)
        prompt = build_attribute_prompt(
            text=text_window,
            language=language,
            entities=batch,
            profile=profile,
            prompt_variant=prompt_variant,
            reference_guidance=reference_guidance,
            strategy_note=config.strategy_note,
        )
        response = generate_json(prompt, config)
        parsed.append(parse_json_response(response))
        raw_items.append(
            {
                "entity_start": start,
                "entity_count": len(batch),
                "context_chars": len(text_window),
                "response": response,
            }
        )
    return parsed, raw_items


def _attribute_context_for_batch(text: str, entities: list[dict], max_chars: int) -> str:
    snippets: list[tuple[int, str]] = []
    seen_ranges: set[tuple[int, int]] = set()
    window = 360
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        names = [n for n in iter_name_aliases(entity.get("name", "")) if n and len(n) >= 2]
        matched_for_entity = 0
        for name in sorted(set(names), key=len, reverse=True):
            pattern = re.escape(name)
            for match in re.finditer(pattern, text, flags=re.IGNORECASE if name.isascii() else 0):
                start = max(0, match.start() - window)
                end = min(len(text), match.end() + window)
                range_key = (start, end)
                if range_key in seen_ranges:
                    continue
                seen_ranges.add(range_key)
                snippets.append((start, text[start:end].strip()))
                matched_for_entity += 1
                if matched_for_entity >= 2:
                    break
            if matched_for_entity:
                break
    if not snippets:
        return text[:max_chars]
    snippets.sort(key=lambda item: item[0])
    parts: list[str] = []
    total = 0
    for _, snippet in snippets:
        if not snippet:
            continue
        block = f"[片段]\n{snippet}"
        if total + len(block) + 2 > max_chars:
            break
        parts.append(block)
        total += len(block) + 2
    return "\n\n".join(parts) if parts else text[:max_chars]


def extract_path(input_path: Path, config: ExtractConfig) -> list[Path]:
    files = collect_input_files(input_path)
    if config.output_file and len(files) > 1:
        raise ValueError("--output-file can only be used with a single input file")

    outputs: list[Path] = []
    for file in files:
        print(f"[lenovo_graph] extracting {file}")
        output = extract_file(file, config)
        print(f"[lenovo_graph] wrote {output}")
        outputs.append(output)
    return outputs


def build_submission(output_dir: Path, submission_name: str) -> Path:
    folder_name = f"轻量化模型下的知识图谱构建_100point_{submission_name}"
    submission_root = output_dir.parent / f"submission_{submission_name}"
    submission_dir = submission_root / folder_name
    if submission_dir.exists():
        shutil.rmtree(submission_dir)
    submission_dir.mkdir(parents=True, exist_ok=True)
    for file in sorted(output_dir.glob("*.json"), key=lambda p: int(p.stem) if p.stem.isdigit() else p.stem):
        shutil.copy2(file, submission_dir / file.name)
    zip_path = output_dir.parent / f"{folder_name}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(submission_dir.glob("*.json"), key=lambda p: int(p.stem) if p.stem.isdigit() else p.stem):
            zf.write(file, arcname=f"{folder_name}/{file.name}")
    return zip_path


def build_final_submission(output_dir: Path, time_suffix: str) -> Path:
    """Build the final-round package: submit/submit_<stem>.json."""
    package_name = f"配套_轻量化图谱{time_suffix}_100point"
    submission_root = output_dir.parent / f"submission_{time_suffix}"
    submission_dir = submission_root / "submit"
    if submission_root.exists():
        shutil.rmtree(submission_root)
    submission_dir.mkdir(parents=True, exist_ok=True)
    for file in sorted(output_dir.glob("*.json"), key=lambda p: int(p.stem) if p.stem.isdigit() else p.stem):
        shutil.copy2(file, submission_dir / f"submit_{file.stem}.json")
    zip_path = output_dir.parent / f"{package_name}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(submission_dir.glob("*.json"), key=lambda p: int(p.stem.replace("submit_", "")) if p.stem.replace("submit_", "").isdigit() else p.stem):
            zf.write(file, arcname=f"submit/{file.name}")
    return zip_path
