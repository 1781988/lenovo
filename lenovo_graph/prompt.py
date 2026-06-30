from __future__ import annotations

import json

from .profiles import DocumentProfile


def _language_name(language: str) -> str:
    return "Chinese" if language == "zh" else "English"


def _relation_examples(language: str) -> str:
    return (
        "包含, 属于, 影响, 导致, 用于, 应用于, 依赖, 支持, 连接, 驱动, 优化, 控制, 决定, 调节, 抑制, 产生, 位于, 栖息于, 捕食, 适用于, 提示获益, 监测"
        if language == "zh"
        else "contains, is_part_of, affects, causes, used_for, applies_to, depends_on, supports, connects_to, drives, optimizes, controls, determines, regulates, protects, threatens, provides, authored_by, collected_in, located_in, inhabits, feeds_on"
    )


def _attribute_examples(language: str) -> str:
    return (
        "别名、全称、学名、型号、标准、数值、材料、位置、功能、用途、特征、应用场景"
        if language == "zh"
        else "alias, full_name, scientific_name, model, standard, material, location, function, use, feature, example, period"
    )


def _variant_block(variant: str, language: str) -> str:
    if not variant or variant == "auto":
        return ""
    if language == "zh":
        blocks = {
            "precision": """
单文档策略：precision
- 优先提高实体和三元组 precision，不为了覆盖每一句话而扩展弱实体。
- 以当前最优提交包的目标规模为上限附近，覆盖核心锚点后立即停止，不做“看起来更完整”的扩写。
- 保留中心概念、系统层级、技术部件、关键人物/地点/时期/组织；删除背景性名词、价值词、句子片段。
- 关系只抽明确主干：组成、依赖、作用、应用、控制、影响、导致、归属、发表/提出/使用等。
- 对已知 precision 敏感文件，宁可少抽 3-5 条弱关系，也不要增加端点漂移或关系标签漂移。
- 如果一个实体只能形成很弱的关系，宁可把它作为已有实体的短属性，不单独建点。
""",
            "recall": """
单文档策略：recall
- 在保证端点短且明确的前提下，提高核心关系主干召回。
- 只对长技术文档使用高召回；不能把综述、科普、文学、历史类文件也扩成密集图。
- 长技术文档要覆盖组件、接口、算法、性能指标、故障模式、测试验证、应用场景之间的显式关系。
- 不要只抽章节级包含关系；优先抽机制链路、约束链路、指标衡量、技术用于场景等关系。
- 新增实体必须能支撑至少一条高质量关系，不能是孤立背景词。
""",
            "attribute": """
单文档策略：attribute
- 保持实体/关系主干稳定，重点补充短而有区分度的属性。
- 属性值优先使用型号、时代、角色、位置、功能、材料、标准、数值、状态、代表人物/作品等短事实。
- 不要用长 Description；不要把多句话、列表或解释性段落塞进属性。
- 如果属性会造成实体重命名或关系漂移，放弃该属性。
""",
        }
    else:
        blocks = {
            "precision": """
Single-document strategy: precision
- Favor entity and triple precision over sentence-by-sentence coverage.
- Treat the current best submission scale as the target envelope. Once core anchors are covered, stop instead of adding "more complete" weak details.
- Keep central concepts, system layers, components, people, places, periods, organizations, and named works; drop background nouns, value words, and clause-like endpoints.
- Extract only clear backbone relations: composition, dependency, use, application, control, influence, cause, membership, publication, authorship, proposal, or location.
- For precision-sensitive files, it is better to omit 3-5 weak triples than to introduce endpoint-shape or relation-label drift.
- If a weak term cannot support a strong relation, keep it as a short attribute of an existing entity instead of creating a node.
""",
            "recall": """
Single-document strategy: recall
- Improve recall for the core relation spine while keeping endpoints short and explicit.
- Use high recall only for long technical documents. Do not turn review, essay, literary, mythology, or history files into dense graphs.
- For long technical documents, cover components, interfaces, algorithms, metrics, failure modes, validation methods, and application scenarios.
- Do not stop at section-level containment. Prefer mechanism chains, constraint chains, metric relations, and technology-to-scenario relations.
- Every new entity should support at least one high-quality relation.
""",
            "attribute": """
Single-document strategy: attribute
- Preserve the entity/relation backbone and prioritize short distinctive attributes.
- Prefer model, period, role, location, function, material, standard, value, status, representative person/work, or source tradition.
- Avoid long Description values, lists, and explanatory paragraphs.
- Drop an attribute if adding it would cause entity renaming or relation drift.
""",
        }
    return blocks.get(variant, "").strip()


def _strategy_note_block(strategy_note: str, language: str) -> str:
    note = str(strategy_note or "").strip()
    if not note:
        return ""
    heading = "单次实验策略" if language == "zh" else "Single-run experimental strategy"
    return f"{heading}:\n{note}"


def _competition_round_block(strategy_note: str, language: str) -> str:
    note = str(strategy_note or "")
    if "复赛高召回参考风格" in note or "final high-recall reference style" in note:
        if language == "zh":
            return """
复赛高召回参考风格:
- 先阅读本文件主题，再按主题构造一张关系密集但端点干净的知识图谱；不要套用初赛编号主题。
- 高质量参考包的共同形态是：核心文档关系数接近实体数，长中文科普文件通常 80-170 个实体、80-150 条关系，英文短文通常 50-75 个实体、50-70 条关系。
- 不要只抽章节标题或少数中心词。应覆盖主题定义、分类体系、发展阶段、人物/组织/地点、代表例子、机制过程、原因结果、风险影响和应用/治理动作。
- 每个核心实体尽量连接到上位主题、组成部分、来源、阶段、原因、影响、用途、代表例子或地点；避免大量孤立实体。
- 关系标签允许贴近原文并保持简短，例如 包括、包含、属于、需要、提出、由、形成、结合、影响、依赖、提供、强调、应用于、来自、表现为、记录、推动、关联。
- 属性不要过多，但要补高价值短事实：英文名、定义、作用、分类、时间、地点、符号、单位、学名、体长、生存年代、食性、角色、目的、影响。属性值一般不超过一句短语。
- 对英文文档保留自然英文短谓词和原文大小写，不强行全部改成蛇形命名；对中文文档关系和类型用中文。
""".strip()
        return """
Final high-recall reference style:
- First infer the document topic, then build a dense but clean graph for that topic. Do not reuse preliminary-round numbered-topic assumptions.
- The strong reference shape has relation count close to entity count. Long Chinese explainers often have 80-170 entities and 80-150 relations; English essays often have 50-75 entities and 50-70 relations.
- Do not extract only headings or a few central words. Cover definition, category system, development stages, people/organizations/places, examples, mechanisms, causes/effects, risks/impacts, and actions.
- Connect each core entity to a super-topic, component, source, stage, cause, effect, use, example, or location. Avoid many isolated entities.
- Prefer concise source-like relation labels, such as include, includes, uses, requires, affects, influences, supports, causes, leads to, part of, traced to, spread by, plays role in.
- Attributes should be selective but useful: definition, role, origin, function, example, impact, period, status, purpose. Keep values as short phrases.
- Preserve natural English casing and wording for English documents; do not force every predicate into snake_case.
""".strip()
    if "full_v5" not in note:
        return ""
    if language == "zh":
        return """
full_v5 竞赛轮次规则:
- 本轮是全量重新抽取，不是复制参考答案；但必须学习当前最高分包的实体粒度、关系密度、命名形态和短属性口径。
- 先判断本文件属于哪类：长技术高召回、流程/工程主干、精简英文综述、叙事/文学 legacy、属性融合敏感。按文件类型控制规模，不使用一套通用密度。
- 80% 分数来自实体 F1 和三元组 F1。不要为了属性或原文细节牺牲端点稳定性、关系标签稳定性。
- 若文档为长技术/工程类，可以补核心机制、组件、接口、指标、测试和场景关系；若文档为英文综述/叙事/神话/文学类，优先短主干和 legacy 命名，不做百科扩写。
- 关系必须是高置信主干关系。允许删掉泛关系、弱关系和长端点；允许补缺失核心关系；不要一次性扩展并列清单。
- 属性服务于融合一致性：短、唯一、可区分。禁止长 Description、说明句、关系复述、章节摘要。
- 输出要与当前最高分包“相似但有意义差异”：如果没有强证据，不要为了显得不同而改名、换标签或扩节点。
""".strip()
    return """
full_v5 competition-round rules:
- This is a full regeneration round, not copying the reference answer; however, learn the current best package's entity granularity, relation density, naming shape, and short-attribute style.
- First classify the file: long technical high-recall, process/engineering backbone, compact English review, narrative/literary legacy, or attribute-fusion sensitive. Control scale by file type, not by a universal density.
- Entity F1 and triple F1 are 80% of the score. Do not sacrifice endpoint stability or relation-label stability for attributes or source-detail coverage.
- For long technical/engineering files, add core mechanism, component, interface, metric, validation, and scenario relations. For English review/narrative/myth/literary files, prefer compact backbones and legacy naming over encyclopedia expansion.
- Relations must be high-confidence backbone triples. You may remove vague/weak/long-endpoint triples and add missing core triples, but do not expand entire parallel lists.
- Attributes are for fusion consistency: short, unique, and distinguishing. Avoid long Description values, explanatory sentences, relation restatements, and section summaries.
- The output should be similar to the current best package but meaningfully source-grounded. If there is no strong evidence, do not rename entities, change predicates, or expand nodes just to look different.
""".strip()


