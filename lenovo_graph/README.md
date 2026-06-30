# Lenovo Graph

`lenovo_graph` 是为 `overview.md` 中比赛评分规则单独构造的抽取管线。它不是 Knwler 的封装，不做 schema discovery、cluster analysis、GML/HTML 导出，只输出比赛需要的 JSON：

```json
{
  "entities": [
    {"name": "实体名", "type": "实体类型", "attributes": {}}
  ],
  "relations": [
    ["实体1", "关系", "实体2"]
  ]
}
```

## 当前策略

当前最高参照包已更新为 `0612/轻量化模型下的知识图谱构建_100point_best_0612（评分31.83）.zip`。它以 `0610(评分31.53)` 为底座，只替换平台单文件测试确认有效的 `5.json`、`6.json`、`10.json`、`22.json`。

- 默认版本：`lenovograph_YYYYMMDD_HHMMSS`
- 默认本地模型：`qwen2.5:14b`
- 默认策略：多阶段抽取，先实体 inventory，再关系抽取，最后补短属性。
- `v1.15` 诊断结论：它调用了本地 `qwen2.5:14b`，但只是参考图属性补丁；实体 `1285`、关系 `1010` 与最高分包完全一致，有属性实体从 `882` 到 `902`，平台分数仍为 `31.53`。
- 当前不再推荐继续提交属性补丁包。下一步应实现 relation-spine critic：让模型基于原文和最高分参考图提出少量有证据的实体/关系 delta。
- 自动门控仍然保留，但接受标准应从“属性收益”转向“历史正收益类型的实体/关系主干变化”。
- 单文档优化新增 `--prompt-variant auto|precision|recall|attribute`。`auto` 会根据当前平台反馈对 `5/10` 使用精度型策略、对 `6` 使用召回型策略、对 `22` 使用属性稳定策略，其它文件保持原策略。
- 新增 `--reference-guidance` 和 `--reference-relation-rescue`。前者用最高分包约束命名/规模，后者让模型按编号分批确认缺失的参考风格主干关系。
- `output/lenovograph_20260612_033453` 已完整重抽并生成 zip，结构上比上一版参考引导包进步，但不建议直接提交：关系重合从 `645/1028` 提到 `729/1028`，仍低于当前最好包，且 `6.md` 未分批 rescue 时补救不足。
- `output/lenovograph_file6_rescue_batch_20260612/6.json` 验证分批 rescue 有效：`6.md` 从 `177/105/170` 改到 `185/178/151`，关系重合从 `48/189` 提到 `96/189`。
- `output/lenovograph_20260612_155123` 已跑完整包并生成 zip，zip 有效、无无效关系，总量 `1318/1045/1010`。它比 `033453` 的关系重合更高（`748/1028` vs `729/1028`），但收益集中在 `6/17`，`5/11/14/21/22/23` 下降，因此不建议整包直接替换当前最高分包。

## 当前最高提交包

已生成最新最高分候选提交包：

```text
0612/轻量化模型下的知识图谱构建_100point_best_0612（评分31.83）.zip
```

对应展开目录：

```text
0612/轻量化模型下的知识图谱构建_100point_best_0612_replace_05_06_10_22_from_195831
```

构造方式：

- 底座：`轻量化模型下的知识图谱构建_100point_0610(评分31.53)`
- 替换：`output/submission_lenovograph_20260611_195831/轻量化模型下的知识图谱构建_100point_lenovograph_20260611_195831` 中的 `5.json`、`6.json`、`10.json`、`22.json`
- 校验：zip 内包含 25 个编号 JSON，无无效关系端点。

## 单文档策略参数

`--prompt-variant` 用于单文件针对性抽取，避免每轮只用同一套提示词。

- `auto`：使用当前反馈规则，`5/10=precision`、`6=recall`、`22=attribute`，其它文件不额外干预。
- `precision`：偏高精度，压掉背景实体、句子片段、弱关系，适合关系 F1 敏感文件。
- `recall`：偏主干召回，适合 `6.md` 这类长技术文档，强调组件、指标、故障、验证、场景之间的关系。
- `attribute`：保持实体/关系主干稳定，重点补短而有区分度的属性，适合英文时期/人物/作品类文件。

单文件抽取示例：

```bash
python run_lenovo_graph.py zhishipublic/6.md \
  --backend ollama \
  -m qwen2.5:14b \
  -c 1 \
  --prompt-variant recall \
  --selection-policy none \
  --no-cache \
  --keep-raw \
  -o output/single_6_recall_$(date +%Y%m%d_%H%M%S)
```

如果想快速生成单文件替换测试包：

```bash
python ~/.codex/skills/lenovo-kg-optimizer/scripts/lenovo_kg_iterate.py single-replace-zips \
  --project . \
  --base '0612/轻量化模型下的知识图谱构建_100point_best_0612_replace_05_06_10_22_from_195831' \
  --candidate output/<候选目录> \
  --output 0612/single_tests \
  --stems 6 \
  --tag file6_recall
```

