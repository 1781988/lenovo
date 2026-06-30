from __future__ import annotations

import argparse
import os
from pathlib import Path

from .config import DEFAULT_OUTPUT_ROOT, ExtractConfig, default_version_name
from .pipeline import build_final_submission, build_submission, extract_path


def build_parser() -> argparse.ArgumentParser:
    default_run_name = default_version_name()
    parser = argparse.ArgumentParser(
        description="Lenovo competition-specific graph extractor"
    )
    parser.add_argument("input", type=Path, help="Input file or directory")
    parser.add_argument("--backend", choices=["ollama", "openai", "gemini"], default="ollama")
    parser.add_argument("-m", "--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument(
        "--version-name",
        default=default_run_name,
        help="Versioned run name. Defaults to lenovograph_YYYYMMDD_HHMMSS",
    )
    parser.add_argument("-o", "--output-dir", type=Path, default=None)
    parser.add_argument("--output-file", type=Path, default=None)
    parser.add_argument(
        "--reference-dir",
        type=Path,
        default=None,
        help="Optional reference package directory. By default it is only used for comparison/delta context, not for pass-through copying.",
    )
    parser.add_argument(
        "--reference-guidance",
        action="store_true",
        help="Use --reference-dir as prompt guidance for name/scale/style anchors while still regenerating every target file from source.",
    )
    parser.add_argument(
        "--reference-relation-rescue",
        action="store_true",
        help=(
            "After source extraction, ask the model to confirm high-scoring reference-style "
            "relations missing from the candidate and add only source-supported existing-endpoint triples."
        ),
    )
    parser.add_argument(
        "--reference-relation-rescue-stems",
        default="",
        help="Comma-separated file stems where relation rescue should run. Empty means all files when --reference-relation-rescue is set.",
    )
    parser.add_argument(
        "--rescue-relation-limit",
        type=int,
        default=80,
        help="Maximum reference-style relations to ask the model to confirm per file",
    )
    parser.add_argument(
        "--rescue-batch-size",
        type=int,
        default=35,
        help="Number of relation rescue candidates reviewed in each confirmation prompt",
    )
    parser.add_argument(
        "--pass-through-reference",
        action="store_true",
        help="When --reference-dir and stem filters are set, copy non-target files directly from the reference package. Disabled by default.",
    )
    parser.add_argument(
        "--selection-policy",
        choices=["none", "conservative", "balanced", "locked"],
        default="conservative",
        help="How to select between model candidate and --reference-dir graph",
    )
    parser.add_argument(
        "--selection-accept-stems",
        default="",
        help="Comma-separated file stems that should force-accept the model candidate when using a reference",
    )
    parser.add_argument(
        "--candidate-stems",
        default="",
        help="Comma-separated file stems to regenerate when --reference-dir is set; other files pass through reference JSON",
    )
    parser.add_argument(
        "--reference-patch-stems",
        default="",
        help="Comma-separated file stems to improve by applying constrained patches on top of --reference-dir JSON",
    )
    parser.add_argument(
        "--relation-delta-stems",
        default="",
        help="Comma-separated file stems to improve by applying source-evidenced entity/relation deltas on top of --reference-dir JSON",
    )
    parser.add_argument(
        "--prompt-variant",
        choices=["auto", "precision", "recall", "attribute"],
        default="auto",
        help=(
            "Single-document extraction strategy. auto uses score-feedback defaults; "
            "precision favors compact high-confidence graphs; recall favors denser relation-spine graphs; "
            "attribute favors short distinctive attributes without broad entity drift."
        ),
    )
    parser.add_argument(
        "--strategy-note",
        default="",
        help="Additional single-run extraction strategy injected into inventory, relation, and attribute prompts.",
    )
    parser.add_argument(
        "--delta-add-entity-limit",
        type=int,
        default=5,
        help="Maximum accepted entity additions per relation-delta file",
    )
    parser.add_argument(
        "--delta-add-relation-limit",
        type=int,
        default=10,
        help="Maximum accepted relation additions per relation-delta file",
    )
    parser.add_argument(
        "--delta-remove-relation-limit",
        type=int,
        default=6,
        help="Maximum accepted relation removals per relation-delta file",
    )
    parser.add_argument(
        "--patch-attribute-limit",
        type=int,
        default=10,
        help="Maximum accepted attribute updates per patched file",
    )
    parser.add_argument(
        "--patch-relation-limit",
        type=int,
        default=0,
        help="Maximum accepted existing-endpoint relation additions per patched file",
    )
    parser.add_argument("-c", "--concurrent", type=int, default=1)
    parser.add_argument("--chunk-chars", type=int, default=2600)
    parser.add_argument("--overlap-chars", type=int, default=300)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--max-output-tokens", type=int, default=4096)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--keep-raw", action="store_true")
    parser.add_argument(
        "--single-stage",
        action="store_true",
        help="Use the old one-shot chunk extraction mode instead of inventory/relation/attribute stages",
    )
    parser.add_argument("--attribute-batch-size", type=int, default=25)
    parser.add_argument("--attribute-text-chars", type=int, default=30000)
    parser.add_argument(
        "--submission-name",
        default=None,
        help="If set, create competition zip using this work name after extraction; usually same as --version-name",
    )
    parser.add_argument(
        "--submission-format",
        choices=["initial", "final"],
        default="initial",
        help="initial builds the old first-round package; final builds submit/submit_<file>.json with 配套_轻量化图谱时间后缀_100point.zip.",
    )
    parser.add_argument(
        "--final-time-suffix",
        default=None,
        help="Time suffix for final package name. Defaults to YYYYMMDD_HHMMSS from --version-name or current run.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    api_key = args.api_key
    if not api_key and args.backend == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key and args.backend == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
    output_dir = args.output_dir or (DEFAULT_OUTPUT_ROOT / args.version_name)
    submission_name = args.version_name if args.submission_name == "auto" else args.submission_name

    config = ExtractConfig(
        backend=args.backend,
        model=args.model,
        base_url=args.base_url,
        api_key=api_key,
        output_dir=output_dir,
        output_file=args.output_file,
        reference_dir=args.reference_dir,
        reference_guidance=args.reference_guidance,
        reference_relation_rescue=args.reference_relation_rescue,
        reference_relation_rescue_stems=tuple(
            item.strip() for item in args.reference_relation_rescue_stems.split(",") if item.strip()
        ),
        rescue_relation_limit=args.rescue_relation_limit,
        rescue_batch_size=args.rescue_batch_size,
        pass_through_reference=args.pass_through_reference,
        selection_policy=args.selection_policy,
        selection_accept_stems=tuple(
            item.strip() for item in args.selection_accept_stems.split(",") if item.strip()
        ),
        candidate_stems=tuple(item.strip() for item in args.candidate_stems.split(",") if item.strip()),
        reference_patch_stems=tuple(
            item.strip() for item in args.reference_patch_stems.split(",") if item.strip()
        ),
        relation_delta_stems=tuple(
            item.strip() for item in args.relation_delta_stems.split(",") if item.strip()
        ),
        prompt_variant=args.prompt_variant,
        strategy_note=args.strategy_note,
        delta_add_entity_limit=args.delta_add_entity_limit,
        delta_add_relation_limit=args.delta_add_relation_limit,
        delta_remove_relation_limit=args.delta_remove_relation_limit,
        patch_attribute_limit=args.patch_attribute_limit,
        patch_relation_limit=args.patch_relation_limit,
        chunk_chars=args.chunk_chars,
        overlap_chars=args.overlap_chars,
        max_concurrent=args.concurrent,
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
        timeout_seconds=args.timeout_seconds,
        keep_raw=args.keep_raw,
        use_cache=not args.no_cache,
        submission_name=submission_name,
        version_name=args.version_name,
        single_stage=args.single_stage,
        attribute_batch_size=args.attribute_batch_size,
        attribute_text_chars=args.attribute_text_chars,
    )
    extract_path(args.input, config)
    if submission_name:
        if args.submission_format == "final":
            suffix = args.final_time_suffix or args.version_name.replace("lenovograph_", "")
            zip_path = build_final_submission(output_dir, suffix)
        else:
            zip_path = build_submission(output_dir, submission_name)
        print(f"[lenovo_graph] submission zip: {zip_path}")


if __name__ == "__main__":
    main()
