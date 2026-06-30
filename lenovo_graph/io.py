from __future__ import annotations

import re
from pathlib import Path

from .config import SUPPORTED_SUFFIXES


def read_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        try:
            import fitz  # type: ignore

            with fitz.open(str(path)) as doc:
                return "\n".join(page.get_text() for page in doc)
        except Exception as exc:  # pragma: no cover - depends on local PDF backend
            raise RuntimeError(f"Failed to read PDF {path}: {exc}") from exc
    raise ValueError(f"Unsupported input suffix: {path.suffix}")


def collect_input_files(path: Path) -> list[Path]:
    if path.is_file():
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise ValueError(
                f"Unsupported input file type: {path.suffix}. "
                f"Supported: {', '.join(sorted(SUPPORTED_SUFFIXES))}"
            )
        return [path]
    if not path.is_dir():
        raise FileNotFoundError(f"Input path does not exist: {path}")
    files = sorted(
        p for p in path.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
    )
    if not files:
        raise ValueError(f"No supported files found in {path}")
    return files


def detect_language(text: str) -> str:
    chinese = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    letters = sum(1 for char in text if char.isascii() and char.isalpha())
    return "zh" if chinese > 0 and chinese >= letters * 0.25 else "en"


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[\u200b-\u200f\ufeff]", "", text)
    text = re.sub(
        r"[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U00002600-\U000026FF]",
        " ",
        text,
    )
    text = re.sub(r"[�]+", " ", text)
    text = re.sub(r"(?:Ã.|Â.|þÿ|ã|ð¬)", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, chunk_chars: int, overlap_chars: int) -> list[str]:
    text = normalize_text(text)
    if not text:
        return []
    if len(text) <= chunk_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_chars)
        window = text[start:end]
        if end < len(text):
            split_at = max(
                window.rfind("\n\n"),
                window.rfind("。"),
                window.rfind(". "),
                window.rfind("\n"),
            )
            if split_at > chunk_chars * 0.55:
                end = start + split_at + 1
                window = text[start:end]
        chunks.append(window.strip())
        if end >= len(text):
            break
        start = max(0, end - overlap_chars)
    return [chunk for chunk in chunks if chunk]