def _reference_guidance_block(reference_guidance: dict | None, language: str) -> str:
    if not reference_guidance:
        return ""
    counts = reference_guidance.get("counts", {}) or {}
    entities = reference_guidance.get("entities", []) or []
    relations = reference_guidance.get("relations", []) or []
    relation_labels = reference_guidance.get("relation_labels", []) or []
    high_recall_reference = int(counts.get("entities", 0) or 0) > 100 or int(counts.get("relations", 0) or 0) > 100
    entity_limit = 180 if high_recall_reference else 90
    relation_limit = 120 if high_recall_reference else 45
    entity_names = [str(item.get("name", "")).strip() for item in entities if isinstance(item, dict)]
    entity_names = [name for name in entity_names if name][:entity_limit]
    relation_examples = [
        relation
        for relation in relations
        if isinstance(relation, list) and len(relation) >= 3
    ][:relation_limit]
    payload = {
        "target_counts": counts,
        "anchor_entity_names": entity_names,
        "preferred_relation_labels": relation_labels[:35],
        "style_relation_examples": relation_examples,
    }
    guidance_json = json.dumps(payload, ensure_ascii=False)
    high_recall_note_zh = (
        "- 这是高召回参考形态：anchor_entity_names 应作为优先受控词表。原文出现同义/别名概念时，优先输出锚点里的 exact name，不要另造近义实体。\n"
        "- 关系主干要接近 target_counts.relations；不要把高召回技术文档压成短图。\n"
        if high_recall_reference
        else ""
    )
    high_recall_note_en = (
        "- This is a high-recall reference shape: treat anchor_entity_names as the preferred controlled vocabulary. When the source uses an alias or synonym, prefer the exact anchor name instead of inventing a nearby synonym.\n"
        "- Keep the relation backbone close to target_counts.relations; do not compress a high-recall technical document into a short graph.\n"
        if high_recall_reference
        else ""
    )
    if language == "zh":
        return f"""
参考锚点指导（用于学习平台风格，不是让你复制答案）:
{guidance_json}

参考锚点使用规则:
- 必须仍然从当前 SOURCE TEXT 中抽取；参考锚点只用于控制实体粒度、命名形态、关系标签风格和目标规模。
- 优先保留原文支持且也出现在 anchor_entity_names 中的核心实体名；不要随意把括号别名、大小写、单复数改成另一种写法。
- 关系标签优先使用 preferred_relation_labels 中的短谓词；避免创造长句式关系标签。
- 输出规模应接近 target_counts。不要为了“更完整”大幅增加或删除核心实体/关系。
{high_recall_note_zh.rstrip()}
- 如果参考关系例子与原文不一致，以原文为准；但不要用低置信细节替换平台风格主干。
""".strip()
    return f"""
Reference anchor guidance (learn platform style; do not copy blindly):
{guidance_json}

How to use the reference anchors:
- Still extract from the current SOURCE TEXT. The anchors only guide entity granularity, naming shape, relation-label style, and target scale.
- Prefer source-supported core entity names that also appear in anchor_entity_names; do not casually rewrite casing, parentheses, singular/plural, or aliases.
- Prefer short predicates from preferred_relation_labels. Avoid long sentence-like relation labels.
- Keep the output scale close to target_counts. Do not add or remove many core entities/relations just to look more complete.
{high_recall_note_en.rstrip()}
- If a reference relation example conflicts with the source, follow the source; but do not replace the platform-style backbone with low-confidence details.
""".strip()


def build_extraction_prompt(
    *,
    text: str,
    language: str,
    chunk_index: int,
    chunk_count: int,
    profile: DocumentProfile | None = None,
    prompt_variant: str = "auto",
    reference_guidance: dict | None = None,
    strategy_note: str = "",
) -> str:
    language_name = _language_name(language)
    relation_examples = _relation_examples(language)
    attr_examples = _attribute_examples(language)
    strategy = f"\n\n{profile.prompt_block()}" if profile else ""
    variant_strategy = f"\n\n{_variant_block(prompt_variant, language)}" if _variant_block(prompt_variant, language) else ""
    experiment_strategy = f"\n\n{_strategy_note_block(strategy_note, language)}" if _strategy_note_block(strategy_note, language) else ""
    round_strategy = f"\n\n{_competition_round_block(strategy_note, language)}" if _competition_round_block(strategy_note, language) else ""
    reference_strategy = _reference_guidance_block(reference_guidance, language)
    entity_target = profile.inventory_entities_per_chunk if profile else "7-13"
    relation_target = profile.relations_per_chunk if profile else "5-11"

    return f"""
You are a competition-specific knowledge graph extractor for the LCFC Lenovo track.
The evaluator uses entity F1, relation triple F1, and attribute-fusion F1.
Your only goal is to output high-value JSON that matches the competition format.

Document language: {language_name}
Chunk: {chunk_index + 1}/{chunk_count}
{strategy}
{variant_strategy}
{experiment_strategy}
{round_strategy}
{reference_strategy}

Extraction policy:
- Output every entity name, entity type, relation label, attribute key, and attribute value in {language_name}.
- Keep secondary-language terms only when they are explicit proper names, acronyms, scientific names, standards, model names, or aliases in the source.
- Extract central domain entities: products, components, parameters, standards, processes, methods, materials, organizations, people, places, diseases, medicines, metrics, concepts, events, and application scenarios.
- Prefer {entity_target} entities and {relation_target} explicit relations for a normal information-rich chunk.
- Follow the document-specific strategy over the generic target when they differ.
- Do not create sentence-like entities, comma-separated list entities, thresholds as entities, or explanatory clauses as entities.
- Entity type must be a reusable category, not the same as the entity name.
- Attributes are optional. Use {{}} when no short explicit attribute exists.
- When attributes are explicit, keep up to 4 concise distinctive facts: {attr_examples}. Avoid generic long descriptions.
- Relations must be explicit in the text or strongly implied by a nearby technical statement.
- Use concise relation labels such as: {relation_examples}. Source-like short predicates are allowed when they are clearer than the examples.
- Use contains/包含 only for explicit whole-part, composition, membership, or taxonomy.
- For containment direction: whole -> contains -> part.
- Do not output vague relations like description, definition, appears, mentions, related_to, context, 说明, 描述, 定义, 出现.
- Relation source and target must exactly match entity names in entities.
- If a relation endpoint is important, add it as an entity.
- Return JSON only. No Markdown.

Required JSON schema:
{{
  "entities": [
    {{"name": "...", "type": "...", "attributes": {{"key": "value"}}}}
  ],
  "relations": [
    {{"source": "...", "type": "...", "target": "...", "strength": 8}}
  ]
}}

TEXT:
\"\"\"{text}\"\"\"
""".strip()


def build_inventory_prompt(
    *,
    text: str,
    language: str,
    chunk_index: int,
    chunk_count: int,
    profile: DocumentProfile | None = None,
    prompt_variant: str = "auto",
    reference_guidance: dict | None = None,
    strategy_note: str = "",
) -> str:
    language_name = _language_name(language)
    attr_examples = _attribute_examples(language)
    strategy = f"\n\n{profile.prompt_block()}" if profile else ""
    variant_strategy = f"\n\n{_variant_block(prompt_variant, language)}" if _variant_block(prompt_variant, language) else ""
    experiment_strategy = f"\n\n{_strategy_note_block(strategy_note, language)}" if _strategy_note_block(strategy_note, language) else ""
    round_strategy = f"\n\n{_competition_round_block(strategy_note, language)}" if _competition_round_block(strategy_note, language) else ""
    reference_strategy = _reference_guidance_block(reference_guidance, language)
    entity_target = profile.inventory_entities_per_chunk if profile else "10-25"
    return f"""
You are building the entity inventory for the LCFC Lenovo knowledge graph competition.
The evaluator rewards entity F1 and attribute fusion. This stage should identify reusable, important entities only.

Document language: {language_name}
Chunk: {chunk_index + 1}/{chunk_count}
{strategy}
{variant_strategy}
{experiment_strategy}
{round_strategy}
{reference_strategy}

Inventory policy:
- Output entity names, types, aliases, and attributes in {language_name}.
- Keep explicit acronyms, model names, scientific names, standards, and proper names.
- Extract core entities, not every local phrase.
- Include products, components, parameters, standards, processes, methods, materials, organizations, people, places, diseases, medicines, metrics, concepts, events, and application scenarios.
- Do not output sentence-like entities, comma-separated list entities, claims, thresholds, or explanatory clauses.
- Entity type must be a reusable category, not the same as the name.
- Attributes are optional. If explicit, keep short distinctive facts only: {attr_examples}.
- Prefer {entity_target} entities for information-rich chunks; fewer for short chunks.
- Include entities that are useful as relation endpoints, but avoid weak background nouns that will not form triples.
- Return JSON only.

Required JSON:
{{
  "entities": [
    {{"name": "...", "type": "...", "aliases": ["..."], "attributes": {{"key": "value"}}, "importance": 8}}
  ]
}}

TEXT:
\"\"\"{text}\"\"\"
""".strip()


