from __future__ import annotations

import json
import re
from typing import Any, Literal

from .profiles import DocumentProfile


MAX_ATTRIBUTE_VALUE_LENGTH = 120
MAX_ATTRIBUTES_PER_ENTITY = 6
STRICT_ENTITY_BUDGET_PROFILES = {
    "file2_notebook_test_system",
    "file3_notebook_architecture_precision",
    "english_millennium_prize_reference_aligned",
    "english_conspiracy_0609_platform",
    "english_fashion_balanced",
    "english_autonomous_vehicle_balanced",
    "english_coral_reef_0609_platform",
}
RELATION_RECALL_PROFILES = {
    "file6_ssd_engineering_llm_precision",
}

BAD_ENTITY_TYPES = {
    "entitytype",
    "knowledgegraphentitytype",
    "实体类型",
    "知识图谱实体类型",
    "unknown",
    "未知",
}
BAD_RELATION_TYPES = {
    "relationtype",
    "relationshiptype",
    "关系类型",
    "描述",
    "描述为",
    "定义",
    "说明",
    "需要",
    "强调",
    "显示",
    "出现",
    "可能属于",
    "related_to",
    "mentions",
    "describes",
}
COMPOSITE_RELATION_MARKERS = ("/", "／", "|", "或", " or ", " and ")

ZH_RELATION_TYPE_MAP = {
    "包含关系": "包含",
    "层级关系": "包含",
    "影响关系": "影响",
    "依赖关系": "依赖",
    "依赖于": "依赖",
    "连接关系": "连接",
    "连接到": "连接",
    "使用于": "应用于",
    "优化目标": "优化",
    "驱动因素": "驱动",
    "栖息地": "栖息于",
    "由...组成": "包含",
    "由……组成": "包含",
}
ZH_INVERT_TO_CONTAINS = {
    "构成",
    "组成",
    "组成关系",
    "组成单元",
    "组成部分",
    "集成于",
    "集成在",
    "属于",
}
ZH_TYPE_MAP = {
    "product": "产品",
    "hardware_component": "硬件组件",
    "component": "组件",
    "interface": "接口",
    "material": "材料",
    "standard": "标准",
    "process_step": "流程步骤",
    "quality_metric": "质量指标",
    "technology": "技术",
    "concept": "概念",
    "organization": "组织",
    "equipment": "设备",
    "software": "软件",
    "firmware": "固件",
}
EN_RELATION_TYPE_MAP = {
    "is part of": "is_part_of",
    "part of": "is_part_of",
    "belongs to": "is_part_of",
    "originates from": "originates_from",
    "originated from": "originates_from",
    "located in": "located_in",
    "used for": "used_for",
    "applies to": "applies_to",
    "depends on": "depends_on",
    "feeds on": "feeds_on",
    "emerged in": "emerged_in",
    "occurs during": "occurs_during",
}
EN_RELATION_PHRASE_MAP = (
    ("transformed the way", "affects"),
    ("shaped the social fabric", "affects"),
    ("cultivated and traded", "traded_in"),
    ("plays a role in", "affects"),
    ("serves as", "used_for"),
    ("acts as", "used_for"),
    ("helps prevent", "protects"),
    ("helps to prevent", "protects"),
    ("is used to", "used_for"),
    ("is used for", "used_for"),
    ("is an example of", "example_of"),
)
ATTRIBUTE_KEY_PRIORITY = {
    "别名": 0,
    "英文名": 0,
    "英文缩写": 0,
    "缩写": 0,
    "学名": 0,
    "scientific_name": 0,
    "全称": 0,
    "full_name": 0,
    "alias": 0,
    "功能": 1,
    "作用": 1,
    "用途": 1,
    "类型": 1,
    "型号": 1,
    "标准": 1,
    "协议": 1,
    "材料": 1,
    "位置": 1,
    "阈值": 1,
    "参数": 1,
    "关键指标": 1,
}
PART_TYPE_HINTS = ("部件", "组件", "芯片", "模块", "单元", "介质", "材料", "协议", "接口", "算法", "软件", "固件", "控制器")
WHOLE_TYPE_HINTS = ("产品", "设备", "系统", "平台", "终端", "对象", "存储设备")


