"""Perplexity AI CLI — web search, reasoning, and deep research."""

import re
import sys
from enum import Enum
from typing import Optional

import httpx
import orjson
import structlog
import typer

from perplexity_cli.config import MODELS, Provider, settings

log = structlog.get_logger()

# ── Output helpers ───────────────────────────────────────────────────────────


class Format(str, Enum):
    json = "json"
    text = "text"


def emit(data, fmt: Format):
    """Write structured data to stdout. NOTHING else goes to stdout."""
    if fmt == Format.json:
        sys.stdout.buffer.write(orjson.dumps(data) + b"\n")
    else:
        if isinstance(data, dict) and "data" in data:
            payload = data["data"]
            if isinstance(payload, str):
                typer.echo(payload)
            elif isinstance(payload, dict):
                for k, v in payload.items():
                    typer.echo(f"{k}: {v}")
            elif isinstance(payload, list):
                for item in payload:
                    typer.echo(item)
        else:
            typer.echo(data)


def emit_error(message: str, code: int, retryable: bool = False,
               remediation: str = ""):
    """Write structured error to stderr and exit."""
    err = {"status": "error", "error": {
        "message": message, "code": code,
        "retryable": retryable, "remediation": remediation,
    }}
    sys.stderr.buffer.write(orjson.dumps(err) + b"\n")
    raise typer.Exit(code)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _resolve_provider(provider: Optional[Provider], command: str) -> Provider:
    """Resolve which provider to use. Search forces perplexity."""
    if command == "search":
        if provider == Provider.openrouter:
            emit_error(
                "The search command is only available via the Perplexity API (not OpenRouter).",
                code=2, retryable=False,
                remediation="Use --provider perplexity or set PERPLEXITY_API_KEY",
            )
        return Provider.perplexity

    if provider is not None:
        return provider

    # Auto-detect: prefer perplexity, fall back to openrouter
    if settings.perplexity_api_key:
        return Provider.perplexity
    if settings.openrouter_api_key:
        return Provider.openrouter
    return Provider.perplexity  # will fail on auth check


def _require_auth(provider: Provider):
    """Exit with code 4 if the provider's API key is missing."""
    key = settings.api_key(provider)
    if not key:
        var = "PERPLEXITY_API_KEY" if provider == Provider.perplexity else "OPENROUTER_API_KEY"
        emit_error(
            f"{var} not set",
            code=4, retryable=False,
            remediation=f"Set {var} env var or run: install.sh",
        )


def _headers(provider: Provider) -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.api_key(provider)}",
    }


def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks from response text."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _format_citations(citations: list[str]) -> str:
    """Format citations as a numbered list."""
    if not citations:
        return ""
    lines = [f"[{i + 1}] {url}" for i, url in enumerate(citations)]
    return "\n\nCitations:\n" + "\n".join(lines)


def _chat_request(provider: Provider, model: str, messages: list[dict],
                  timeout_ms: int) -> dict:
    """Make a chat completions request to either provider."""
    url = f"{settings.base_url(provider)}/chat/completions"
    body = {"model": model, "messages": messages}
    timeout = timeout_ms / 1000.0

    try:
        resp = httpx.post(url, headers=_headers(provider), json=body,
                          timeout=timeout)
    except httpx.TimeoutException:
        emit_error("Request timed out", code=7, retryable=True,
                   remediation="Increase PERPLEXITY_TIMEOUT_MS or try again")
    except httpx.ConnectError as e:
        emit_error(f"Connection error: {e}", code=9, retryable=True)

    if resp.status_code == 429:
        retry_after = resp.headers.get("retry-after", "unknown")
        emit_error(f"Rate limited. Retry after {retry_after}s",
                   code=8, retryable=True)
    if resp.status_code == 401:
        emit_error("Authentication failed — invalid API key",
                   code=4, retryable=False,
                   remediation="Check your API key")
    if resp.status_code >= 400:
        emit_error(f"API error {resp.status_code}: {resp.text}",
                   code=9, retryable=resp.status_code >= 500)

    return resp.json()


