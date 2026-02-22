# perplexity

Web search, reasoning, and deep research via Perplexity AI API — with dual-provider support for Perplexity direct and OpenRouter.

## What it does

An agent skill and CLI tool that gives AI agents access to Perplexity's real-time web capabilities: raw search results, quick AI Q&A (Sonar Pro), deep multi-source research (Sonar Deep Research), and step-by-step reasoning (Sonar Reasoning Pro). Supports routing through OpenRouter as an alternative provider.

## Quick start

### Prerequisites
- Python 3.10+
- `uv` ([install](https://astral.sh/uv/install.sh))
- A [Perplexity API key](https://www.perplexity.ai/account/api) and/or [OpenRouter API key](https://openrouter.ai/settings/keys)

### Install the skill
```bash
curl -fsSL https://raw.githubusercontent.com/bobbbino/perplexity-skill/main/install.sh | bash -s -- claude-code
```

<details><summary>Manual install</summary>

```bash
gh release download --repo bobbbino/perplexity-skill --pattern '*.zip'
unzip perplexity-skill-*.zip -d ~/.claude/skills/perplexity
```
</details>

### Set up credentials
```bash
# Option 1: run the install script (offers OS keychain or shell profile export)
curl -fsSL https://raw.githubusercontent.com/bobbbino/perplexity-skill/main/install.sh | bash -s -- claude-code

# Option 2: export manually
export PERPLEXITY_API_KEY=your-key-here    # from https://www.perplexity.ai/account/api
export OPENROUTER_API_KEY=your-key-here    # from https://openrouter.ai/settings/keys
```

### Verify
```bash
perplexity auth status
```

## Usage examples

- "Search for the latest news about Rust programming"
- "What is the current population of Tokyo?"
- "Do a deep research report on mRNA vaccine advances in 2025"
- "Reason through: is it better to use WebSockets or SSE for real-time updates?"

## Available commands

| Command | Description |
|---------|-------------|
| `perplexity auth status` | Check authentication for both providers |
| `perplexity search <query>` | Raw web search (Perplexity API only) |
| `perplexity ask <query>` | Quick AI Q&A via Sonar Pro |
| `perplexity research <query>` | Deep research via Sonar Deep Research |
| `perplexity reason <query>` | Step-by-step reasoning via Sonar Reasoning Pro |

All commands support `--format json|text` and `--provider perplexity|openrouter`.

## Development

```bash
git clone https://github.com/bobbbino/perplexity-skill.git
cd perplexity-skill
uv sync
uv run perplexity --help
uv run pytest
```

## License

MIT