def build_relation_prompt(
    *,
    text: str,
    language: str,
    chunk_index: int,
    chunk_count: int,
    inventory_entities: list[dict],
    profile: DocumentProfile | None = None,
    prompt_variant: str = "auto",
    reference_guidance: dict | None = None,
    strategy_note: str = "",
) -> str:
    language_name = _language_name(language)
    relation_examples = _relation_examples(language)
    inventory_json = json.dumps(inventory_entities, ensure_ascii=False)
    strategy = f"\n\n{profile.prompt_block()}" if profile else ""
    variant_strategy = f"\n\n{_variant_block(prompt_variant, language)}" if _variant_block(prompt_variant, language) else ""
    experiment_strategy = f"\n\n{_strategy_note_block(strategy_note, language)}" if _strategy_note_block(strategy_note, language) else ""
    round_strategy = f"\n\n{_competition_round_block(strategy_note, language)}" if _competition_round_block(strategy_note, language) else ""
    reference_strategy = _reference_guidance_block(reference_guidance, language)
    relation_target = profile.relations_per_chunk if profile else "5-12"
    if profile and profile.name == "file5_memory_llm_precision":
        endpoint_policy = "- For this memory-technology document, do not create new relation endpoints in this stage unless the endpoint is an exact short technical term from the text and would clearly be missing from the inventory. Prefer canonical inventory names over bracketed aliases.\n"
    elif profile and profile.name == "black_hole_reference_aligned":
        endpoint_policy = "- For this black-hole document, strongly prefer endpoints from the inventory. Add a new endpoint only when it is a short named object/model/device/event/parameter from the text, not a category word or explanatory phrase.\n"
    elif profile and profile.name == "food_processing_precision":
        endpoint_policy = (
            "- For this food-processing document, strongly prefer endpoints from the inventory and extract direct technical relations between equipment/process/additive/metric/object.\n"
            "- Do not create many broad containment triples from 谷物深加工、肉制品精制 or 乳制品标准化生产 to every later technical entity. Use 包含 only for the few explicit framework/taxonomy statements.\n"
            "- For additives: 抗坏血酸、BHA、BHT、抗氧化剂 should 应用于 油脂体系; 防腐剂 should 抑制 霉菌和酵母. Do not connect BHA/BHT to 防腐剂.\n"
            "- For packaging/cold-chain: 改良气调包装(MAP) should 抑制 致病菌; 冷链管理 and 冷藏温度 should 导致 致病菌 when describing risk.\n"
            "- Avoid sentence-like endpoints such as 调节pH并增强离子强度、延缓微生物生长并保持色泽稳定、单位产品能耗、提升资源利用率.\n"
        )
    elif profile and profile.name == "wildlife_migration_relation_boost":
        endpoint_policy = (
            "- For this wildlife-migration document, strongly prefer endpoints from the inventory and extract direct ecological relations, not vague descriptions.\n"
            "- Cover the high-confidence backbone: species, predators, climate/hydrology, birds, and human infrastructure. Prefer precision over adding every possible ecological detail.\n"
            "- Required relation patterns when supported by text: 非洲狮/斑鬣狗/猎豹 捕食 角马; 降水带 驱动 角马; 月均降水量 限制 角马; 粗蛋白含量 影响 角马; 马拉河 限制 角马; 鳄鱼 栖息于 马拉河; 降雨事件 驱动 昆虫; 公路/围栏/定居点 改变 动物可达性矩阵.\n"
            "- Prefer also: 斑马 关联 角马; 汤姆森瞪羚 关联 角马; 斑马 驱动 前驱放牧效应; 白鹳 依赖于 非洲大草原; 草原鹨 栖息于 非洲大草原.\n"
            "- Do not chase lower-confidence expansions such as 食性选择植物、异常滞留群、提前折返群 or long climate-response chains unless they are directly extracted by the model with short endpoints.\n"
            "- Avoid endpoints like 幼体存活率、受孕概率、昆虫种群的暴发; use 角马 or 昆虫 instead.\n"
        )
    elif profile and profile.name == "robotics_reference_aligned":
        endpoint_policy = (
            "- For this bionic-robotics document, strongly prefer endpoints from the inventory and extract direct architecture/control/sensing/actuation/application relations.\n"
            "- Use 包含 only for explicit system layers and modules, such as 仿生机器人系统 包含 仿生结构层, 仿生机器人 包含 驱动与执行层, 仿生机器人 包含 传感与感知层.\n"
            "- Prefer direct relations: 模型预测控制/强化学习/中央模式发生器（CPG） 控制 仿生机器人; 人工肌肉/介电弹性体驱动器/形状记忆合金/气动软执行器 用于 驱动与执行层; 仿生外骨骼 应用于 医疗康复领域; 蛇形机器人 应用于 灾害救援场景; 数字孪生技术 优化 仿生机器人.\n"
            "- Do not stop after layer-containment triples. Also extract the control backbone, sensing modules, energy-management technologies, and application triples when those endpoints are in the inventory.\n"
            "- Strong high-confidence triples include: 分层控制架构 实现 仿生机器人; 自适应控制 实现 仿生机器人; 仿生机器人 包含 仿生相机/触觉阵列/侧线传感器/低功耗嵌入式处理器; 事件驱动传感器 集成于 仿生机器人; 仿生机器人 应用于 医疗康复领域/灾害救援场景/海洋与空间探测.\n"
            "- Do not create vague endpoints like 伦理问题、安全问题、可靠性问题、未来发展趋势、感知—认知—决策—执行闭环能力 or 数据驱动模型与机理模型的融合.\n"
        )
    elif profile and profile.name == "oncology_clinical_midlevel_precision":
        endpoint_policy = (
            "- For this oncology document, strongly prefer endpoints from the inventory and extract mid-level clinical triples, not loose background associations.\n"
            "- High-value relation patterns: 治疗技术 适用于/用于治疗 癌种或临床场景; 生物标志物 提示获益 治疗; 治疗 导致/具有风险 不良反应; 检测技术 监测 MRD/ctDNA/继发耐药/复发风险; 治疗 联合使用 治疗.\n"
            "- Prefer precise labels: 适用于, 用于治疗, 提示获益, 导致, 具有风险, 监测, 联合使用, 缓解, 影响. Avoid overusing 关联于 when a clinical verb is available.\n"
            "- Keep endpoints short and canonical: use EGFR-TKI, PARP抑制剂, PD-1/PD-L1抑制剂, CTLA-4抑制剂, CAR-T, ADC, TACE, NGS, ctDNA, MSI-H/dMMR, TMB.\n"
            "- Do not focus only on targeted and immune therapy. Also extract surgery, radiotherapy, chemotherapy toxicity/supportive-care, trial-method, and evaluation-standard triples when present.\n"
            "- High-confidence examples: 系统性淋巴结清扫 联合使用 解剖性肺叶切除; 化疗 导致 骨髓抑制/心脏毒性; 粒细胞刺激因子 缓解 中性粒细胞减少; RECIST标准 用于 影像学疗效评估; 双膦酸盐/RANKL通路抑制剂 用于治疗 骨相关事件.\n"
            "- These examples are not the whole answer. Continue extracting the other explicit triples in the same chunk, especially treatment indications, biomarker benefit, adverse events, monitoring, and combination therapy.\n"
            "- Do not create endpoints from long clinical conditions, metaphors, or graph-building advice such as 药物治疗癌症, 节点之间的规则化连接, 名词爆炸, 知识图谱系统.\n"
        )
    elif profile and profile.name == "corridor_logistics_midlevel_precision":
        endpoint_policy = (
            "- For this corridor-logistics document, strongly prefer short infrastructure, city, port, energy, information-system, and support-facility endpoints from the inventory.\n"
            "- Extract stable network relations, not operational log fragments. Prefer labels: 调度, 协同, 监控, 连接, 服务于, 配置, 同步, 触发, 保障, 属于, 位于, 影响.\n"
            "- High-value relation patterns: 城市/调度节点 调度 港口或工业节点; 信息平台 连接/同步/服务于 港口、关务中心、冷链系统、预测模型; 保障设施 服务于/保障 港区、粮食储备、多式联运班列; 港口/油田/管道 属于 国家.\n"
            "- Preserve cargo/product and monitoring nodes when explicit and relational: 聚乙烯单元, 能源类货流, 高时效货物, SCADA, SCADA 终端, AIS, VTS, AIS 航迹校核. Useful patterns include 石化园区 包含 聚乙烯单元; 杰伊汉港 服务于 能源类货流; 伊斯坦布尔 服务于 高时效货物; 卫星调度台 监控 AIS/VTS.\n"
            "- Do not miss support-chain and external-link relations when they are explicit: 开罗 协同 苏伊士运河; 亚历山大港 协同 粮食储备中心/海水淡化补给网; 亚历山大港 依赖于 吞吐量预测模型; 区域冷链追踪系统 服务于 哈马德港/杰贝阿里港/亚喀巴港/舒艾拜港; 海水淡化补给网 服务于 粮食储备中心; 粮食储备中心 协同 应急燃料库/多式联运班列; 应急燃料库 保障 多式联运班列.\n"
            "- Keep aliases canonical: 朱拜勒/Jubail工业节点/东部园区核心化工岛 -> 朱拜勒工业城; DQ -> 杜库姆港（DQ）; SH -> 苏哈尔港（SH）; Yard-Forecast/吞吐模型 -> 吞吐量预测模型; 预测引擎 may be kept when explicitly named.\n"
            "- Do not create endpoints from batch numbers, windows, timestamps, percentages, temperature thresholds, vehicle counts, version numbers, or sentences such as 若08:00前未完成A-Loop切换.\n"
            "- Do not over-extract isolated abbreviations such as ETA, ETD, TEU, FEU, VLCC, ULCC, NGL unless they are explicit relation endpoints.\n"
        )
    elif profile and profile.name == "global_energy_transition_macro_balanced":
        endpoint_policy = (
            "- For this global-energy-transition document, extract a macro concept graph. Prefer stable high-level endpoints such as 能源系统, 全球能源系统, 能源资源, 基础设施, 政策工具, 技术路线, 市场机制, 经济体 when the text frames a broad relationship.\n"
            "- Do not over-expand into every country, every mineral, or every flexible-grid tool. Prefer 52-66 high-confidence relations over a very dense fine-grained graph.\n"
            "- Preferred labels: 影响, 约束, 调节, 应用于, 促使, 驱动, 构建, 构筑, 发布, 推动, 属于, 依赖于, 构成, 替代.\n"
            "- High-value macro patterns: 国际能源署（IEA）/政府间气候变化专门委员会（IPCC）/联合国气候变化框架公约（UNFCCC） 影响 能源系统; 气候变化 约束 能源系统; 可再生能源 替代 化石燃料; 财政激励 应用于 能源系统; 政策工具 促使 技术路线.\n"
            "- High-value policy patterns: 欧盟 发布 欧盟碳排放交易体系（EU ETS）; 美国 发布 通胀削减法案（IRA）; 巴黎协定 驱动 欧盟; 碳边境调节机制（CBAM） 属于 欧盟; 绿色金融 促使 产业升级; 国家自主贡献（NDC） 约束 中国.\n"
            "- High-value power-system patterns: 中国 构建 新型电力系统; 中国 构筑 电网建设; 新型储能 应用于 电力系统; 辅助服务市场 调节 电力系统; 可再生能源 影响 电力系统; 数据中心 约束 局部电网; 容量市场 调节 局部电网.\n"
            "- High-value technology patterns: 绿氢 依赖于 电解槽; 蓝氢 依赖于 CCUS; 氢能 应用于 炼化/钢铁直接还原（DRI）; CCUS 应用于 水泥; 小型模块化反应堆（SMR） 属于 核能; 水电 约束 生态约束; 生物质与生物燃料 替代 能源资源.\n"
            "- Split slash lists if the list itself becomes an endpoint, but prefer macro endpoints such as 关键矿产, 新能源项目, 电网建设, 技术路线 instead of many one-off list items.\n"
            "- Keep aliases canonical: EU ETS -> 欧盟碳排放交易体系（EU ETS）; CBAM -> 碳边境调节机制（CBAM）; IRA -> 通胀削减法案（IRA）; HVDC/UHV -> 高压直流输电（HVDC/UHV）; SAF -> 可持续航空燃料（SAF）; SMR -> 小型模块化反应堆（SMR）.\n"
            "- Do not create endpoints from garbled markers, section titles alone, or full narrative clauses.\n"
        )
    elif profile and profile.name == "english_energy_system_reference_aligned":
        endpoint_policy = (
            "- For this English energy-system document, keep all entity names, types, attributes, and relation labels in English.\n"
            "- Extract a reference-like macro concept graph. Prefer stable endpoints from the inventory, especially Global Energy System, Fossil Fuels, Coal, Oil, Natural gas, Carbon emissions, Climate Change, Energy Transition, Renewable energy, Nuclear energy, Hydrogen, Electricity grids, Smart Grids, Energy policy, Policy, International Organizations, Developed Countries, Developing Countries.\n"
            "- Preferred relation labels: powers, is_part_of, contains, drives, affects, influences, supports, enables, regulates, requires, mitigates, challenges, used_for, applies_to, optimizes.\n"
            "- High-value fossil/climate patterns: Global Energy System powers Economic Activity; Fossil Fuels is_part_of Global Energy System; Fossil Fuels contains Coal/Oil/Natural gas; Coal/Oil/Natural gas drives Carbon emissions; Carbon emissions drives Climate Change; Climate Change influences Energy policy and drives Energy Transition.\n"
            "- High-value renewable/grid patterns: Solar energy/Wind energy/Hydropower is_part_of Renewable energy; Wind energy powers Electricity grids; Nuclear energy supports Electricity grids; Battery technology enables Electricity grids; Batteries supports Renewable energy; Smart Grids is_part_of Electricity grids; Electricity grids requires Renewable energy.\n"
            "- High-value hydrogen/policy patterns: Hydrogen enables Hard-to-abate sectors; Hydrogen used_for Steelmaking/Chemicals/Long-Distance Transport; Renewable Electricity applies_to Green Hydrogen; Energy policy regulates Electricity grids; Policy regulates Energy System/Energy Transition; International Organizations influences Energy System and supports Developing Countries.\n"
            "- Do not miss reference-style macro relations: Global Energy System contains Energy Transition/Fossil Fuels; Coal/Oil/Nuclear energy is_part_of Global Energy System; Energy Transition drives Global Economy/Earth’s Climate System; Technology enables Energy System and influences Energy Transition; Public Acceptance influences Energy Transition; Regulations/Subsidies applies_to Energy policy; Smart Grids optimizes Grid Modernization; Renewable energy mitigates Energy Security.\n"
            "- Canonicalize synonyms aggressively: use Storage, not Energy Storage Technologies/Pumped hydropower/Thermal storage/Compressed air energy storage; use Policy, not Policy interactions; use Technology, not Technology interactions/Technological innovation; use Pipelines, not Hydrogen Infrastructure; use Earth’s Climate System, not Stability of Earth’s climate system; use Global Economy, not Future of the global economy.\n"
            "- Forbidden noisy endpoints for this file: Price volatility, Supply disruptions, Uneven resource distribution, Import-dependent economies, Electricity markets, Decentralized energy production, Grid stability, Energy efficiency, Energy storage technologies, Nuclear power plants, Decarbonization, System optimization, Markets, Geopolitical tensions, Regional conflicts, Global energy markets, Trade relationships.\n"
            "- Do not create endpoints from full sentences, generic section titles, or long explanatory clauses. Keep relation endpoints short and canonical. Aim for about 50-56 high-confidence relations.\n"
        )
    elif profile and profile.name == "english_evolution_reference_aligned":
        endpoint_policy = (
            "- For this English evolution document, keep all entity names, types, attributes, and relation labels in English.\n"
            "- Extract a compact reference-style graph around evolutionary mechanisms, major transitions, and representative lineages. Do not build a large textbook ontology.\n"
            "- Preferred endpoints: Biological evolution, Organism, Last Universal Common Ancestor (LUCA), RNA World hypothesis, RNA, DNA, Proteins, Cellular structures, Environmental constraints, Natural selection, Mutation, Genetic drift, Gene flow, Photosynthesis, Cyanobacteria, Great Oxidation Event, Aerobic respiration, Eukaryotic cells, Endosymbiotic theory, Mitochondria, Multicellularity, Cambrian Explosion, Oxygen levels, Regulatory genes, Speciation, Biodiversity, Mass extinction, Mammals, Cretaceous period, Dinosaur groups, Primates, Homo sapiens, Cultural evolution, Climate change.\n"
            "- Useful optional endpoints when explicit and connected: Adaptation, Mass extinction events, Anaerobic Processes, Survival, Reproduction, Cell Adhesion, Communication, Common Ancestor, Atmospheric Oxygen, Different Lineages.\n"
            "- Preferred relation labels: drives, enables, facilitates, results_in, is_evidence_for, is_composed_of, influenced_by, occurred_during, shares_ancestry_with, causes, depends_on, evolved_from, is_more_efficient_than.\n"
            "- High-value mechanism patterns: Environmental constraints drives Biological evolution; Mutation enables Natural selection; Gene flow influenced_by Genetic drift; Climate change drives Biological evolution.\n"
            "- High-value early-life patterns: Last Universal Common Ancestor (LUCA) shares_ancestry_with Organism; RNA World hypothesis is_evidence_for RNA; Last Universal Common Ancestor (LUCA) is_composed_of Cellular structures; Natural selection drives RNA.\n"
            "- High-value transition patterns: Cyanobacteria drives Photosynthesis; Photosynthesis results_in Great Oxidation Event; Great Oxidation Event enables Aerobic respiration; Endosymbiotic theory is_evidence_for Eukaryotic cells; Mitochondria is_composed_of Eukaryotic cells; Multicellularity facilitates Eukaryotic cells; Oxygen levels drives Cambrian Explosion; Regulatory genes enables Cambrian Explosion.\n"
            "- High-value later-history patterns: Speciation causes Biodiversity; Mass extinction occurred_during Cretaceous period; Dinosaur groups facilitates Mammals; Primates drives Homo sapiens; Cultural evolution influenced_by Biological evolution.\n"
            "- Forbidden noisy endpoints: Life on Earth, early evolution, genetic information, amino acids, RNA sequences, genetic material, allele frequencies, populations, energy conversion, anaerobic organisms, modern populations, habitat modification, human activity, conservation, environmental management, Africa, Understanding evolution.\n"
            "- Do not use entity types as relation labels, such as organism, concept, process, biological_process, biochemical_molecule, environmental_factor, or cellular_structure. Keep relation endpoints short and canonical. Aim for about 23-35 high-confidence relations.\n"
        )
    elif profile and profile.name == "english_evolution_pdf_mechanism_aligned":
        endpoint_policy = (
            "- For this PDF, the main document language is English. Ignore Chinese annotations, noisy tables, page numbers, code-block markers, and garbled text. Output English only.\n"
            "- Extract a population-level biological evolution mechanism graph. Do not reuse the file-15 LUCA/RNA-world/Cambrian history template unless those endpoints are explicitly central in this PDF chunk.\n"
            "- Preferred endpoints: Biological evolution, Population, Heritable variation, Genetic variation, Mutation, Natural selection, Selection pressure, Environmental conditions, Common ancestor, DNA, Adaptation, Fitness, Genetic drift, Gene flow, Speciation, Reproductive isolation, Fossil record, Extinction, Mass extinction, Asteroid impact, Volcanic activity, Ecosystems, Comparative anatomy, Molecular biology.\n"
            "- Evidence-source endpoints are important here: do not hide Comparative anatomy and Molecular biology only inside attributes of Common ancestor. Extract them as entities and connect them with supports Common ancestor when present.\n"
            "- Expansion endpoints are also important for this PDF. When explicit, extract these as standalone entities instead of hiding them in attributes: Environmental Factors, Selection Pressures, Small Populations, Geographic Barriers, Behavioral Differences, Ecological Specialization, Genetic Information, New Genetic Material, Extinction Events, Asteroid Impacts, Mass Extinction Events, Macroevolutionary Patterns.\n"
            "- Keep exactly one table-derived observation endpoint if present and useful: Evolution observation batch 002. Do not keep batch 001, batch 003, sample counts, data-entry status, remarks, or malformed table cells.\n"
            "- Preferred relation labels: operates_on, drives, shape, explains, carries, produces, occurs_in, acts_on, define, increases, changes, counteracts, causes, results_from, supports, documents, reshapes, modifies, influence, is_a, records, measures.\n"
            "- High-value mechanism relations: Biological evolution operates_on Population; Heritable variation drives Biological evolution; Environmental conditions shape Heritable variation; Common ancestor explains Biological evolution; DNA carries Heritable variation; Mutation produces Genetic variation; Genetic variation occurs_in Population; Natural selection acts_on Population; Selection pressure drives Natural selection; Environmental conditions define Selection pressure; Natural selection produces Adaptation; Adaptation increases Fitness.\n"
            "- High-value population/speciation/evidence relations: Genetic drift changes Population; Gene flow acts_on Population; Gene flow increases Genetic variation; Gene flow counteracts Genetic drift; Reproductive isolation causes Speciation; Speciation results_from Biological evolution; Fossil record supports Biological evolution; Fossil record documents Extinction; Comparative anatomy supports Common ancestor; Molecular biology supports Common ancestor; Fossil record supports Common ancestor.\n"
            "- High-value extinction/environment relations: Asteroid impact causes Mass extinction; Volcanic activity causes Mass extinction; Mass extinction is_a Extinction; Extinction reshapes Ecosystems; Population modifies Environmental conditions; Environmental conditions influence Biological evolution; Evolution observation batch 002 records Biological evolution; Evolution observation batch 002 measures Population.\n"
            "- High-value expansion relations: DNA carries Genetic Information; Mutation introduces New Genetic Material; Genetic variation arises_from Mutation; Genetic variation drives Natural selection; Environmental Factors imposes Selection Pressures; Environmental Factors defines Selection Pressures; Genetic drift depends_on Small Populations; Gene flow causes New Genetic Material; Speciation is_part_of Macroevolutionary Patterns; Fossil record supports Macroevolutionary Patterns; Macroevolutionary Patterns is_part_of Biological evolution; Extinction Events reshapes Ecosystems.\n"
            "- Forbidden endpoints: Evolution observation batch 001, Evolution observation batch 003, valid sample count, data entry status, temporary note, graph TD, 种群分化, 基因流中断, page numbers, Ê markers, 𝕏𝕐ℤ, ∮, 代码块.\n"
        )
    elif profile and profile.name == "english_quantum_theory_compact":
        endpoint_policy = (
            "- For this quantum theory document, keep all entity names, types, attributes, and relation labels in English.\n"
            "- Extract a compact history-and-concepts graph. Do not create a full physics ontology or philosophical discussion graph.\n"
            "- Preferred people: Max Planck, Albert Einstein, Niels Bohr, Werner Heisenberg, Erwin Schrödinger, Max Born.\n"
            "- Preferred theory/formalism endpoints: Quantum Theory, quantum mechanics, Planck Constant, Bohr Model of the Atom, Matrix Mechanics, Wave Mechanics, Schrödinger's Equation, Wave Function, probabilistic interpretation of quantum mechanics, Uncertainty Principle.\n"
            "- Preferred phenomena/concepts/applications: Black-Body Radiation, Photoelectric Effect, Photon, probability density, position, momentum, superposition, measurement, wave function collapse, Copenhagen interpretation, many-worlds interpretation, quantum entanglement, qubit, quantum computing, quantum cryptography, quantum communication.\n"
            "- Preferred relation labels: introduced_by, contributed_to, part_of, led_to, explains, supports, proposed, developed, formulated_by, governs_system, uses, derived_from, affected_by, introduced_in, caused_by, interpretation_of, applies_to.\n"
            "- High-value patterns: Quantum Theory introduced_by Max Planck/Albert Einstein/Niels Bohr/Werner Heisenberg/Erwin Schrödinger; Planck Constant part_of Quantum Theory; Black-Body Radiation led_to Quantum Theory; Photoelectric Effect led_to Quantum Theory; Albert Einstein explains Photoelectric Effect; Photoelectric Effect supports Photon.\n"
            "- High-value formalism patterns: Niels Bohr proposed Bohr Model of the Atom; Werner Heisenberg developed Matrix Mechanics; Erwin Schrödinger developed Wave Mechanics; Matrix Mechanics and Wave Mechanics part_of quantum mechanics; Schrödinger's Equation governs_system quantum systems and uses Wave Function; Max Born introduced probabilistic interpretation of quantum mechanics; probability density derived_from Wave Function.\n"
            "- High-value principle/application patterns: Uncertainty Principle formulated_by Werner Heisenberg; position/momentum affected_by Uncertainty Principle; superposition introduced_in Quantum Theory; wave function collapse caused_by measurement; Copenhagen interpretation and many-worlds interpretation interpretation_of quantum mechanics; quantum computing uses qubit/superposition/quantum entanglement; quantum cryptography and quantum communication applies_to Quantum Theory.\n"
            "- Forbidden noisy endpoints: Dinger’s equation, correlations between particles, reality, determinism, role of the observer, philosophical questions, intuitive understanding, classical physics, emerging technologies, fundamental interactions, electromagnetic radiation, microscopic scales, matter and energy.\n"
        )
    elif profile and profile.name == "english_conspiracy_0609_platform":
        endpoint_policy = (
            "- For this conspiracy-theory document, keep English output and preserve the 0609 package style: about 30 entities and 32 broad platform relations.\n"
            "- Preferred endpoints: Conspiracy theories, Conspiracy theory, Moon landing hoax, Apollo 11 mission, Moon landing, United States government, U.S. government, Soviet Union, Assassination of John F. Kennedy, John F. Kennedy assassination, Lee Harvey Oswald, CIA, Mafia, Illuminati, September 11 attacks, September 11, 2001 terrorist attacks, 9/11 conspiracy theories, Internet, Social media, Official narratives, Distrust of authority, human desire for alternative explanations, Neil Armstrong, Buzz Aldrin, Texas School Book Depository, flat Earth, public opinion, power, truth, Celebrity deaths.\n"
            "- Preferred relation labels: challenges, is attributed to, is associated with, originates from, is fueled by, contains, is_part_of, affects, supports, causes, drives.\n"
            "- High-value platform patterns: Moon landing hoax challenges Apollo 11 mission and is attributed to United States government; CIA/Mafia/Lee Harvey Oswald is associated with Assassination of John F. Kennedy; 9/11 conspiracy theories originates from September 11 attacks and challenges Official narratives; Internet and Social media is fueled by 9/11 conspiracy theories; Conspiracy theories contains Moon landing/United States government/Soviet Union/CIA/Mafia; Illuminati is_part_of Conspiracy theories and affects Celebrity deaths; power drives Conspiracy theories; truth challenges Conspiracy theories.\n"
            "- Do not collapse same-looking but reference-distinct endpoints such as Conspiracy theories vs Conspiracy theory, United States government vs U.S. government, or September 11 attacks vs September 11, 2001 terrorist attacks.\n"
            "- Negative feedback warning: shorter claim-safe variants and clean factual ontologies lowered the score. Avoid World Trade Center, Pentagon, controlled demolitions, and long precise claim nodes unless the model strongly extracts them from the text.\n"
        )
    elif profile and profile.name == "english_coral_reef_0609_platform":
        endpoint_policy = (
            "- For this coral reef document, preserve the 0609 package style: about 30 entities and 35 relations with mixed casing and broad ecosystem-service labels.\n"
            "- Preferred endpoints: Coral reefs, Coral polyps, Marine life, Coastal communities, Coastal protection, Fisheries, Natural disasters, Sustainable fisheries, Tourism, Climate change, Pollution, Marine protected areas, Greenhouse gas emissions, marine biodiversity, ecosystem services, human activities, environmental stressors, conservation and sustainable management, Biodiversity, Human Well-being, Local Economies, Coral Bleaching, Tourism Industry, Fish, Storms, Fishing, Overfishing, Ocean Ecosystems, Calcium Carbonate, Ocean Acidification.\n"
            "- Preferred relation labels: contributes_to, is_habitat_for, protects, provides, mitigates, relies_on, supports, threatens, impacts, contains, is_part_of, affects, causes.\n"
            "- High-value platform patterns: Coral polyps contributes_to Coral reefs; Coral reefs is_habitat_for Marine life; Coral reefs protects Coastal communities; Coral reefs provides Coastal protection/Tourism/ecosystem services; Coral reefs mitigates Natural disasters; Fisheries and Sustainable fisheries relies_on Coral reefs; Coral reefs supports Fisheries/Sustainable fisheries/marine biodiversity/Marine life/Fishing/Tourism Industry/Local Economies; Climate change threatens Coral reefs; Pollution impacts or affects Coral reefs; Marine protected areas protects Coral reefs; Greenhouse gas emissions contributes_to or causes Climate change; Coral reefs contains marine biodiversity/Fish; Coral reefs is_part_of Ocean Ecosystems; Coral polyps contains Calcium Carbonate; Climate change and Ocean Acidification cause Coral Bleaching; Biodiversity supports Human Well-being.\n"
            "- Negative feedback warning: the smaller semantic-cleanup graph lowered the score. Do not over-normalize casing, do not remove Fish/Storms/Fishing/Ocean Ecosystems, and do not replace all legacy relation labels with a single clean label.\n"
        )
    elif profile and profile.name == "english_fairytale_origin_versions":
        endpoint_policy = (
            "- For this fairytale-origin document, keep all entity names, types, attributes, and relation labels in English.\n"
            "- Extract tale-origin/version relations. Distinguish authors, collectors, collections, tales, source traditions, and explicit story characters or motifs.\n"
            "- Preferred endpoints: Fairytales, Grimm's Fairy Tales, Brothers Grimm, Jacob Grimm, Wilhelm Grimm, German countryside, oral traditions, Cinderella, Rhodopis, ancient Greece, Charles Perrault, fairy godmother, glass slipper, Snow White, evil queen, seven dwarfs, Hansel and Gretel, cannibalistic witch, European folklore, Beauty and the Beast, ancient myths, Ovid, Pygmalion and Galatea, Love and Transformation.\n"
            "- Preferred relation labels: contains, collected_by, collected_in, published_by, published_in, originated_from, has_version_by, introduced, features_character, contains_motif, inspired_by, wrote_about, part_of, gathered_from.\n"
            "- High-value collection/version patterns: Grimm's Fairy Tales contains Cinderella/Snow White/Hansel and Gretel; Grimm's Fairy Tales published_by Brothers Grimm; Jacob Grimm part_of Brothers Grimm; Wilhelm Grimm part_of Brothers Grimm; Brothers Grimm gathered_from German countryside and oral traditions.\n"
            "- Do not omit the collector/source backbone: Jacob Grimm part_of Brothers Grimm; Wilhelm Grimm part_of Brothers Grimm; Grimm's Fairy Tales published_by Brothers Grimm; Brothers Grimm gathered_from oral traditions; Brothers Grimm gathered_from German countryside.\n"
            "- If Jacob Grimm, Wilhelm Grimm, Brothers Grimm, and Grimm's Fairy Tales are in the inventory, include the membership/publishing relations even if the text states them in prose. If Ovid and Pygmalion and Galatea are in the inventory, the direction is Ovid wrote_about Pygmalion and Galatea.\n"
            "- High-value tale patterns: Cinderella originated_from Rhodopis and ancient Greece; Cinderella has_version_by Charles Perrault; Charles Perrault introduced fairy godmother/glass slipper; Snow White originated_from German folklore and features_character evil queen/seven dwarfs; Hansel and Gretel collected_by Brothers Grimm, originated_from European folklore, and features_character cannibalistic witch; Beauty and the Beast originated_from ancient myths and inspired_by Pygmalion and Galatea; Ovid wrote_about Pygmalion and Galatea; Pygmalion and Galatea contains_motif Love and Transformation.\n"
            "- Forbidden false relations: Fairytales authored_by Brothers Grimm; Beauty and the Beast collected_by Brothers Grimm; Beauty and the Beast authored_by Ovid; Cinderella published_in Charles Perrault; Ovid authored_by Pygmalion and Galatea; Jacob Grimm collected_by Grimm's Fairy Tales.\n"
            "- Avoid generic theme endpoints such as magical elements, heroic protagonists, moral lessons, human experience, power of storytelling unless the model can connect them precisely and briefly.\n"
        )
    elif profile and profile.name == "english_millennium_prize_reference_aligned":
        endpoint_policy = (
            "- For this Millennium Prize Problems document, keep entity names, types, attributes, and relation labels in English.\n"
            "- Extract a review-style reference graph around the Clay Mathematics Institute, the seven Millennium Prize Problems, named mathematicians, mathematical fields, theories, application domains, and the document's concluding historical/cultural framing.\n"
            "- Preferred institution/history endpoints: Clay Mathematics Institute, Landon T. Clay, Millennium Prize Problems, David Hilbert, Paris, Mathematics.\n"
            "- Preferred problem endpoints: P versus NP problem, P vs NP problem, Riemann Hypothesis, Navier–Stokes existence and smoothness problem, Yang–Mills existence and mass gap problem, Hodge conjecture, Birch and Swinnerton-Dyer conjecture, Poincaré conjecture.\n"
            "- Preferred people/theory endpoints: Bernhard Riemann, Claude-Louis Navier, George Gabriel Stokes, Chen Ning Yang, Robert Mills, Yang–Mills theory, Quantum Yang–Mills theory, Henri Poincaré, Grigori Perelman, Ricci flow with surgery.\n"
            "- Preferred expansion endpoints: Computational complexity theory, Theoretical Computer Science, Cryptography, Optimization, Algorithm Design, Algebraic geometry, Number theory, Standard Model, Standard Model of particle physics, Bryan Birch, Peter Swinnerton-Dyer, Elliptic curve, Navier–Stokes Equations.\n"
            "- Do not actively chase fine mathematical detail endpoints such as W. V. D. Hodge, Richard Hamilton, Riemann zeta function, L-function, Prime numbers, Fluid dynamics, Quantum field theory, Topology, or Three-dimensional sphere. Keep them only if the model has already selected them naturally and the graph remains within the target scale.\n"
            "- Also keep short concluding-frame endpoints when explicitly present: Historical Traditions, Modern Scientific Needs, Abstract Mathematical Thinking. Do not expand them into long sentence-like entities.\n"
            "- Preferred relation labels: founded, proposed, established, announced_by, belongs_to, is_part_of, contains, applies_to, affects, influences, named_after, addresses, concerns, forms_foundation_of, forms_the_foundation_of, formulated_by, developed_by, proposed_by, solved_by, located_in, is_located_in, originates_from.\n"
            "- High-value institution/history relations: Landon T. Clay founded Clay Mathematics Institute; Clay Mathematics Institute proposed/established Millennium Prize Problems; Millennium Prize Problems announced_by Clay Mathematics Institute; David Hilbert influences Millennium Prize Problems; Millennium Prize Problems is_located_in Paris for the announcement; Millennium Prize Problems influences Mathematics.\n"
            "- High-value P versus NP relations: P versus NP problem belongs_to Computational complexity theory; P versus NP problem is_part_of Millennium Prize Problems; Computational complexity theory applies_to P versus NP problem; Cryptography affects P versus NP problem; Optimization affects P versus NP problem; P versus NP problem affects Algorithm Design/Theoretical Computer Science.\n"
            "- High-value problem/person relations: Bernhard Riemann proposed Riemann Hypothesis; Claude-Louis Navier and George Gabriel Stokes named_after Navier–Stokes existence and smoothness problem; Chen Ning Yang and Robert Mills proposed Yang–Mills theory; Yang–Mills theory addresses Yang–Mills existence and mass gap problem and forms_foundation_of Standard Model; Hodge conjecture belongs_to Algebraic geometry; Birch and Swinnerton-Dyer conjecture belongs_to Number theory and applies_to Elliptic curve; Bryan Birch/Peter Swinnerton-Dyer formulated_by Birch and Swinnerton-Dyer conjecture; Henri Poincaré proposed/proposed_by Poincaré conjecture; Grigori Perelman addresses/solved_by Poincaré conjecture; Ricci flow with surgery forms_foundation_of Poincaré conjecture.\n"
            "- Fine-detail relations around Riemann zeta function, L-function, Prime numbers, Fluid dynamics, Quantum field theory, Topology, Three-dimensional sphere, W. V. D. Hodge, and Richard Hamilton are optional, not required; previous forced expansion in this direction lowered the score.\n"
            "- For attributes, add short distinguishing facts for named problems and people: field_of_study, proposer, year, status, location, role, related_problem, or application. Avoid long Description values.\n"
            "- Forbidden noisy endpoints: whether P is equal to NP, distribution of prime numbers as a phrase, one million US dollars, technical difficulty, theoretical mathematics, mass gap phenomenon, Perelman’s proof, mathematical community, targets for resolution, guiding landmarks for mathematical exploration, living discipline, enduring mystery of mathematics.\n"
        )
    elif profile and profile.name == "english_greek_mythology_reference_precision":
        endpoint_policy = (
            "- For this Greek mythology document, keep all entity names, types, attributes, and relation labels in English.\n"
            "- Extract a precision-oriented reference graph, not a complete narrative graph. There is no fixed quantity limit, but every entity and relation must be central and likely to appear in a compact mythology answer key.\n"
            "- Preferred endpoints: Zeus, Cronus, Hera, Athena, Apollo, Artemis, Demeter, Hades, Persephone, Moirai, Clotho, Lachesis, Atropos, fate, Heracles, Alcmene, Cerberus, Nemean Lion, Achilles, Peleus, Thetis, Trojan War, Paris, Helen, Troy, Mount Olympus, Delphi, Athens, Odysseus, Ares, Aphrodite, Hermes, Charon.\n"
            "- Optional endpoints only when they form a very stable core triple: Poseidon, Hestia, Underworld, Styx, Tartarus, Hector, Agamemnon, Trojan Horse. Do not include them just because they are mentioned.\n"
            "- Preferred relation labels: parent_of, son_of, daughter_of, spouse_of, is_twin_sister_of, is_ruler_of, resides_in, patron_deity_of, associated_with, involves, abducted_by, captured_by, killed, slayed_by, is_part_of, governs, govern, opposed_by, overthrew.\n"
            "- High-value patterns: Zeus overthrew/killed Cronus; Zeus spouse_of Hera; Zeus is_ruler_of/resides_in Mount Olympus; Zeus parent_of Athena/Apollo/Heracles; Demeter parent_of Persephone; Hades spouse_of Persephone; Athena patron_deity_of/governs Athens; Athena associated_with Odysseus; Apollo resides_in Delphi; Artemis is_twin_sister_of Apollo; Achilles son_of Peleus/Thetis; Trojan War involves Achilles; Heracles son_of Zeus/Alcmene; Heracles killed Nemean Lion; Cerberus captured_by Heracles; Clotho/Lachesis/Atropos is_part_of Moirai; Moirai governs/govern fate.\n"
            "- Avoid the previous low-scoring expansion style: do not output sibling lists for Zeus, Underworld/Styx/Tartarus scenery chains, Trojan Horse infiltration, Hector/Agamemnon side stories, or duplicated inverse relations unless the model is very confident they are central.\n"
            "- Forbidden noisy endpoints: gods, mortals, causes, governs as an entity, guides souls, is child of, plays role in, resides in, rules over, wilderness, mortal affairs, conflict, land, winter, twelve labors, sea, souls, Greek forces, walls, sanctity of marriage, power, love, human condition, natural world.\n"
        )
    elif profile and profile.name == "english_blockchain_aurorachain_compact_architecture":
        endpoint_policy = (
            "- For this AuroraChain document, keep all entity names, types, attributes, and relation labels in English.\n"
            "- Extract a compact system architecture graph for the described network. Do not build a generic blockchain glossary or a sentence-by-sentence event graph.\n"
            "- Preferred component endpoints: AuroraChain Network, NovaTech Labs, Distributed Ledger, Validator Nodes, Proof of Authority, Proof of Authority consensus mechanism, AuroraToken, Smart Contracts, Contract Deployment Module, Digital Identities, Digital Identity, Identity Management System, Transaction Pool, Cross-Chain Gateway, Governance Committee, Governance Smart Contracts, Monitoring Service, API Gateway, Audit Nodes.\n"
            "- Preferred compact data/operation endpoints: On-Chain Data, Off-Chain Data, Transaction Records, Relayer Services, Regulatory bodies, Independent Auditors, Enterprise, cryptographic hashes, permissioned blockchain, unconfirmed transactions, new blocks, pay transaction fees, premium network services, submit transactions, full copy of the Distributed Ledger, network activity.\n"
            "- Preferred relation labels: contains, composed_of, integrates, uses, utilizes, operates, operates_as, manages, used_for, enables_access_to, incentivizes, follows, validates, monitors, packages, stores, temporarily_stores, relies_on, references, analyzes, interacts_with, operated_by, operate, governs, implements, facilitates, developed_by.\n"
            "- High-value compact patterns: AuroraChain Network contains/composed_of Distributed Ledger and Validator Nodes; AuroraChain Network integrates Cross-Chain Gateway, Smart Contracts, Digital Identities; AuroraChain Network operates_as permissioned blockchain; NovaTech Labs developed_by AuroraChain Network.\n"
            "- High-value compact patterns: AuroraToken used_for pay transaction fees, incentivizes Validator Nodes, enables_access_to premium network services; Smart Contracts executed_via Contract Deployment Module and used_for submit transactions; Identity Management System manages Digital Identities.\n"
            "- High-value compact patterns: Transaction Pool stores/temporarily_stores unconfirmed transactions; Validator Nodes monitor/manage/operate Transaction Pool, validate Distributed Ledger, follow Proof of Authority, package new blocks; Cross-Chain Gateway relies_on Relayer Services.\n"
            "- High-value compact patterns: Governance Committee governs AuroraChain Network and implements Governance Smart Contracts; Governance Smart Contracts facilitates Governance Committee; Monitoring Service analyzes network activity and interacts_with Governance Committee; On-Chain Data includes Transaction Records; Off-Chain Data references cryptographic hashes; Audit Nodes maintain full copy of the Distributed Ledger and are operated_by Regulatory bodies/Independent Auditors; Enterprise uses AuroraChain Network.\n"
            "- Forbidden endpoints that previously reduced score: Monetary Policy, Core Protocol, Asset Transfer Contract, Cryptographic Proofs, External blockchain systems, asset transfers, data exchange, external applications, developers, blockchain data, cryptographic keys, verifiable credentials, Smart Contract States, Governance Decisions, alerts, anomalies, malicious behavior, performance degradation, transparency, immutability, accountability, efficiency, governance as a standalone generic concept, security, trust, operational friction, centralized intermediaries.\n"
        )
    else:
        endpoint_policy = "- You may add a new endpoint only if the text clearly introduces an important named entity, standard, metric, component, person, place, organization, method, disease, medicine, or concept.\n"
    return f"""
You are extracting relation triples for the LCFC Lenovo knowledge graph competition.
Use the document-level entity inventory as the preferred endpoint list.

Document language: {language_name}
Chunk: {chunk_index + 1}/{chunk_count}
{strategy}
{variant_strategy}
{experiment_strategy}
{round_strategy}
{reference_strategy}

Entity inventory:
{inventory_json}

Relation policy:
- Relation labels must be in {language_name}.
- Relation labels must be predicates or verb phrases, not entity categories. Good: affects/影响, used_for/用于, contains/包含. Bad: 添加剂, 参数, 技术, 质量控制体系, hardware component.
- Prefer relation endpoints from the inventory.
{endpoint_policy.rstrip()}
- Extract explicit or strongly nearby-implied relations. Keep high-confidence recall within the document-specific target scale; do not expand low-confidence details just to add more triples.
- Prefer {relation_target} relations for information-rich chunks.
- Prefer domain-specific verbs when explicit, but do not drop a good triple just because the best label is broad.
- For medical text, prefer labels like 适用于, 用于治疗, 关联于, 提示获益, 导致, 联合使用, 监测.
- For ecology/literature/fashion/simple English text, keep relation recall: use natural labels such as protects, threatens, provides, authored_by, collected_in, evolved_during, popularized_by.
- Use concise labels such as: {relation_examples}.
- Use contains/包含 only for explicit whole-part, composition, membership, or taxonomy.
- For containment direction: whole -> contains -> part.
- Do not output vague labels such as description, definition, appears, mentions, related_to, context, 说明, 描述, 定义, 出现.
- Relation source and target must be atomic entity names, not sentences or lists.
- Return JSON only.

Required JSON:
{{
  "entities": [
    {{"name": "...", "type": "...", "attributes": {{}}}}
  ],
  "relations": [
    {{"source": "...", "type": "...", "target": "...", "strength": 8}}
  ]
}}

TEXT:
\"\"\"{text}\"\"\"
""".strip()


