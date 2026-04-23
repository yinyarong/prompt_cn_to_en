# prompt_cn_to_en

> Type in Chinese, send in English — a Claude Code hook for instant, in-place prompt translation.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

## Overview

`prompt_cn_to_en` is a [`UserPromptSubmit`](https://docs.anthropic.com/en/docs/claude-code/hooks) hook for Claude Code. When you prefix a message with `:`, it intercepts the Chinese text, translates it to English using a local LLM (or Google Translate as a fallback), and copies the result to your clipboard — all before the message is sent. You then paste the English translation and submit it instead.

It keeps your Claude Code context in English without interrupting your natural Chinese writing flow.

## Features

- **Colon-trigger:** Prefix any message with `:` or `：` (fullwidth) to activate translation
- **Local-first:** Uses Ollama + Qwen2.5-3B — offline, free, ~0.7 s on Apple Silicon when the model is warm
- **Google Translate fallback:** Falls back to `translate-shell` when Ollama is unavailable
- **Technical-term preservation:** Code, file paths, and variable names are passed through untouched
- **Translation cache:** MD5-keyed disk cache under `~/.claude/hooks/cache/`; max 500 entries with automatic LRU eviction
- **Cross-platform clipboard:** `pbcopy` (macOS), `xclip` / `xsel` (X11), `wl-copy` (Wayland)
- **Zero-cost passthrough:** Messages without Chinese characters or without the `:` prefix are never touched

## How It Works

```
You type:   :帮我重构这段代码，让它更简洁
                │
                ▼
        Hook intercepts (UserPromptSubmit)
                │
                ├─ Cache hit? ──────────────────────────────┐
                │                                           │
                ▼                                           │
        Ollama running?                                     │
          ├─ Yes → Qwen2.5-3B translates                    │
          └─ No  → translate-shell (Google Translate)       │
                │                                           │
                ▼                                           │
        Clean LLM preamble ("Here is the translation…")    │
                │                                           │
                ▼                                           ▼
        Copy to clipboard ◄─────────────────────────────────┘
        Exit code 2 (blocks original message from sending)

You press Cmd+V, paste the English, and send it.
```

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.10+ | Uses `str \| None` union syntax |
| [Claude Code](https://claude.ai/code) | Hook target |
| [Ollama](https://ollama.com) | Primary backend — `brew install ollama` |
| Qwen2.5-3B model | `ollama pull qwen2.5:3b` (~1.9 GB, one-time) |
| [translate-shell](https://github.com/soimort/translate-shell) | Optional fallback — `brew install translate-shell` |

## Installation

1. Copy the hook into Claude Code's hooks directory:

```bash
cp translate-to-english.py ~/.claude/hooks/translate-to-english.py
```

2. Register the hook in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/translate-to-english.py"
          }
        ]
      }
    ]
  }
}
```

3. Pull the Ollama model (one-time, ~1.9 GB):

```bash
ollama pull qwen2.5:3b
```

## Configuration

Edit the constants at the top of `translate-to-english.py`:

| Variable | Default | Description |
|---|---|---|
| `CACHE_DIR` | `~/.claude/hooks/cache` | Directory for cached translations |
| `CACHE_MAX_ENTRIES` | `500` | Max cached entries before LRU eviction |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Ollama model used for translation |

## Usage

In Claude Code, prefix your Chinese message with `:` or `：`:

```
:帮我解释一下这段代码的作用
```

The hook translates it, copies the English to your clipboard, and blocks the original. You'll see:

```
✅ Cmd+V to paste.
```

Press `Cmd+V` (macOS) or `Ctrl+Shift+V` (Linux), then send.

Messages without the `:` prefix are never intercepted.

## Examples

**Example 1 — Code request:**
```
Input:  :帮我重构这段代码，让它更简洁
Output: Refactor this code to make it more concise
```

**Example 2 — Question:**
```
Input:  :为什么这个函数返回 None？
Output: Why does this function return None?
```

**Example 3 — Cache hit (instant):**
```
Input:  :帮我重构这段代码，让它更简洁   ← same as Example 1
Output: Refactor this code to make it more concise   (served from disk cache, no LLM call)
```

## Testing

Pipe a JSON payload directly to the script to test without Claude Code:

```bash
# Should exit 2, print "✅ Cmd+V to paste." on stderr, and copy English to clipboard
echo '{"prompt":":帮我解释一下这段代码的作用"}' | python3 translate-to-english.py

# Should exit 0 silently (no colon trigger)
echo '{"prompt":"explain this code"}' | python3 translate-to-english.py

# Should exit 0 silently (colon but no Chinese)
echo '{"prompt":":explain this code"}' | python3 translate-to-english.py
```

## Troubleshooting

**Hook fires but clipboard is empty**

Ollama is not running and `translate-shell` is not installed. Start Ollama (`ollama serve`) or install the fallback (`brew install translate-shell`).

**`ollama pull` is slow**

The Qwen2.5-3B model is ~1.9 GB. Pull it on a good connection once and it stays local forever.

**Translation includes "Here is the translation:" preamble**

The `clean_translation()` function strips common LLM preambles. If a new pattern slips through, add it to the `prefixes_to_skip` list in the script.

**Hook does not trigger at all**

Verify the hook is registered in `~/.claude/settings.json` under `UserPromptSubmit` and that the path to the script is correct.

## Contributing

Issues and pull requests are welcome. Please open an issue first to discuss significant changes.

## License

MIT