def parse_json_response(text: str) -> dict[str, Any]:
    text = str(text or "").strip()
    if not text:
        return {"entities": [], "relations": []}
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return salvage_partial_graph_json(text)
        else:
            return salvage_partial_graph_json(text)
    return data if isinstance(data, dict) else {"entities": [], "relations": []}


def salvage_partial_graph_json(text: str) -> dict[str, Any]:
    """Recover complete array items from a truncated LLM JSON response."""
    return {
        "entities": _salvage_array_items(text, "entities"),
        "relations": _salvage_array_items(text, "relations"),
    }


def _salvage_array_items(text: str, key: str) -> list[Any]:
    match = re.search(rf'"{re.escape(key)}"\s*:\s*\[', text)
    if not match:
        return []
    decoder = json.JSONDecoder()
    items: list[Any] = []
    pos = match.end()
    length = len(text)
    while pos < length:
        while pos < length and text[pos] in " \t\r\n,":
            pos += 1
        if pos >= length or text[pos] == "]":
            break
        if text[pos] not in "{[":
            next_object = min(
                [idx for idx in (text.find("{", pos), text.find("[", pos)) if idx >= 0],
                default=-1,
            )
            if next_object < 0:
                break
            pos = next_object
        try:
            item, next_pos = decoder.raw_decode(text, pos)
        except json.JSONDecodeError:
            next_object = min(
                [idx for idx in (text.find("{", pos + 1), text.find("[", pos + 1)) if idx >= 0],
                default=-1,
            )
            if next_object < 0:
                break
            pos = next_object
            continue
        if isinstance(item, (dict, list)):
            items.append(item)
        pos = next_pos
    return items


def compact_label(value: str) -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"[_\-\s]+", " ", value)
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "", value)
    return value


def normalize_name_key(value: str) -> str:
    value = str(value or "").strip().lower()
    value = value.replace("_", " ").replace("-", " ")
    value = re.sub(r"[（）()]", " ", value)
    value = re.sub(r"[^\w\u4e00-\u9fff]+", " ", value)
    tokens = []
    for token in value.split():
        if token.isascii() and token.endswith("s") and len(token) > 3:
            token = token[:-1]
        tokens.append(token)
    return " ".join(tokens)