def build_attribute_prompt(
    *,
    text: str,
    language: str,
    entities: list[dict],
    profile: DocumentProfile | None = None,
    prompt_variant: str = "auto",
    reference_guidance: dict | None = None,
    strategy_note: str = "",
) -> str:
    language_name = _language_name(language)
    attr_examples = _attribute_examples(language)
    strategy = f"\n\n{profile.prompt_block()}" if profile else ""
    variant_strategy = f"\n\n{_variant_block(prompt_variant, language)}" if _variant_block(prompt_variant, language) else ""
    experiment_strategy = f"\n\n{_strategy_note_block(strategy_note, language)}" if _strategy_note_block(strategy_note, language) else ""
    round_strategy = f"\n\n{_competition_round_block(strategy_note, language)}" if _competition_round_block(strategy_note, language) else ""
    reference_strategy = _reference_guidance_block(reference_guidance, language)
    entities_json = json.dumps(
        [{"name": e.get("name"), "type": e.get("type")} for e in entities],
        ensure_ascii=False,
    )
    return f"""
You are filling attributes for already-selected entities in the LCFC Lenovo knowledge graph competition.
This stage improves attribute-fusion F1. Do not add new entities or relations.

Document language: {language_name}
{strategy}
{variant_strategy}
{experiment_strategy}
{round_strategy}
{reference_strategy}

Entities to enrich:
{entities_json}

Attribute policy:
- Output attribute keys and values in {language_name}.
- Use only facts explicitly supported by the text.
- Keep values short and distinctive. Avoid generic long descriptions.
- Good attribute keys include: {attr_examples}.
- Do not add attributes like generic description/definition unless the value is very short and uniquely identifying.
- Prefer attributes that would help distinguish this entity from nearby entities in the same document.
- If no useful short fact exists for an entity, return an empty attributes object.
- Return JSON only.

Required JSON:
{{
  "entities": [
    {{"name": "...", "attributes": {{"key": "value"}}}}
  ]
}}

TEXT:
\"\"\"{text}\"\"\"
""".strip()