def _search_request(query: str, max_results: int, max_tokens_per_page: int,
                    country: Optional[str], timeout_ms: int) -> dict:
    """Make a search request to the Perplexity Search API."""
    url = f"{settings.base_url(Provider.perplexity)}/search"
    body: dict = {
        "query": query,
        "max_results": max_results,
        "max_tokens_per_page": max_tokens_per_page,
    }
    if country:
        body["country"] = country

    timeout = timeout_ms / 1000.0
    try:
        resp = httpx.post(url, headers=_headers(Provider.perplexity),
                          json=body, timeout=timeout)
    except httpx.TimeoutException:
        emit_error("Request timed out", code=7, retryable=True)
    except httpx.ConnectError as e:
        emit_error(f"Connection error: {e}", code=9, retryable=True)

    if resp.status_code == 429:
        retry_after = resp.headers.get("retry-after", "unknown")
        emit_error(f"Rate limited. Retry after {retry_after}s",
                   code=8, retryable=True)
    if resp.status_code == 401:
        emit_error("Authentication failed — invalid API key",
                   code=4, retryable=False)
    if resp.status_code >= 400:
        emit_error(f"API error {resp.status_code}: {resp.text}",
                   code=9, retryable=resp.status_code >= 500)

    return resp.json()


# ── App ──────────────────────────────────────────────────────────────────────

app = typer.Typer(
    name="perplexity",
    help="Web search, reasoning, and deep research via Perplexity AI.",
    no_args_is_help=True,
)

# ── Auth sub-app ─────────────────────────────────────────────────────────────

auth_app = typer.Typer(help="Authentication commands.")
app.add_typer(auth_app, name="auth")


@auth_app.command("status")
def auth_status(
    format: Format = typer.Option(Format.json, "--format", "-f"),
):
    """Check authentication status. Exit 0 if authenticated, 4 if not."""
    import os

    perplexity_ok = bool(settings.perplexity_api_key)
    openrouter_ok = bool(settings.openrouter_api_key)
    authenticated = perplexity_ok or openrouter_ok

    providers = {}
    if perplexity_ok:
        src = "env" if os.environ.get("PERPLEXITY_API_KEY") else "keyring"
        providers["perplexity"] = {"authenticated": True, "token_source": src}
    else:
        providers["perplexity"] = {"authenticated": False}

    if openrouter_ok:
        src = "env" if os.environ.get("OPENROUTER_API_KEY") else "keyring"
        providers["openrouter"] = {"authenticated": True, "token_source": src}
    else:
        providers["openrouter"] = {"authenticated": False}

    result = {"status": "success", "data": {
        "authenticated": authenticated,
        "providers": providers,
        "service": "perplexity",
    }}
    if not authenticated:
        result["data"]["remediation"] = (
            "Set PERPLEXITY_API_KEY or OPENROUTER_API_KEY env var"
        )
    emit(result, format)
    if not authenticated:
        raise typer.Exit(4)


# ── Commands ─────────────────────────────────────────────────────────────────


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query string"),
    max_results: int = typer.Option(10, "--max-results", "-n",
        help="Number of results (1-20)", min=1, max=20),
    max_tokens_per_page: int = typer.Option(1024, "--max-tokens",
        help="Max tokens per page (256-2048)", min=256, max=2048),
    country: Optional[str] = typer.Option(None, "--country", "-c",
        help="ISO 3166-1 alpha-2 country code (e.g. US, GB)"),
    format: Format = typer.Option(Format.json, "--format", "-f"),
):
    """Web search via Perplexity Search API. Returns raw results without AI synthesis.
    Only available via the Perplexity API (not OpenRouter)."""
    _require_auth(Provider.perplexity)
    data = _search_request(query, max_results, max_tokens_per_page, country,
                           settings.perplexity_timeout_ms)

    results = data.get("results", [])
    if format == Format.text:
        if not results:
            typer.echo("No results found.")
            return
        lines = [f"Found {len(results)} search results:\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. **{r.get('title', 'Untitled')}**")
            lines.append(f"   URL: {r.get('url', '')}")
            if r.get("snippet"):
                lines.append(f"   {r['snippet']}")
            if r.get("date"):
                lines.append(f"   Date: {r['date']}")
            lines.append("")
        typer.echo("\n".join(lines))
    else:
        emit({"status": "success", "data": results,
              "metadata": {"count": len(results), "query": query}}, format)


