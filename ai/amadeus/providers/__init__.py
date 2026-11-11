"""Provider-independent model access.

Two kinds of provider:
  chat   the daemon runs the tool loop; the provider does one model turn.
         (anthropic, openai-compatible: OpenAI, OpenRouter, ollama, llama.cpp, ...)
  agent  an external agent CLI runs its own loop on a subscription login and
         reaches the OS through Amadeus' MCP server, so policy and audit still apply.
         (claude-cli, codex-cli)

Neutral history format (provider adapters translate it):
  {"role": "user", "text": str}
  {"role": "assistant", "text": str, "calls": [{"id", "name", "args"}], "raw": provider-native}
  {"role": "tool", "results": [{"id", "name", "content": str, "is_error": bool}]}
"""
from .. import config


class ProviderError(Exception):
    pass


def make(name, cfg):
    pcfg = cfg["providers"].get(name)
    if not pcfg:
        raise ProviderError(f"no provider named {name!r} in config")
    t = pcfg.get("type")
    if t == "anthropic":
        from .anthropic import Anthropic
        return Anthropic(name, pcfg)
    if t == "openai":
        from .openai import OpenAICompat
        return OpenAICompat(name, pcfg)
    if t == "claude-cli":
        from .cli import ClaudeCLI
        return ClaudeCLI(name, pcfg)
    if t == "codex-cli":
        from .cli import CodexCLI
        return CodexCLI(name, pcfg)
    raise ProviderError(f"unknown provider type {t!r}")