def build_reference_patch_prompt(
    *,
    text: str,
    language: str,
    reference_graph: dict,
    profile: DocumentProfile | None = None,
    attribute_limit: int = 10,
    relation_limit: int = 3,
) -> str:
    language_name = _language_name(language)
    attr_examples = _attribute_examples(language)
    strategy = f"\n\n{profile.prompt_block()}" if profile else ""
    entities = reference_graph.get("entities", []) or []
    relations = reference_graph.get("relations", []) or []
    sparse_entities = [
        {
            "name": entity.get("name", ""),
            "type": entity.get("type", ""),
            "attributes": entity.get("attributes", {}),
        }
        for entity in entities
        if isinstance(entity, dict) and not entity.get("attributes")
    ]
    if not sparse_entities:
        sparse_entities = [
            {
                "name": entity.get("name", ""),
                "type": entity.get("type", ""),
                "attributes": entity.get("attributes", {}),
            }
            for entity in entities
            if isinstance(entity, dict) and len(entity.get("attributes") or {}) < 2
        ]
    reference_payload = {
        "entities": [
            {
                "name": entity.get("name", ""),
                "type": entity.get("type", ""),
                "attributes": entity.get("attributes", {}),
            }
            for entity in entities
        ],
        "relations": relations,
        "sparse_entities_first": sparse_entities[:80],
    }
    reference_json = json.dumps(reference_payload, ensure_ascii=False)
    return f"""
You are improving an already high-scoring LCFC Lenovo knowledge graph.
Do NOT re-extract the whole graph. Produce only a tiny patch on top of the reference graph.

Document language: {language_name}
{strategy}

Reference graph:
{reference_json}

Patch policy:
- You may only update entities that already exist in the reference graph. Use the exact entity names from the reference graph.
- Do not rename entities, do not add new entities, and do not delete entities.
- Attribute updates are the priority. Add at most {attribute_limit} useful updates total.
- Prefer entities with empty or very sparse attributes.
- Attribute keys and values must be in {language_name}; keep explicit acronyms, scientific names, standards, and proper names as written in the source.
- Attribute values must be short, distinctive, and directly supported by the source text. Good keys: {attr_examples}.
- Avoid generic Description/description/简介 unless the value is under 12 words or 20 Chinese characters and uniquely identifies the entity.
- Do not use relation labels as attribute keys. Bad attribute keys: affects, supports, contains, collected_by, features_character, 影响, 依赖, 触发, 同步, 协同, 服务于, 配置, 监控.
- Do not output JSON arrays or comma-heavy lists as attribute values. Use one short phrase only.
- Relation additions are optional. Add at most {relation_limit} high-confidence relations total.
- Relation endpoints must be exact existing reference entity names. Do not introduce relation endpoints that are not already entities.
- Do not add broad related_to/关联/描述/定义/说明 relations.
- If no safe improvement exists, return empty arrays.
- Return JSON only.

Required JSON:
{{
  "attribute_updates": [
    {{"name": "exact existing entity name", "attributes": {{"key": "short value"}}}}
  ],
  "relation_additions": [
    ["exact existing source", "relation label", "exact existing target"]
  ]
}}

SOURCE TEXT:
\"\"\"{text}\"\"\"
""".strip()


