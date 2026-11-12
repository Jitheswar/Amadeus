"""Claude via the Messages API. Raw HTTP on purpose: the daemon runs on the system
Python and must not depend on anything outside the base OS."""
import os
from .. import config
from . import ProviderError
from .http import post_json

OFFICIAL = "https://api.anthropic.com"


class Anthropic:
    kind = "chat"

    def __init__(self, name, pcfg):
        self.name, self.cfg = name, pcfg
        self.model = pcfg.get("model") or "claude-opus-5-5"
        self.base = (pcfg.get("base_url") or OFFICIAL).rstrip("/")

    def chat(self, system, history, tools):
        key = config.secret(self.cfg, self.name)
        if not key:
            raise ProviderError(f"no API key for {self.name}: set {self.cfg.get('key_env')} or run `ama provider key {self.name}`")
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
        body = {
            "model": self.model,
            "max_tokens": int(self.cfg.get("max_tokens", 16000)),
            "system": system,
            "messages": self._messages(history),
            "tools": [{"name": t["name"], "description": t["description"], "input_schema": t["schema"]} for t in tools],
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": self.cfg.get("effort", "medium")},
        }
        # On a policy decline, let the API re-run the turn on a fallback model.
        if self.base == OFFICIAL and self.cfg.get("fallbacks", True):
            headers["anthropic-beta"] = "server-side-fallback-2026-07-01"
            body["fallbacks"] = "default"
        r = post_json(self.base + "/v1/messages", body, headers)
        stop = r.get("stop_reason")
        if stop == "refusal":
            why = (r.get("stop_details") or {}).get("explanation") or "the model declined this request"
            return {"text": f"[declined] {why}", "calls": [], "raw": None, "stop": "end"}
        blocks = r.get("content", [])
        text = "".join(b["text"] for b in blocks if b["type"] == "text")
        calls = [{"id": b["id"], "name": b["name"], "args": b.get("input") or {}} for b in blocks if b["type"] == "tool_use"]
        if stop == "max_tokens":
            calls = []   # a truncated tool call must not run
            blocks = [b for b in blocks if b["type"] != "tool_use"]   # ...or be replayed without a result
            text += "\n[output limit reached]"
        # raw is replayed unchanged so thinking blocks stay valid.
        return {"text": text, "calls": calls, "raw": blocks, "stop": "tools" if calls else "end"}

    def _messages(self, history):
        out = []
        for m in history:
            if m["role"] == "user":
                out.append({"role": "user", "content": m["text"]})
            elif m["role"] == "assistant":
                content = m.get("raw") if m.get("raw_from") == self.name else None
                if content is None:
                    content = ([{"type": "text", "text": m["text"]}] if m.get("text") else []) + [
                        {"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["args"]} for c in m.get("calls", [])]
                out.append({"role": "assistant", "content": content or [{"type": "text", "text": "(no output)"}]})
            else:
                out.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": r["id"], "content": r["content"], "is_error": bool(r.get("is_error"))}
                    for r in m["results"]]})
        return out
