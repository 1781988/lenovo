# 联想轻量化知识图谱抽取系统

本仓库只包含知识图谱抽取项目的代码、依赖说明和复现命令，不包含数据集、生成结果、PPT、历史实验文件或本地缓存。

项目用于读取 PDF/Markdown 文档，调用大语言模型抽取实体、关系和属性，并自动生成比赛要求的提交压缩包。

## 目录结构

```text
.
├── lenovo_graph/              # 核心抽取代码
├── run_final_submission.py    # 复赛一键抽取入口
├── run_lenovo_graph.py        # 通用抽取命令入口
├── validate_submission.py     # 本地 JSON/zip 校验脚本
├── requirements.txt           # Python 依赖
└── README.md                  # 使用说明
```

## 数据准备

请在仓库根目录下创建数据目录：

```text
data/zhishipublic_2/
```

并将复赛数据文件放入该目录，例如：

```text
data/zhishipublic_2/1.md
data/zhishipublic_2/2.pdf
...
data/zhishipublic_2/25.md
```

`data/` 已加入 `.gitignore`，不会被提交到仓库。

## 环境安装

建议使用 Python 3.10 或更高版本。

```bash
pip install -r requirements.txt
```

PDF 解析依赖 `PyMuPDF`，Markdown/TXT 文件读取使用 Python 标准库。

## 默认本地模型

默认使用 Ollama 后端和 `qwen2.5:14b` 模型：

```bash
ollama pull qwen2.5:14b
```

脚本会在需要时自动尝试启动 `ollama serve`。

## 一键复赛抽取

在仓库根目录执行：

```bash
python run_final_submission.py
```

默认行为：

- 读取 `data/zhishipublic_2`；
- 使用 Ollama `qwen2.5:14b`；
- 启用复赛主题感知 profile；
- 输出 JSON 到 `output/lenovograph_<时间戳>/`；
- 自动生成 `output/配套_轻量化图谱<时间戳>_100point.zip`；
- zip 内部文件格式为 `submit/submit_*.json`。

如果希望固定输出名称：

```bash
python run_final_submission.py --suffix 20260630_demo
```

## 本地校验

校验 JSON 目录：

```bash
python validate_submission.py output/lenovograph_20260630_demo
```

校验最终提交 zip：

```bash
python validate_submission.py output/配套_轻量化图谱20260630_demo_100point.zip
```

校验内容包括：

- JSON 文件数量；
- `entities` 和 `relations` 基本结构；
- 关系端点是否存在于实体列表；
- 是否存在重复实体、重复关系或自环；
- zip 内部是否符合 `submit/submit_*.json` 格式。

## 其他模型后端

### OpenAI 或 OpenAI 兼容接口

```bash
export OPENAI_API_KEY="your_api_key"

python run_final_submission.py \
  --backend openai \
  --model gpt-4o-mini \
  --base-url https://api.openai.com/v1 \
  --suffix openai_demo
```

如果使用 API 中转站，保持 `--backend openai`，替换 `--base-url` 和 `--model` 即可。

### Gemini 原生接口

```bash
export GEMINI_API_KEY="your_api_key"

python run_final_submission.py \
  --backend gemini \
  --model gemini-3.1-flash-lite-preview \
  --suffix gemini_demo
```

## 抽取策略说明

当前策略面向比赛评分方式设计：

- 实体 F1：40%；
- 三元组 F1：40%；
- 属性融合一致性：20%。

核心设计：

- 使用复赛主题感知 profile，不复用初赛按编号的旧主题策略；
- 针对不同文档主题控制实体规模、关系密度和属性口径；
- 对长文提高关系主干召回，同时保持实体端点短而明确；
- 中文文档输出中文实体/关系/属性，英文文档保留自然英文实体名和短谓词；
- 属性只保留短而有区分度的事实，避免长段描述；
- 后处理负责 JSON 容错、实体类型清洗、属性裁剪、关系端点校验、去重和提交包构造。

## 通用抽取命令

单文件抽取：

```bash
python run_lenovo_graph.py data/zhishipublic_2/20.md \
  --backend ollama \
  -m qwen2.5:14b \
  -o output/file20_demo \
  --selection-policy none
```

目录抽取并生成复赛格式 zip：

```bash
python run_lenovo_graph.py data/zhishipublic_2 \
  --backend ollama \
  -m qwen2.5:14b \
  --selection-policy none \
  --submission-format final \
  --final-time-suffix demo
```

正常复赛流程推荐使用 `run_final_submission.py`，因为它已经内置复赛默认配置。
