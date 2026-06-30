from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .config import ExtractConfig


CACHE_DIR = Path.home() / ".lenovo_graph" / "cache"


def _cache_key(prompt: str, config: ExtractConfig) -> str:
    payload = {
        "backend": config.backend,
        "model": config.resolved_model,
        "base_url": config.resolved_base_url,
        "temperature": config.temperature,
        "prompt": prompt,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _read_cache(key: str) -> str | None:
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("response")
    except Exception:
        return None


def _write_cache(key: str, response: str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{key}.json"
    path.write_text(json.dumps({"response": response}, ensure_ascii=False), encoding="utf-8")


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    parsed = urlparse(url)
    opener = None
    if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        open_fn = opener.open if opener else urllib.request.urlopen
        with open_fn(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
            content_type = response.headers.get("Content-Type", "")
            if "text/event-stream" in content_type:
                return _parse_event_stream(text)
            return json.loads(text)
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM request failed HTTP {exc.code}: {details[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LLM request failed: {exc}") from exc


def _parse_event_stream(text: str) -> dict[str, Any]:
    parts: list[str] = []
    last: dict[str, Any] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        last = chunk
        choice = (chunk.get("choices") or [{}])[0]
        delta = choice.get("delta") or {}
        message = choice.get("message") or {}
        content = delta.get("content") or message.get("content")
        if content:
            parts.append(content)
    if parts:
        return {"choices": [{"message": {"content": "".join(parts)}}]}
    if last:
        return last
    raise RuntimeError("Empty event-stream LLM response")


def generate_json(prompt: str, config: ExtractConfig) -> str:
    key = _cache_key(prompt, config)
    if config.use_cache:
        cached = _read_cache(key)
        if cached is not None:
            return cached

    if config.backend == "ollama":
        response = _generate_ollama(prompt, config)
    elif config.backend == "openai":
        response = _generate_openai(prompt, config)
    elif config.backend == "gemini":
        response = _generate_gemini(prompt, config)
    else:
        raise ValueError(f"Unsupported backend: {config.backend}")

    if config.use_cache:
        _write_cache(key, response)
    return response


def _generate_ollama(prompt: str, config: ExtractConfig) -> str:
    payload = {
        "model": config.resolved_model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "format": "json",
        "options": {
            "temperature": config.temperature,
            "num_predict": config.max_output_tokens,
        },
    }
    data = _post_json(
        f"{config.resolved_base_url}/api/generate",
        payload,
        {"Content-Type": "application/json"},
        config.timeout_seconds,
    )
    return str(data.get("response", ""))


def _generate_openai(prompt: str, config: ExtractConfig) -> str:
    api_key = config.api_key or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set")
    payload = {
        "model": config.resolved_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": config.temperature,
        "max_tokens": config.max_output_tokens,
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    data = _post_json(
        f"{config.resolved_base_url}/chat/completions",
        payload,
        {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        config.timeout_seconds,
    )
    return str((data.get("choices") or [{}])[0].get("message", {}).get("content", ""))


def _generate_gemini(prompt: str, config: ExtractConfig) -> str:
    # Gemini can be used either through native generateContent or an OpenAI-compatible proxy.
    if config.resolved_base_url.endswith("/openai") or "/openai" in config.resolved_base_url:
        openai_config = ExtractConfig(
            backend="openai",
            model=config.resolved_model,
            base_url=config.resolved_base_url,
            api_key=config.api_key or os.environ.get("GEMINI_API_KEY", ""),
            output_dir=config.output_dir,
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
            timeout_seconds=config.timeout_seconds,
            use_cache=config.use_cache,
        )
        return _generate_openai(prompt, openai_config)

    api_key = config.api_key or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": config.temperature,
            "maxOutputTokens": config.max_output_tokens,
            "responseMimeType": "application/json",
        },
    }
    data = _post_json(
        f"{config.resolved_base_url}/models/{config.resolved_model}:generateContent",
        payload,
        {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        config.timeout_seconds,
    )
    candidates = data.get("candidates") or []
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts") or []
    return "".join(str(part.get("text", "")) for part in parts)
