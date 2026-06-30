#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

from lenovo_graph.config import DEFAULT_OUTPUT_ROOT, ExtractConfig
from lenovo_graph.pipeline import build_final_submission, extract_path


FINAL_STRATEGY_NOTE = """复赛通用抽取策略:
- 复赛 zhishipublic_2 的文件编号与初赛主题不对应，必须完全根据当前文档内容判断领域；不要沿用文件编号对应的旧领域先验。
- 复赛高召回参考风格：先识别文档主题、章节结构、表格和干扰文本，再抽核心实体、关系密集主干和短属性。
- 长文要明显提高召回，但不要抽章节标题、闲聊、教学提示、日期通知、无关数字和完整句子端点。
- 关系召回要积极：核心实体不应大量孤立，每个核心概念/人物/地点/过程/作品/技术尽量连接到上位主题、来源、组成、影响、应用、发生地点或代表例子。
- 目标形态参考高质量提交：中文长文通常接近 80-170 个实体、80-150 条关系；英文短文通常接近 50-75 个实体、50-70 条关系。按文件主题 profile 调整，不平均用一套密度。
- 对表格中的关键行可以抽实体和属性，表格列值优先作为短属性；只有能形成稳定三元组时才建关系。
- 实体名应贴近原文表达，保留必要英文缩写/学名/作品名/机构名；type 必须是类别，不能等于 name。
- 关系优先抽清晰主干：包括、包含、属于、需要、提出、由、形成、结合、影响、依赖、提供、强调、应用于、来自、表现为、记录、推动、关联等。
- 属性只写短而有区分度的事实：英文名、定义、作用、分类、时间、地点、符号、单位、学名、体长、生存年代、食性、角色、目的、影响。没有好属性就留空。
- 对综述/科普/历史/文化类文章，不只抽摘要，要覆盖代表例子、发展阶段、核心机制、社会/产业影响和治理动作。
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Lenovo final-round extraction and build the required submission zip."
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path("data/zhishipublic_2"),
        help="Final-round dataset directory. Default: data/zhishipublic_2",
    )
    parser.add_argument("--backend", choices=["ollama", "openai", "gemini"], default="ollama")
    parser.add_argument("-m", "--model", default="qwen2.5:14b")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("-c", "--concurrent", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--suffix", default=None, help="Package time suffix. Default: YYYYMMDD_HHMMSS")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--prompt-variant", choices=["auto", "precision", "recall", "attribute"], default="recall")
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--max-output-tokens", type=int, default=4096)
    parser.add_argument("--chunk-chars", type=int, default=2200)
    parser.add_argument("--overlap-chars", type=int, default=220)
    parser.add_argument("--attribute-batch-size", type=int, default=25)
    parser.add_argument("--attribute-text-chars", type=int, default=30000)
    parser.add_argument("--use-cache", action="store_true", help="Reuse cached model calls. Default: disabled.")
    parser.add_argument("--no-keep-raw", action="store_true", help="Do not save raw prompts/chunks.")
    parser.add_argument(
        "--multi-stage",
        action="store_true",
        help="Use the slower inventory+relation+attribute pipeline. Default finals mode is single-stage.",
    )
    parser.add_argument("--no-start-ollama", action="store_true", help="Do not auto-start ollama serve.")
    return parser


def ollama_is_ready() -> bool:
    try:
        subprocess.run(
            ["ollama", "list"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=5,
        )
        return True
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


def ensure_ollama_ready(model: str, auto_start: bool = True) -> None:
    if ollama_is_ready():
        ensure_ollama_model(model)
        return
    if not auto_start:
        raise RuntimeError("Ollama server is not running. Please run `ollama serve` first.")

    log_path = Path("output") / "ollama_serve.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("ab")
    env = os.environ.copy()
    for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"):
        env.pop(key, None)
    print(f"[final] Ollama is not running; starting `ollama serve` in background. Log: {log_path}")
    subprocess.Popen(
        ["ollama", "serve"],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env=env,
        start_new_session=True,
    )
    for _ in range(30):
        time.sleep(1)
        if ollama_is_ready():
            ensure_ollama_model(model)
            return
    raise RuntimeError(f"Ollama server did not become ready within 30s. See {log_path}")


def ensure_ollama_model(model: str) -> None:
    result = subprocess.run(
        ["ollama", "list"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if model in result.stdout:
        return
    raise RuntimeError(
        f"Ollama model `{model}` is not installed.\n"
        f"Installed models:\n{result.stdout}\n"
        f"Please run: ollama pull {model}"
    )


def main() -> None:
    args = build_parser().parse_args()
    if not args.input.exists():
        raise FileNotFoundError(args.input)

    suffix = args.suffix or datetime.now().strftime("%Y%m%d_%H%M%S")
    version_name = f"lenovograph_{suffix}"
    output_dir = args.output_root / version_name

    api_key = args.api_key
    if not api_key and args.backend == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key and args.backend == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")

    config = ExtractConfig(
        backend=args.backend,
        model=args.model,
        base_url=args.base_url,
        api_key=api_key,
        output_dir=output_dir,
        selection_policy="none",
        prompt_variant=args.prompt_variant,
        strategy_note=FINAL_STRATEGY_NOTE,
        disable_numbered_profiles=True,
        disable_file_postprocess=True,
        final_round_profiles=True,
        preserve_source_relation_labels=True,
        chunk_chars=args.chunk_chars,
        overlap_chars=args.overlap_chars,
        max_concurrent=args.concurrent,
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
        timeout_seconds=args.timeout_seconds,
        keep_raw=not args.no_keep_raw,
        use_cache=args.use_cache,
        version_name=version_name,
        single_stage=not args.multi_stage,
        attribute_batch_size=args.attribute_batch_size,
        attribute_text_chars=args.attribute_text_chars,
    )

    print(f"[final] input: {args.input}")
    print(f"[final] output: {output_dir}")
    print(f"[final] backend/model: {args.backend}/{config.resolved_model}")
    print(f"[final] suffix: {suffix}")

    if args.backend == "ollama":
        ensure_ollama_ready(config.resolved_model, auto_start=not args.no_start_ollama)

    outputs = extract_path(args.input, config)
    zip_path = build_final_submission(output_dir, suffix)

    print(f"[final] json files: {len(outputs)}")
    print(f"[final] submission zip: {zip_path}")


if __name__ == "__main__":
    main()
