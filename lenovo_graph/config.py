from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR = ROOT / "zhishipublic"
DEFAULT_VERSION_PREFIX = "lenovograph"


def default_version_name() -> str:
    return f"{DEFAULT_VERSION_PREFIX}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


DEFAULT_VERSION_NAME = default_version_name()
DEFAULT_OUTPUT_ROOT = ROOT / "output"
DEFAULT_OUTPUT_DIR = DEFAULT_OUTPUT_ROOT / DEFAULT_VERSION_NAME

DEFAULT_OLLAMA_MODEL = "qwen2.5:14b"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite-preview"

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

SUPPORTED_SUFFIXES = {".pdf", ".md", ".txt"}


@dataclass(frozen=True)
class ExtractConfig:
    backend: str = "ollama"
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    output_dir: Path = DEFAULT_OUTPUT_DIR
    output_file: Path | None = None
    reference_dir: Path | None = None
    reference_guidance: bool = False
    reference_relation_rescue: bool = False
    reference_relation_rescue_stems: tuple[str, ...] = ()
    rescue_relation_limit: int = 80
    rescue_batch_size: int = 35
    pass_through_reference: bool = False
    selection_policy: str = "conservative"
    selection_accept_stems: tuple[str, ...] = ()
    candidate_stems: tuple[str, ...] = ()
    reference_patch_stems: tuple[str, ...] = ()
    relation_delta_stems: tuple[str, ...] = ()
    prompt_variant: str = "auto"
    strategy_note: str = ""
    disable_numbered_profiles: bool = False
    disable_file_postprocess: bool = False
    final_round_profiles: bool = False
    preserve_source_relation_labels: bool = False
    delta_add_entity_limit: int = 5
    delta_add_relation_limit: int = 10
    delta_remove_relation_limit: int = 6
    patch_attribute_limit: int = 10
    patch_relation_limit: int = 0
    chunk_chars: int = 2600
    overlap_chars: int = 300
    max_concurrent: int = 1
    temperature: float = 0.1
    max_output_tokens: int = 4096
    timeout_seconds: int = 180
    keep_raw: bool = False
    use_cache: bool = True
    submission_name: str | None = None
    version_name: str = DEFAULT_VERSION_NAME
    single_stage: bool = False
    attribute_batch_size: int = 25
    attribute_text_chars: int = 30000

    @property
    def resolved_model(self) -> str:
        if self.model:
            return self.model
        if self.backend == "openai":
            return DEFAULT_OPENAI_MODEL
        if self.backend == "gemini":
            return DEFAULT_GEMINI_MODEL
        return DEFAULT_OLLAMA_MODEL

    @property
    def resolved_base_url(self) -> str:
        if self.base_url:
            return self.base_url.rstrip("/")
        if self.backend == "openai":
            return DEFAULT_OPENAI_BASE_URL
        if self.backend == "gemini":
            return DEFAULT_GEMINI_BASE_URL
        return DEFAULT_OLLAMA_BASE_URL
