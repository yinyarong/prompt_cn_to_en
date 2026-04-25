#!/usr/bin/env python3
"""
Claude Code Hook: UserPromptSubmit — Clipboard Translation

Flow:
  User types :中文 → hook translates → copies English to clipboard
  → blocks original → user pastes (Cmd+V) English and sends

Translation priority:
  1. Ollama + Qwen2.5-3B  (local, free, fast, natural English output)
  2. translate-shell       (free Google Translate fallback)

Install:
  ollama pull qwen2.5:3b       # pull model (~1.9GB, one-time)
  brew install translate-shell  # optional fallback
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CACHE_DIR = os.path.expanduser("~/.claude/hooks/cache")
CACHE_MAX_ENTRIES = 500
OLLAMA_MODEL = "qwen2.5:7b"


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------
def contains_chinese(text: str) -> bool:
    return bool(re.search(r'[\u4e00-\u9fff\u3400-\u4dbf]', text))


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
def cache_key(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def cache_get(text: str) -> str | None:
    path = os.path.join(CACHE_DIR, cache_key(text))
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return f.read()
        except OSError:
            return None
    return None


def cache_set(text: str, translation: str) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, cache_key(text))
    try:
        with open(path, "w") as f:
            f.write(translation)
        entries = os.listdir(CACHE_DIR)
        if len(entries) > CACHE_MAX_ENTRIES:
            full_paths = [os.path.join(CACHE_DIR, e) for e in entries]
            full_paths.sort(key=lambda p: os.path.getmtime(p))
            for p in full_paths[: len(full_paths) // 2]:
                os.remove(p)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Clipboard
# ---------------------------------------------------------------------------
def copy_to_clipboard(text: str) -> bool:
    try:
        if sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=True, timeout=5)
        elif shutil.which("xclip"):
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text.encode(), check=True, timeout=5,
            )
        elif shutil.which("xsel"):
            subprocess.run(
                ["xsel", "--clipboard", "--input"],
                input=text.encode(), check=True, timeout=5,
            )
        elif shutil.which("wl-copy"):
            subprocess.run(["wl-copy"], input=text.encode(), check=True, timeout=5)
        else:
            return False
        return True
    except (subprocess.SubprocessError, OSError):
        return False


# ---------------------------------------------------------------------------
# Output cleaning
# ---------------------------------------------------------------------------
def clean_translation(text: str) -> str:
    """Remove common LLM prefixes/suffixes from translation output."""
    lines = text.strip().splitlines()
    # Remove leading lines that look like preamble
    prefixes_to_skip = [
        "here's the translation",
        "here is the translation",
        "the translation is",
        "translation:",
        "english translation:",
        "translated text:",
    ]
    while lines:
        first = lines[0].strip().lower().rstrip(":")
        if any(first.startswith(p) or first == p for p in prefixes_to_skip):
            lines.pop(0)
        elif not first:
            lines.pop(0)
        else:
            break
    result = "\n".join(lines).strip()
    # Remove wrapping quotes if present
    if len(result) > 1 and result[0] == '"' and result[-1] == '"':
        result = result[1:-1].strip()
    return result


# ---------------------------------------------------------------------------
# Translation backends
# ---------------------------------------------------------------------------
def translate_with_ollama(text: str) -> str | None:
    """
    Local translation via Ollama API + Qwen2.5-3B.
    Free, offline, fast on Apple Silicon (~0.7s when model is warm).
    Skips instantly if Ollama is not running.
    """
    # Quick health check (0.5s timeout) — skip instantly if Ollama is down
    try:
        check = subprocess.run(
            ["curl", "-s", "--max-time", "0.5", "http://localhost:11434/"],
            capture_output=True, text=True, timeout=2,
        )
        if check.returncode != 0:
            return None
    except (subprocess.TimeoutExpired, OSError):
        return None

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a translator converting Chinese instructions into natural English for an AI coding assistant. "
                    "Produce fluent, idiomatic English that a native speaker would naturally say — "
                    "restructure sentences as needed, do NOT translate word-for-word. "
                    "Convey the speaker's intent clearly. "
                    "Keep code snippets, file paths, variable names, technical terms, and any English words exactly as-is. "
                    "Output ONLY the translated text. No explanations, no quotes, no preamble."
                ),
            },
            {"role": "user", "content": text},
        ],
        "stream": False,
        "options": {"num_predict": 512, "temperature": 0},
    })

    try:
        result = subprocess.run(
            [
                "curl", "-s",
                "http://localhost:11434/api/chat",
                "-d", payload,
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            response = json.loads(result.stdout)
            content = response.get("message", {}).get("content", "").strip()
            if content:
                return clean_translation(content)
    except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError):
        pass
    return None


def translate_with_trans(text: str) -> str | None:
    """
    translate-shell (brew install translate-shell).
    Free Google Translate fallback.
    """
    trans_bin = shutil.which("trans")
    if not trans_bin:
        return None

    try:
        result = subprocess.run(
            [trans_bin, "-b", "-no-ansi", "zh:en", text],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    prompt = input_data.get("prompt", "")

    # Gate 0: only trigger when prompt starts with : or ：(colon trigger)
    if not prompt.startswith(":") and not prompt.startswith("："):
        sys.exit(0)

    # Strip the leading colon
    prompt = prompt.lstrip(":").lstrip("：").strip()

    if not prompt:
        sys.exit(0)

    # Gate 1: no Chinese → pass through
    if not contains_chinese(prompt):
        sys.exit(0)

    # Gate 3: cache hit
    cached = cache_get(prompt)
    if cached:
        copy_to_clipboard(cached)
        print(
            "✅ Cmd+V to paste.",
            file=sys.stderr,
        )
        sys.exit(2)

    # Try translation backends in priority order
    translators = [
        ("Qwen2.5", translate_with_ollama),
        ("Google", translate_with_trans),
    ]

    translated = None
    source = ""
    for name, fn in translators:
        translated = fn(prompt)
        if translated:
            source = name
            break

    if not translated:
        sys.exit(0)

    # Cache and copy to clipboard
    cache_set(prompt, translated)
    copy_to_clipboard(translated)

    print(
        "✅ Cmd+V to paste.",
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