@app.command()
def ask(
    query: str = typer.Argument(..., help="Question to ask"),
    system: Optional[str] = typer.Option(None, "--system", "-s",
        help="System prompt"),
    provider: Optional[Provider] = typer.Option(None, "--provider", "-p",
        help="API provider: perplexity or openrouter (auto-detected if omitted)"),
    format: Format = typer.Option(Format.json, "--format", "-f"),
):
    """Quick AI-answered question with web grounding via Sonar Pro.
    Fast and cost-effective for factual Q&A."""
    prov = _resolve_provider(provider, "ask")
    _require_auth(prov)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": query})

    model = MODELS[prov]["ask"]
    data = _chat_request(prov, model, messages, settings.perplexity_timeout_ms)

    content = data["choices"][0]["message"]["content"]
    citations = data.get("citations", [])
    response_text = content + _format_citations(citations)

    if format == Format.text:
        typer.echo(response_text)
    else:
        emit({"status": "success", "data": {
            "response": response_text,
            "model": data.get("model", model),
            "provider": prov.value,
            "citations": citations,
            "usage": data.get("usage"),
        }}, format)


@app.command()
def research(
    query: str = typer.Argument(..., help="Research topic or question"),
    system: Optional[str] = typer.Option(None, "--system", "-s",
        help="System prompt"),
    strip_thinking: bool = typer.Option(False, "--strip-thinking",
        help="Remove <think> tags from response to save context tokens"),
    provider: Optional[Provider] = typer.Option(None, "--provider", "-p",
        help="API provider: perplexity or openrouter (auto-detected if omitted)"),
    format: Format = typer.Option(Format.json, "--format", "-f"),
):
    """Deep multi-source research via Sonar Deep Research.
    Significantly slower (30s+) but thorough. Best for literature reviews
    and investigative queries."""
    prov = _resolve_provider(provider, "research")
    _require_auth(prov)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": query})

    model = MODELS[prov]["research"]
    data = _chat_request(prov, model, messages, settings.perplexity_timeout_ms)

    content = data["choices"][0]["message"]["content"]
    if strip_thinking:
        content = _strip_thinking(content)
    citations = data.get("citations", [])
    response_text = content + _format_citations(citations)

    if format == Format.text:
        typer.echo(response_text)
    else:
        emit({"status": "success", "data": {
            "response": response_text,
            "model": data.get("model", model),
            "provider": prov.value,
            "citations": citations,
            "usage": data.get("usage"),
        }}, format)


@app.command()
def reason(
    query: str = typer.Argument(..., help="Question requiring reasoning"),
    system: Optional[str] = typer.Option(None, "--system", "-s",
        help="System prompt"),
    strip_thinking: bool = typer.Option(False, "--strip-thinking",
        help="Remove <think> tags from response to save context tokens"),
    provider: Optional[Provider] = typer.Option(None, "--provider", "-p",
        help="API provider: perplexity or openrouter (auto-detected if omitted)"),
    format: Format = typer.Option(Format.json, "--format", "-f"),
):
    """Step-by-step reasoning with web grounding via Sonar Reasoning Pro.
    Best for math, logic, comparisons, and chain-of-thought analysis."""
    prov = _resolve_provider(provider, "reason")
    _require_auth(prov)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": query})

    model = MODELS[prov]["reason"]
    data = _chat_request(prov, model, messages, settings.perplexity_timeout_ms)

    content = data["choices"][0]["message"]["content"]
    if strip_thinking:
        content = _strip_thinking(content)
    citations = data.get("citations", [])
    response_text = content + _format_citations(citations)

    if format == Format.text:
        typer.echo(response_text)
    else:
        emit({"status": "success", "data": {
            "response": response_text,
            "model": data.get("model", model),
            "provider": prov.value,
            "citations": citations,
            "usage": data.get("usage"),
        }}, format)


# ── Entry point ──────────────────────────────────────────────────────────────


def main():
    app()


if __name__ == "__main__":
    main()