def normalize_entity_name(value: str, language: str | None) -> str:
    value = str(value or "").strip()
    if language == "en":
        value = re.sub(r"_+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def split_name_aliases(name: str) -> tuple[str, list[str]]:
    name = str(name or "").strip()
    main = re.sub(r"[（(].*?[）)]", "", name).strip()
    aliases = [x.strip() for x in re.findall(r"[（(](.*?)[）)]", name) if x.strip()]
    return main or name, aliases


def alias_is_descriptive(alias: str) -> bool:
    alias = str(alias or "").strip()
    if not alias:
        return False
    if len(alias) > 24:
        return True
    if any(marker in alias for marker in (",", "，", ";", "；")):
        return True
    if len(alias.split()) >= 4:
        return True
    return False


def clean_entity_display_name(name: str, language: str | None) -> str:
    name = normalize_entity_name(name, language)
    main, aliases = split_name_aliases(name)
    if aliases and (len(name) > 48 or any(alias_is_descriptive(alias) for alias in aliases)):
        return normalize_entity_name(main, language)
    return name


def iter_name_aliases(name: str) -> list[str]:
    main, aliases = split_name_aliases(name)
    values = [name]
    if main and main != name:
        values.append(main)
    values.extend(aliases)
    return values


def contains_chinese(text: str) -> bool:
    return any("\u4e00" <= c <= "\u9fff" for c in str(text or ""))


def language_mismatch(value: str, language: str | None) -> bool:
    return language == "en" and contains_chinese(value)


def is_sentence_like_name(name: str, zh: bool) -> bool:
    name = str(name or "").strip()
    if not name or len(name) > 64:
        return True
    if any(marker in name for marker in ("=", "√", "∑", "≈", "≤", "≥")):
        return True
    if zh and any(marker in name for marker in ("，", "。", "；", "、")):
        return True
    if not zh and name.count(",") >= 2:
        return True
    if not zh:
        words = name.split()
        lower_start = bool(name[:1] and name[:1].islower())
        phrase_starts = (
            "building ",
            "creation of ",
            "further ",
            "millions of ",
            "all individuals ",
            "cooking food ",
            "enhance ",
            "growth of ",
        )
        if len(words) >= 5 and lower_start:
            return True
        if any(name.lower().startswith(prefix) for prefix in phrase_starts):
            return True
    noisy = (
        "是否", "低于", "高于", "超过", "小于", "大于", "显著", "明显", "更适合",
        "更倾向", "通常会", "率先进入", "尚未被", "偏好", "创造条件", "功能描述",
    )
    return any(x in name for x in noisy)


def default_entity_type(zh: bool) -> str:
    return "概念" if zh else "concept"


def normalize_entity_type(entity_type: str, name: str, zh: bool, language: str | None) -> str:
    entity_type = str(entity_type or "").strip() or default_entity_type(zh)
    if zh:
        entity_type = ZH_TYPE_MAP.get(entity_type, ZH_TYPE_MAP.get(entity_type.lower(), entity_type))
    if language_mismatch(entity_type, language):
        entity_type = default_entity_type(zh)
    label = compact_label(entity_type)
    if not label or label in BAD_ENTITY_TYPES or label == compact_label(name):
        return default_entity_type(zh)
    return entity_type


def normalize_attributes(attrs: Any, language: str | None, entity_type: str | None = None) -> dict:
    if not isinstance(attrs, dict):
        return {}
    normalized = {}
    entity_type_label = compact_label(entity_type or "")
    for key, value in attrs.items():
        key = str(key).strip()
        if not key or value in (None, "", [], {}):
            continue
        if language_mismatch(key, language) or language_mismatch(str(value), language):
            continue
        if isinstance(value, (str, int, float, bool)):
            normalized_value = str(value).strip() if isinstance(value, str) else value
        else:
            normalized_value = json.dumps(value, ensure_ascii=False)
        key_label = compact_label(key)
        value_label = compact_label(str(normalized_value))
        if key_label in {"type", "类型"} and entity_type_label and value_label == entity_type_label:
            continue
        if key_label in {"type", "类型"} and value_label in {"concept", "概念"}:
            continue
        if isinstance(normalized_value, str) and len(normalized_value) > MAX_ATTRIBUTE_VALUE_LENGTH:
            normalized_value = normalized_value[:MAX_ATTRIBUTE_VALUE_LENGTH].rstrip() + "..."
        normalized[key] = normalized_value
    ranked = sorted(
        normalized.items(),
        key=lambda item: (ATTRIBUTE_KEY_PRIORITY.get(item[0], 10), len(str(item[1])), item[0]),
    )
    return dict(ranked[:MAX_ATTRIBUTES_PER_ENTITY])


def enrich_alias_attribute(name: str, attrs: dict, zh: bool, entity_type: str | None = None) -> dict:
    attrs = dict(attrs)
    _, aliases = split_name_aliases(name)
    if aliases:
        key = "别名" if zh else "alias"
        short_aliases = [alias for alias in aliases if not alias_is_descriptive(alias)]
        if short_aliases:
            attrs.setdefault(key, short_aliases[0])
    return normalize_attributes(attrs, "zh" if zh else "en", entity_type)


def should_keep_relation_type(relation_type: str) -> bool:
    relation_type = str(relation_type or "").strip()
    if any(marker in relation_type for marker in COMPOSITE_RELATION_MARKERS):
        return False
    label = compact_label(relation_type)
    return bool(label) and label not in BAD_RELATION_TYPES and not label.isdigit()


def normalize_relation_type(relation_type: str, zh: bool) -> tuple[str, bool]:
    relation_type = str(relation_type or "").strip()
    if not zh:
        relation_type = re.sub(r"[_\s]+", " ", relation_type).strip()
        relation_key = relation_type.lower()
        if relation_key in EN_RELATION_TYPE_MAP:
            return EN_RELATION_TYPE_MAP[relation_key], False
        for marker, replacement in EN_RELATION_PHRASE_MAP:
            if marker in relation_key:
                return replacement, False
        if len(relation_key.split()) > 4:
            return "", False
        return relation_key.replace(" ", "_"), False
    if relation_type in ZH_INVERT_TO_CONTAINS:
        return "包含", True
    return ZH_RELATION_TYPE_MAP.get(relation_type, relation_type), False


def should_invert_contains_by_type(source_type: str, target_type: str) -> bool:
    source_part = any(hint in str(source_type) for hint in PART_TYPE_HINTS)
    target_whole = any(hint in str(target_type) for hint in WHOLE_TYPE_HINTS)
    return source_part and target_whole


def endpoint_is_atomic(value: str) -> bool:
    value = str(value or "").strip()
    if not value or len(value) > 80:
        return False
    list_markers = ["、", "；", ";", " and ", " or ", "以及", "或者"]
    if any(marker in value for marker in list_markers):
        return False
    clause_markers = ["，", "。", ",", "低于", "高于", "超过", "小于", "大于", "显著", "明显", "由于", "因此"]
    return not any(marker in value for marker in clause_markers)


def normalize_competition_graph(
    chunks: list[dict],
    language: Literal["zh", "en"],
    preserve_source_relation_labels: bool = False,
) -> dict:
    zh = language == "zh"
    entity_map: dict[str, dict] = {}
    canonical: dict[str, str] = {}

    def add_entity(name: str, entity_type: str, attrs: Any = None) -> str | None:
        name = clean_entity_display_name(name, language)
        if not name or language_mismatch(name, language) or is_sentence_like_name(name, zh):
            return None
        key = normalize_name_key(split_name_aliases(name)[0])
        if not key:
            return None
        entity_type = normalize_entity_type(entity_type, name, zh, language)
        attributes = enrich_alias_attribute(name, normalize_attributes(attrs, language, entity_type), zh, entity_type)
        if key not in entity_map:
            entity_map[key] = {"name": name, "type": entity_type, "attributes": attributes}
        else:
            entity_map[key]["attributes"].update(attributes)
            entity_map[key]["attributes"] = normalize_attributes(
                entity_map[key]["attributes"],
                language,
                entity_map[key].get("type", ""),
            )
            if entity_map[key]["type"] == default_entity_type(zh) and entity_type != default_entity_type(zh):
                entity_map[key]["type"] = entity_type
        for alias in iter_name_aliases(entity_map[key]["name"]):
            alias_key = normalize_name_key(alias)
            if alias_key:
                canonical[alias_key] = entity_map[key]["name"]
        return entity_map[key]["name"]

    for chunk in chunks:
        for entity in chunk.get("entities", []) or []:
            if isinstance(entity, dict):
                add_entity(entity.get("name", ""), entity.get("type", ""), entity.get("attributes"))

    name_to_type = {entity["name"]: entity["type"] for entity in entity_map.values()}
    relations: list[list[str]] = []

    for chunk in chunks:
        for raw_relation in chunk.get("relations", []) or []:
            if isinstance(raw_relation, dict):
                source = raw_relation.get("source", "")
                target = raw_relation.get("target", "")
                relation_type = raw_relation.get("type", "")
                strength = raw_relation.get("strength")
                source_type = raw_relation.get("source_type", "")
                target_type = raw_relation.get("target_type", "")
            elif isinstance(raw_relation, list) and len(raw_relation) >= 3:
                source, relation_type, target = raw_relation[:3]
                strength = None
                source_type = ""
                target_type = ""
            else:
                continue
            if isinstance(strength, (int, float)) and strength < 6:
                continue
            source = clean_entity_display_name(source, language)
            target = clean_entity_display_name(target, language)
            if not source or not target or not relation_type:
                continue
            if language_mismatch(source, language) or language_mismatch(target, language) or language_mismatch(str(relation_type), language):
                continue
            if not should_keep_relation_type(str(relation_type)):
                continue
            if preserve_source_relation_labels and not zh:
                relation_type = re.sub(r"\s+", " ", str(relation_type).strip())
                invert = False
            else:
                relation_type, invert = normalize_relation_type(str(relation_type), zh)
            if not should_keep_relation_type(relation_type):
                continue
            source_name = canonical.get(normalize_name_key(source))
            target_name = canonical.get(normalize_name_key(target))
            if not source_name and endpoint_is_atomic(source):
                source_name = add_entity(source, source_type or default_entity_type(zh), {})
            if not target_name and endpoint_is_atomic(target):
                target_name = add_entity(target, target_type or default_entity_type(zh), {})
            if not source_name or not target_name or source_name == target_name:
                continue
            if invert or (zh and relation_type == "包含" and should_invert_contains_by_type(name_to_type.get(source_name, ""), name_to_type.get(target_name, ""))):
                source_name, target_name = target_name, source_name
            row = [source_name, relation_type, target_name]
            reverse = [target_name, relation_type, source_name]
            if row not in relations and reverse not in relations:
                relations.append(row)

    entities = list(entity_map.values())
    return {"entities": entities, "relations": relations}


def inventory_for_prompt(graph: dict, limit: int = 220) -> list[dict]:
    entities = graph.get("entities", []) or []
    compact: list[dict] = []
    for entity in entities[:limit]:
        if not isinstance(entity, dict):
            continue
        compact.append(
            {
                "name": entity.get("name", ""),
                "type": entity.get("type", ""),
            }
        )
    return compact


def merge_attribute_updates(
    graph: dict,
    attribute_chunks: list[dict],
    language: Literal["zh", "en"],
) -> dict:
    zh = language == "zh"
    canonical = {}
    for entity in graph.get("entities", []) or []:
        if not isinstance(entity, dict):
            continue
        for alias in iter_name_aliases(entity.get("name", "")):
            key = normalize_name_key(alias)
            if key:
                canonical[key] = entity.get("name", "")

    by_name = {
        entity.get("name", ""): entity
        for entity in graph.get("entities", []) or []
        if isinstance(entity, dict)
    }
    for chunk in attribute_chunks:
        for item in chunk.get("entities", []) or []:
            if not isinstance(item, dict):
                continue
            name = normalize_entity_name(item.get("name", ""), language)
            canonical_name = canonical.get(normalize_name_key(name))
            if not canonical_name or canonical_name not in by_name:
                continue
            attrs = normalize_attributes(
                item.get("attributes", {}),
                language,
                by_name[canonical_name].get("type", ""),
            )
            if not attrs:
                continue
            existing = by_name[canonical_name].get("attributes") or {}
            existing.update(attrs)
            by_name[canonical_name]["attributes"] = enrich_alias_attribute(
                canonical_name,
                normalize_attributes(existing, language, by_name[canonical_name].get("type", "")),
                zh,
                by_name[canonical_name].get("type", ""),
            )

    return {
        "entities": list(by_name.values()),
        "relations": graph.get("relations", []) or [],
    }


def enrich_attributes_from_source(
    graph: dict,
    text: str,
    language: Literal["zh", "en"],
) -> dict:
    """Add high-precision aliases/acronyms/scientific names directly visible in source text."""
    entities = []
    for entity in graph.get("entities", []) or []:
        if not isinstance(entity, dict):
            continue
        entity = dict(entity)
        entity_type = entity.get("type", "")
        attrs = dict(entity.get("attributes") or {})
        attrs.update(_source_attributes_for_entity(entity.get("name", ""), entity_type, text, language))
        entity["attributes"] = enrich_alias_attribute(
            entity.get("name", ""),
            normalize_attributes(attrs, language, entity_type),
            language == "zh",
            entity_type,
        )
        entities.append(entity)
    return {"entities": entities, "relations": graph.get("relations", []) or []}


def _source_attributes_for_entity(name: str, entity_type: str, text: str, language: Literal["zh", "en"]) -> dict:
    name = normalize_entity_name(name, language)
    if not name or len(name) > 80:
        return {}
    candidates = _parenthetical_candidates(name, text)
    if not candidates:
        return {}
    attrs: dict[str, str] = {}
    for value in candidates:
        value = value.strip().strip("\"'“”")
        if not _safe_source_attribute(value):
            continue
        if language == "zh":
            key = _zh_source_attr_key(value, entity_type)
        else:
            key = _en_source_attr_key(value)
        attrs.setdefault(key, value)
        if len(attrs) >= 2:
            break
    return attrs


def _parenthetical_candidates(name: str, text: str) -> list[str]:
    escaped = re.escape(name)
    boundary = r"[\w\u4e00-\u9fff]"
    candidates = []
    patterns = (
        rf"(?<!{boundary}){escaped}(?!{boundary})\s*[（(]\s*([^（）()]+?)\s*[）)]",
        rf"[（(]\s*([^（）()]+?)\s*[）)]\s*(?<!{boundary}){escaped}(?!{boundary})",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            candidates.append(match.group(1))
    return candidates


def _safe_source_attribute(value: str) -> bool:
    if not value or len(value) > 48:
        return False
    if len(value) == 1:
        return False
    if any(marker in value for marker in ("。", "；", ";", "，", "、", ",", "≈", "╯", "□", "°", "如")):
        return False
    if re.search(r"\d+\s*(?:%|℃|mm|GB|TB|ms|小时|天)", value, re.I):
        return False
    return True


def _looks_like_latin_binomial(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z][a-z]+(?:\s+[a-z]+){1,2}", value))


def _looks_like_acronym(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+/\-]{1,14}", value)) and any(c.isupper() for c in value)


def _zh_source_attr_key(value: str, entity_type: str) -> str:
    bio_type = any(hint in str(entity_type) for hint in ("物种", "捕食者", "生物"))
    if bio_type and _looks_like_latin_binomial(value):
        return "学名"
    if _looks_like_acronym(value):
        return "别名"
    if re.search(r"[A-Za-z]", value):
        return "全称" if len(value.split()) >= 2 else "别名"
    return "别名"


def _en_source_attr_key(value: str) -> str:
    if _looks_like_latin_binomial(value):
        return "scientific_name"
    return "alias" if _looks_like_acronym(value) else "full_name"


def apply_profile_filters(
    graph: dict,
    profile: DocumentProfile,
    language: Literal["zh", "en"],
) -> dict:
    """Remove only profile-confirmed hard noise; avoid broad truncation that hurts recall."""
    deny_terms = tuple(term for term in profile.postprocess_deny_terms if term)

    removed_names: set[str] = set()
    kept_entities: list[dict] = []
    for entity in graph.get("entities", []) or []:
        if not isinstance(entity, dict):
            continue
        name = normalize_entity_name(entity.get("name", ""), language)
        entity_type = str(entity.get("type", "") or "")
        if any(term in name or term in entity_type for term in deny_terms):
            removed_names.add(entity.get("name", ""))
            removed_names.add(name)
            continue
        kept_entities.append(entity)

    kept_relations: list[list[str]] = []
    for relation in graph.get("relations", []) or []:
        if not isinstance(relation, list) or len(relation) < 3:
            continue
        source, _, target = relation[:3]
        relation_type = str(relation[1] or "").strip()
        if not should_keep_relation_type(relation_type):
            continue
        if source in removed_names or target in removed_names:
            continue
        kept_relations.append(relation[:3])

    return calibrate_profile_budget({"entities": kept_entities, "relations": kept_relations}, profile, language)


def _parse_upper_bound(target: str) -> int | None:
    numbers = [int(value) for value in re.findall(r"\d+", str(target or ""))]
    return max(numbers) if numbers else None


def _parse_lower_bound(target: str) -> int | None:
    numbers = [int(value) for value in re.findall(r"\d+", str(target or ""))]
    return min(numbers) if numbers else None


def calibrate_profile_budget(
    graph: dict,
    profile: DocumentProfile,
    language: Literal["zh", "en"],
) -> dict:
    """Trim obvious over-generation with relation-degree priority, not a blind hard cutoff."""
    upper = _parse_upper_bound(profile.target_entities)
    entities = [e for e in graph.get("entities", []) or [] if isinstance(e, dict)]
    relations = [r[:3] for r in graph.get("relations", []) or [] if isinstance(r, list) and len(r) >= 3]
    if not upper:
        return _calibrate_relation_budget({"entities": entities, "relations": relations}, profile, language)
    entity_tolerance = 1.05 if profile.name in STRICT_ENTITY_BUDGET_PROFILES else 1.25
    # Leave normal variance alone. This only handles files where the model ignored the profile scale.
    if len(entities) <= int(upper * entity_tolerance):
        return _calibrate_relation_budget({"entities": entities, "relations": relations}, profile, language)

    degree: dict[str, int] = {}
    for source, _, target in relations:
        degree[source] = degree.get(source, 0) + 1
        degree[target] = degree.get(target, 0) + 1

    zh = language == "zh"
    default_type = default_entity_type(zh)
    target_count = max(upper, int(upper * 1.08))

    def score(entity: dict) -> tuple[int, int, int, int]:
        name = entity.get("name", "")
        attrs = entity.get("attributes") or {}
        entity_type = entity.get("type", "")
        relation_score = degree.get(name, 0) * 8
        attr_score = min(len(attrs), 3) * 4
        type_score = 2 if entity_type and entity_type != default_type else 0
        name_penalty = -4 if len(str(name)) > 48 else 0
        isolate_penalty = -8 if degree.get(name, 0) == 0 and not attrs else 0
        return (relation_score + attr_score + type_score + name_penalty + isolate_penalty, degree.get(name, 0), len(attrs), -len(str(name)))

    ranked = sorted(entities, key=score, reverse=True)
    keep_names = {entity.get("name", "") for entity in ranked[:target_count]}
    relation_lower = _parse_lower_bound(profile.target_relations)
    if relation_lower:
        relation_rank = sorted(
            relations,
            key=lambda row: (
                score(next((e for e in entities if e.get("name", "") == row[0]), {}))[0]
                + score(next((e for e in entities if e.get("name", "") == row[2]), {}))[0],
                degree.get(row[0], 0) + degree.get(row[2], 0),
            ),
            reverse=True,
        )
        for source, _, target in relation_rank:
            current_relations = sum(1 for row in relations if row[0] in keep_names and row[2] in keep_names)
            if current_relations >= relation_lower:
                break
            keep_names.add(source)
            keep_names.add(target)
    kept_entities = [entity for entity in entities if entity.get("name", "") in keep_names]
    kept_relations = [
        relation
        for relation in relations
        if relation[0] in keep_names and relation[2] in keep_names
    ]
    return _calibrate_relation_budget({"entities": kept_entities, "relations": kept_relations}, profile, language)


def _calibrate_relation_budget(
    graph: dict,
    profile: DocumentProfile,
    language: Literal["zh", "en"],
) -> dict:
    relation_upper = _parse_upper_bound(profile.target_relations)
    entities = [e for e in graph.get("entities", []) or [] if isinstance(e, dict)]
    relations = [r[:3] for r in graph.get("relations", []) or [] if isinstance(r, list) and len(r) >= 3]
    if profile.name in RELATION_RECALL_PROFILES:
        return {"entities": entities, "relations": relations}
    if not relation_upper or len(relations) <= int(relation_upper * 1.12):
        return {"entities": entities, "relations": relations}

    entity_by_name = {str(entity.get("name", "")): entity for entity in entities}
    degree: dict[str, int] = {}
    for source, _, target in relations:
        degree[source] = degree.get(source, 0) + 1
        degree[target] = degree.get(target, 0) + 1

    preferred_labels = {compact_label(label) for label in profile.preferred_relation_labels}
    preferred_types = {compact_label(value) for value in profile.preferred_entity_types}
    zh = language == "zh"

    def endpoint_score(name: str) -> int:
        entity = entity_by_name.get(name, {})
        attrs = entity.get("attributes") or {}
        entity_type = str(entity.get("type", ""))
        score = min(degree.get(name, 0), 6) * 3
        score += min(len(attrs), 3) * 2
        if compact_label(entity_type) in preferred_types:
            score += 3
        if len(str(name)) <= (18 if zh else 32):
            score += 2
        if is_sentence_like_name(str(name), zh):
            score -= 12
        return score

    def relation_score(row: list[str], index: int) -> tuple[int, int]:
        source, label, target = row
        label_text = str(label).strip()
        compact = compact_label(label_text)
        score = endpoint_score(source) + endpoint_score(target)
        if compact in preferred_labels:
            score += 22
        elif any(compact == item or compact in item or item in compact for item in preferred_labels):
            score += 10
        if should_keep_relation_type(label_text):
            score += 4
        if any(marker in label_text for marker in COMPOSITE_RELATION_MARKERS):
            score -= 12
        if len(label_text) <= (5 if zh else 18):
            score += 4
        elif len(label_text) > (12 if zh else 32):
            score -= 8
        if source == target:
            score -= 100
        return (score, -index)

    ranked = sorted(enumerate(relations), key=lambda item: relation_score(item[1], item[0]), reverse=True)
    keep_indices = {index for index, _ in ranked[:relation_upper]}
    kept_relations = [relation for index, relation in enumerate(relations) if index in keep_indices]
    return {"entities": entities, "relations": kept_relations}
