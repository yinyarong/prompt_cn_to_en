# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

A single-file Claude Code `UserPromptSubmit` hook that intercepts messages prefixed with `:` or `：`, translates the Chinese content to English via local Ollama (Qwen2.5-3B) with a Google Translate fallback, copies the result to the clipboard, and blocks the original message from sending (exit code 2).

The production copy lives at `~/.claude/hooks/translate-to-english.py`, registered in `~/.claude/settings.json`.

## Translation Pipeline

1. **Ollama + Qwen2.5-3B** — local, offline, ~0.7 s when warm. Requires `ollama serve` to be running.
2. **translate-shell** (`brew install translate-shell`) — Google Translate fallback, requires internet.

If neither backend succeeds, the hook exits 0 (no-op, original message is not blocked).

## Cache

Translations are cached in `~/.claude/hooks/cache/` as MD5-keyed files. Max 500 entries; oldest 50% evicted when the limit is hit.

## Deployment

```bash
cp translate-to-english.py ~/.claude/hooks/translate-to-english.py
```

Ensure the hook is registered in `~/.claude/settings.json`:

```json
"hooks": {
  "UserPromptSubmit": [
    { "matcher": "", "hooks": [{ "type": "command", "command": "python3 ~/.claude/hooks/translate-to-english.py" }] }
  ]
}
```

## Testing

Run manually by piping a JSON payload:

```bash
echo '{"prompt":":你好世界"}' | python3 translate-to-english.py
```

Expected: exits 2, English translation in clipboard, `✅ Cmd+V to paste.` on stderr.