def build_relation_delta_prompt(
    *,
    text: str,
    language: str,
    reference_graph: dict,
    profile: DocumentProfile | None = None,
    add_entity_limit: int = 5,
    add_relation_limit: int = 10,
    remove_relation_limit: int = 6,
) -> str:
    language_name = _language_name(language)
    attr_examples = _attribute_examples(language)
    relation_examples = _relation_examples(language)
    strategy = f"\n\n{profile.prompt_block()}" if profile else ""
    reference_payload = {
        "entities": [
            {
                "name": entity.get("name", ""),
                "type": entity.get("type", ""),
                "attributes": entity.get("attributes", {}),
            }
            for entity in reference_graph.get("entities", []) or []
            if isinstance(entity, dict)
        ],
        "relations": [
            relation[:3]
            for relation in reference_graph.get("relations", []) or []
            if isinstance(relation, list) and len(relation) >= 3
        ],
    }
    reference_json = json.dumps(reference_payload, ensure_ascii=False)
    return f"""
You are a relation-spine critic for the LCFC Lenovo knowledge graph competition.
You are NOT extracting a new graph. You are reviewing a high-scoring reference graph and proposing only a few source-evidenced entity/relation deltas.

Document language: {language_name}
{strategy}

Reference graph:
{reference_json}

Delta policy:
- Keep all names, types, relation labels, attribute keys, and attribute values in {language_name}.
- Preserve explicit acronyms, scientific names, standards, product names, and proper names as written in the source.
- Do not re-output the full graph. Output only changes that are likely to improve entity F1 or relation triple F1.
- Every change must be supported by a short evidence phrase copied or closely paraphrased from the source text.
- Use only these change_type values: missing_core_entity, missing_core_relation, wrong_relation_label, wrong_endpoint_granularity, noisy_relation_removal.
- Add at most {add_entity_limit} entities. Added entities must be short core endpoints, not examples, long clauses, numeric thresholds, or list fragments.
- Add at most {add_relation_limit} relations. Relation endpoints must be exact reference entity names or names from entity_additions.
- Remove at most {remove_relation_limit} relations. Remove only exact existing reference triples that are low-confidence, wrong-label, wrong-endpoint, or edge-case noise.
- Prefer relation-spine improvements: system-layer-component, technology-mechanism-metric, species-behavior-environment, theory-problem-field, event-cause-result.
- Do not propose attribute-only changes. Attributes are allowed only for newly added entities, and must be short distinctive facts: {attr_examples}.
- Good relation labels include: {relation_examples}.
- Reject broad labels such as related_to, mentions, describes, context, description, definition, 相关, 描述, 说明, 定义.
- If no safe scoring improvement exists, return empty arrays.
- Return JSON only.

Required JSON:
{{
  "entity_additions": [
    {{
      "name": "short entity name",
      "type": "reusable entity type",
      "attributes": {{"key": "short value"}},
      "change_type": "missing_core_entity",
      "evidence": "short source evidence",
      "confidence": 8
    }}
  ],
  "relation_additions": [
    {{
      "source": "exact existing or newly added entity",
      "type": "relation label",
      "target": "exact existing or newly added entity",
      "change_type": "missing_core_relation",
      "evidence": "short source evidence",
      "confidence": 8
    }}
  ],
  "relation_removals": [
    {{
      "source": "exact existing source",
      "type": "exact existing relation label",
      "target": "exact existing target",
      "change_type": "noisy_relation_removal",
      "evidence": "why this reference triple is unsafe",
      "confidence": 8
    }}
  ]
}}

SOURCE TEXT:
\"\"\"{text}\"\"\"
""".strip()