## v1.15 诊断复现

以下命令可复现 `v1.15`，但它已经被平台验证为 no-gain，只用于诊断：

```bash
python run_lenovo_graph.py zhishipublic \
  --backend ollama \
  -m qwen2.5:14b \
  -c 1 \
  --version-name lenovograph_v1.15 \
  --submission-name lenovograph_v1.15 \
  --reference-dir '轻量化模型下的知识图谱构建_100point_0610(评分31.53)' \
  --reference-patch-stems 1,6,8,9,10,12,13,15,16,17,23,24,25 \
  --patch-attribute-limit 8 \
  --patch-relation-limit 0 \
  --no-cache \
  --keep-raw
```

输出目录：

```text
output/lenovograph_v1.15
```

提交 zip：

```text
output/轻量化模型下的知识图谱构建_100point_lenovograph_v1.15.zip
```

## 下一步推荐策略

下一轮应跑真正的全量模型抽取，不再用最高分包直接透传未处理文件。`--reference-dir` 只适合做诊断、delta 实验或抽取后对比；如果提供参考包但不想回退到参考图，必须使用 `--selection-policy none`。

当前优先推荐“参考引导 + 指定文件分批关系恢复”来生成候选池。注意：跑出的整包需要再做单文件 ablation，不建议不经筛选直接作为最高分替换包。

```bash
python ~/.codex/skills/lenovo-kg-optimizer/scripts/lenovo_kg_iterate.py run-all \
  --project . \
  --input zhishipublic \
  --tag auto \
  --model qwen2.5:14b \
  --reference-dir '轻量化模型下的知识图谱构建_100point_best_0612（评分31.83）' \
  --reference-guidance \
  --reference-relation-rescue \
  --reference-relation-rescue-stems 5,6,11,13,14,17,21,22,23 \
  --rescue-relation-limit 160 \
  --rescue-batch-size 30 \
  --selection-policy none \
  --submission-name auto
```

这个命令仍会重抽全部 `zhishipublic`，但只对指定文件做 relation rescue，避免稳定文件被过度修改。

`155123` 运行后的优先测试顺序：

- 先生成只替换 `6.json`、只替换 `17.json` 的测试包。
- 暂不直接替换 `5/11/14/21/22/23`，这些文件在本轮整包对比中关系重合下降。
- 如果平台反馈 `6` 或 `17` 有提升，再把有效文件合并到当前 `best_0612` 基础包。

推荐新一轮全量抽取命令，输出目录和提交包会自动使用时间戳命名：

```bash
python run_lenovo_graph.py zhishipublic \
  --backend ollama \
  -m qwen2.5:14b \
  -c 1 \
  --selection-policy none \
  --no-cache \
  --keep-raw \
  --submission-name auto
```

如果想显式指定时间戳名，也可以自己传：

```bash
python run_lenovo_graph.py zhishipublic \
  --backend ollama \
  -m qwen2.5:14b \
  -c 1 \
  --version-name lenovograph_20260611_153000 \
  --submission-name auto \
  --selection-policy none \
  --no-cache \
  --keep-raw
```

如果只是想做“参考图 delta 诊断”，才使用：

```bash
python run_lenovo_graph.py zhishipublic \
  --backend ollama \
  -m qwen2.5:14b \
  -c 1 \
  --reference-dir '轻量化模型下的知识图谱构建_100point_0610(评分31.53)' \
  --relation-delta-stems auto \
  --selection-policy none \
  --no-cache \
  --keep-raw \
  --submission-name auto
```

注意：除非显式加 `--pass-through-reference`，否则现在不会再复制未命中的参考文件。

单文件诊断只用于定位问题，不作为主要比赛流程：

```bash
python run_lenovo_graph.py zhishipublic/17.md \
  --backend ollama \
  -m qwen2.5:14b \
  -c 1 \
  -o output/lenovograph_file17_diag \
  --no-cache \
  --keep-raw
```

## 整包对比

推荐使用 skill 辅助脚本。它可以直接传 `0610(评分31.53)` 外层目录，会自动找到内部编号 JSON：

```bash
python ~/.codex/skills/lenovo-kg-optimizer/scripts/lenovo_kg_iterate.py compare-packages \
  --project . \
  --base '轻量化模型下的知识图谱构建_100point_0610(评分31.53)' \
  --candidate output/lenovograph_v1.15
```

查看详细增删：

```bash
python ~/.codex/skills/lenovo-kg-optimizer/scripts/lenovo_kg_iterate.py compare-packages \
  --project . \
  --base '轻量化模型下的知识图谱构建_100point_0610(评分31.53)' \
  --candidate output/lenovograph_v1.15 \
  --details
```

离线门控已有候选包：

