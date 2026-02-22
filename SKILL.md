---
name: perplexity
description: >-
  Web search, reasoning, and deep research via Perplexity AI API.
  Use when the user needs real-time web information, factual Q&A,
  multi-source research, step-by-step reasoning grounded in web data,
  or raw search results. Handles search queries, research topics,
  reasoning tasks, citations. Supports Perplexity direct and OpenRouter.
compatibility: Python 3.10+. Requires PERPLEXITY_API_KEY or OPENROUTER_API_KEY.
metadata:
  version: "1.0"
---

# perplexity

Real-time web search, AI-powered Q&A, deep research, and step-by-step reasoning via Perplexity AI. Supports both the Perplexity API directly and OpenRouter as an alternative provider.

---

## Prerequisites
- `PERPLEXITY_API_KEY` and/or `OPENROUTER_API_KEY` environment variable set (see Authentication)
- Install the CLI:
  ```bash
  curl -fsSL https://raw.githubusercontent.com/bobbbino/perplexity-skill/main/install.sh | bash -s -- claude-code
  ```

---

## Command syntax
perplexity <command> [options]

---

## Available commands

### `perplexity search <query>`
Raw web search results — no AI synthesis. **Perplexity API only** (not available via OpenRouter).
**Input**: `--max-results INT` (1-20, default 10), `--max-tokens INT` (256-2048, default 1024), `--country CODE`, `--format json|text`
**Output**: `{"status": "success", "data": [{"title": "...", "url": "...", "snippet": "...", "date": "..."}], "metadata": {"count": N}}`
**Example**:
```bash
perplexity search "latest Claude model release" --max-results 5 --format json
```

### `perplexity ask <query>`
Quick AI-answered question with web grounding via Sonar Pro. Fastest and cheapest option.
**Input**: `--system TEXT`, `--provider perplexity|openrouter`, `--format json|text`
**Output**: `{"status": "success", "data": {"response": "...", "citations": [...], "model": "sonar-pro", "provider": "perplexity"}}`
**Example**:
```bash
perplexity ask "What is the current population of Tokyo?" --format json
perplexity ask "Explain quantum entanglement simply" --provider openrouter --format text
```

### `perplexity research <query>`
Deep multi-source research via Sonar Deep Research. **Significantly slower (30s+)** but thorough.
**Input**: `--system TEXT`, `--strip-thinking`, `--provider perplexity|openrouter`, `--format json|text`
**Output**: `{"status": "success", "data": {"response": "...", "citations": [...], "model": "sonar-deep-research"}}`
**Example**:
```bash
perplexity research "comprehensive overview of mRNA vaccine technology advances in 2025" --strip-thinking
```

### `perplexity reason <query>`
Step-by-step reasoning with web grounding via Sonar Reasoning Pro. Best for math, logic, and chain-of-thought.
**Input**: `--system TEXT`, `--strip-thinking`, `--provider perplexity|openrouter`, `--format json|text`
**Output**: `{"status": "success", "data": {"response": "...", "citations": [...], "model": "sonar-reasoning-pro"}}`
**Example**:
```bash
perplexity reason "Compare the economic impacts of tariffs vs subsidies with examples" --format text
```

### `perplexity auth status`
**Input**: `--format json|text`
**Output**: Authentication state per provider
**Example**:
```bash
perplexity auth status --format json
# {"status": "success", "data": {"authenticated": true, "providers": {"perplexity": {"authenticated": true, "token_source": "env"}, "openrouter": {"authenticated": false}}}}
```

---

## Provider selection

- `--provider perplexity` — call Perplexity API directly (default when `PERPLEXITY_API_KEY` is set)
- `--provider openrouter` — route through OpenRouter (default when only `OPENROUTER_API_KEY` is set)
- Omit `--provider` — auto-detects based on which API key is available (prefers Perplexity)
- `search` command is always Perplexity-only (OpenRouter does not expose the search endpoint)

---

## Error handling

| Exit code | Meaning | Retryable |
|-----------|---------|-----------|
| 0 | Success | — |
| 2 | Bad arguments | No |
| 4 | Auth failure | No — fix credentials |
| 7 | Timeout | Yes |
| 8 | Rate limited | Yes — check retry_after |
| 9 | Remote service error | Yes |

All non-zero exits emit a JSON error envelope to stderr:
```json
{"status": "error", "error": {"message": "...", "code": 4, "retryable": false, "remediation": "..."}}
```

---

## Chaining with other tools

```bash
# Search then ask for a summary of the top result
perplexity search "Rust async runtime" --max-results 1 --format json \
  | jq -r '.data[0].url' \
  | xargs -I{} perplexity ask "Summarize the content at {}" --format text

# Deep research then extract just citations
perplexity research "state of quantum computing 2025" --format json \
  | jq -r '.data.citations[]'
```

---

## Authentication

Set at least one API key:
```bash
# Perplexity direct (supports all 4 commands)
export PERPLEXITY_API_KEY=your-key-here   # from https://www.perplexity.ai/account/api

# OpenRouter (supports ask, research, reason — not search)
export OPENROUTER_API_KEY=your-key-here   # from https://openrouter.ai/settings/keys
```

Always verify before workflows:
```bash
perplexity auth status --format json
```

---

## Limitations
- `search` is Perplexity-only — not available via OpenRouter
- `research` is slow (30+ seconds) — use `ask` for quick questions
- `reason` and `research` may include `<think>` tags — use `--strip-thinking` to remove them
- Rate limits depend on your Perplexity or OpenRouter plan
- Default timeout is 5 minutes (configurable via `PERPLEXITY_TIMEOUT_MS` env var)