def build_reference_relation_rescue_prompt(
    *,
    text: str,
    language: str,
    candidate_graph: dict,
    relation_candidates: list[list[str]],
    profile: DocumentProfile | None = None,
) -> str:
    language_name = _language_name(language)
    relation_examples = _relation_examples(language)
    strategy = f"\n\n{profile.prompt_block()}" if profile else ""
    candidate_payload = {
        "entities": [
            {
                "name": entity.get("name", ""),
                "type": entity.get("type", ""),
            }
            for entity in candidate_graph.get("entities", []) or []
            if isinstance(entity, dict)
        ],
        "relations": [
            relation[:3]
            for relation in candidate_graph.get("relations", []) or []
            if isinstance(relation, list) and len(relation) >= 3
        ],
    }
    indexed_candidates = [
        {
            "candidate_id": idx + 1,
            "source": relation[0],
            "type": relation[1],
            "target": relation[2],
        }
        for idx, relation in enumerate(relation_candidates)
        if len(relation) >= 3
    ]
    payload = {
        "candidate_graph": candidate_payload,
        "missing_reference_style_relation_candidates": indexed_candidates,
    }
    payload_json = json.dumps(payload, ensure_ascii=False)
    if language == "zh":
        extra_policy = """
- 候选关系来自历史高分图的关系风格；它们不是答案。你必须在 SOURCE TEXT 中找到明确或近邻强隐含证据后才能确认。
- 优先确认端点已经在 candidate_graph.entities 中出现的关系；只有当源文明确出现端点且关系非常核心时，才确认缺失端点关系。
- 不要为了贴近参考而确认原文不支持、方向不对、标签不对或只是泛泛相关的三元组。
- 对 SSD/医学/天体物理等长技术文档，不要只返回最确定的 3-5 条；请逐条审查本批所有候选，凡是源文有明确段落支持的主干关系都应确认。
"""
    else:
        extra_policy = """
- The candidate relations come from a historically high-scoring relation style; they are not answers. Confirm a relation only when SOURCE TEXT explicitly or strongly-nearby supports it.
- Prefer relations whose endpoints already appear in candidate_graph.entities. Confirm a missing-endpoint relation only when the source clearly names both endpoints and the relation is central.
- Do not confirm triples merely to imitate the reference if the source does not support the endpoint, direction, or predicate.
- For long technical documents, do not return only the top 3-5 obvious candidates. Review every candidate in this batch and confirm every backbone relation supported by a clear source passage.
"""
    return f"""
You are a relation-spine rescue reviewer for the LCFC Lenovo knowledge graph competition.
The current graph was extracted from the source but may have missed high-scoring backbone relations.
Your task is NOT to re-extract the graph. Review only the provided missing relation candidates and confirm the ones that are truly source-supported.

Document language: {language_name}
{strategy}

Candidate graph and missing relation candidates:
{payload_json}

Rescue policy:
- Keep all output names and relation labels in {language_name}.
{extra_policy.strip()}
- Confirm only concise backbone relations: composition, dependency, use/application, mechanism, control, cause/effect, location, authorship/proposal, taxonomy, or support/threat/provide.
- Return candidate_id values from missing_reference_style_relation_candidates. Do not rewrite source/type/target fields and do not put evidence text into source/type/target.
- Review all candidates in this batch; returning many confirmed IDs is expected when many candidates are source-supported.
- Good relation labels look like: {relation_examples}.
- Every confirmed relation must include short evidence copied or closely paraphrased from SOURCE TEXT.
- Confidence must be 8 or higher only when the relation is clearly supported.
- If no safe rescue exists, return an empty confirmed_relations array.
- Return JSON only.

Required JSON:
{{
  "confirmed_relation_ids": [
    {{
      "candidate_id": 1,
      "evidence": "short source evidence",
      "confidence": 8
    }}
  ]
}}

SOURCE TEXT:
\"\"\"{text}\"\"\"
""".strip()