```bash
python ~/.codex/skills/lenovo-kg-optimizer/scripts/lenovo_kg_iterate.py select-package \
  --project . \
  --reference '轻量化模型下的知识图谱构建_100point_0610(评分31.53)' \
  --candidate output/lenovograph_v1.10 \
  --output output/lenovograph_v1.11_selected \
  --policy conservative
```

## v1.15 改动与失败结论

- 新增 `--reference-patch-stems`：指定在参考包上做补丁的文件。
- 新增 `--patch-attribute-limit`：每个补丁文件最多接受多少个属性更新。
- 新增 `--patch-relation-limit`：每个补丁文件最多接受多少条关系补丁；当前推荐为 `0`。
- 新增参考图补丁 prompt：模型只输出 `attribute_updates` 和 `relation_additions`，不能重抽整图。
- 补丁过滤更严格：只更新参考包中已有实体；当前默认只给原本空属性的实体补第一个短属性；已有属性不改。
- `v1.15` 本地结果：实体 `1285`、关系 `1010` 完全不变，有属性实体从 `882` 增至 `902`，无效关系 `0`。
- `v1.15` 平台分数仍为 `31.53`，所以属性-only patch 不是下一轮主策略。

## Relation-Spine Delta 参数

- `--relation-delta-stems`：逗号分隔的文件编号，或使用 `auto` 自动选择 `5,10,14,15,16`。
- `--delta-add-entity-limit`：每个文件最多接受多少个新增实体，默认 `5`。
- `--delta-add-relation-limit`：每个文件最多接受多少条新增关系，默认 `10`。
- `--delta-remove-relation-limit`：每个文件最多接受多少条删除关系，默认 `6`。
- `--submission-name auto`：提交包名称自动使用 `--version-name`，默认即时间戳。
- `--pass-through-reference`：显式开启参考包透传；默认关闭，避免新抽取包中大量文件与参考包完全相同。

## 后端

Ollama：

```bash
python run_lenovo_graph.py zhishipublic --backend ollama -m qwen2.5:14b
```

OpenAI：

```bash
export OPENAI_API_KEY="你的 key"
python run_lenovo_graph.py zhishipublic --backend openai -m gpt-4o-mini
```

Gemini：

```bash
export GEMINI_API_KEY="你的 key"
python run_lenovo_graph.py zhishipublic --backend gemini -m gemini-3.1-flash-lite-preview
```

Gemini 代理：

```bash
python run_lenovo_graph.py zhishipublic \
  --backend gemini \
  --base-url https://api.ofox.ai/gemini/v1beta
```

## v1.11 改动

- 新增 `selection.py`：参考包安全选择器，支持 `conservative/balanced/locked/none` 四种策略。
- 新增 `--reference-dir`：指定参照包，可用于选择、delta 或对比上下文；默认不会透传未命中文件。
- 新增 `--candidate-stems`：只重抽指定文件，其余文件直接沿用参考包，避免稳定文件漂移。
- 新增 `--selection-policy`：候选通过门控才会替换参考包；`conservative` 只接受低属性补强且主干稳定的候选。
- `lenovo-kg-optimizer` 新增 `select-package`：对已有候选包离线执行门控融合。
- 验证结果：以 `31.5` 为参考、`v1.10` 为候选时，门控只接受 `14.json` 的 `low_attribute_rescue`，拒绝其它下降文件。

## 关键参数

- `-c / --concurrent`：chunk 并发数，Ollama 建议从 `1` 开始。
- `--chunk-chars`：chunk 字符数，默认 `2600`。
- `--overlap-chars`：chunk 重叠字符数，默认 `300`。
- `--version-name`：版本化输出名，默认 `lenovograph_YYYYMMDD_HHMMSS`。
- `--reference-dir`：参考包目录；指定后可启用安全选择和 delta 重抽，但不会默认透传。
- `--pass-through-reference`：显式复制参考包中未命中的文件，仅用于诊断或保守融合，不推荐作为比赛自动抽取主流程。
- `--candidate-stems`：逗号分隔的重抽文件编号；未列出的文件直接使用参考包。
- `--reference-patch-stems`：逗号分隔的补丁文件编号；这些文件在参考包上应用受约束属性补丁。
- `--relation-delta-stems`：逗号分隔的 delta 文件编号；这些文件在参考包上应用关系主干 delta。
- `--patch-attribute-limit`：每个补丁文件最多接受的属性更新数，默认 `8`。
- `--patch-relation-limit`：每个补丁文件最多接受的关系补丁数，默认 `0`。
- `--selection-policy`：候选选择策略，默认 `conservative`。
- `--single-stage`：回退到旧版单阶段 chunk 抽取模式。
- `--attribute-batch-size`：属性补全阶段每批实体数量，默认 `25`。
- `--attribute-text-chars`：属性补全可见的全文字符数，默认 `30000`，需要更强属性召回时可调大。
- `--keep-raw`：保存每个 chunk 的原始模型响应。
- `--no-cache`：关闭本地 LLM 响应缓存。
- `--submission-name`：抽取完成后直接生成比赛提交 zip。
