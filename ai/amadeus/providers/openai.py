"""Any OpenAI-compatible chat-completions endpoint: OpenAI, OpenRouter, ollama,
llama.cpp, LM Studio, vLLM, and most other hosted providers."""
import json
from .. import config
from . import ProviderError
from .http import post_json


class OpenAICompat:
    kind = "chat"

    def __init__(self, name, pcfg):
        self.name, self.cfg = name, pcfg
        self.model = pcfg.get("model", "")
        self.base = pcfg.get("base_url", "https://api.openai.com/v1").rstrip("/")

    def chat(self, system, history, tools):
        if not self.model:
            raise ProviderError(f"provider {self.name} has no model set in config.toml")
        key = config.secret(self.cfg, self.name)
        headers = {"authorization": f"Bearer {key}"} if key else {}
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}] + self._messages(history),
            "tools": [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["schema"]}} for t in tools],
        }
        r = post_json(self.base + "/chat/completions", body, headers)
        try:
            msg = r["choices"][0]["message"]
        except (KeyError, IndexError):
            raise ProviderError(f"unexpected response from {self.name}: {str(r)[:300]}")
        calls = []
        for c in msg.get("tool_calls") or []:
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {"_invalid_json": c["function"].get("arguments")}
            calls.append({"id": c.get("id") or f"call_{len(calls)}", "name": c["function"]["name"], "args": args})
        return {"text": msg.get("content") or "", "calls": calls, "raw": None, "stop": "tools" if calls else "end"}

    def _messages(self, history):
        out = []
        for m in history:
            if m["role"] == "user":
                out.append({"role": "user", "content": m["text"]})
            elif m["role"] == "assistant":
                a = {"role": "assistant", "content": m.get("text") or None}
                if m.get("calls"):
                    a["tool_calls"] = [{"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": json.dumps(c["args"])}} for c in m["calls"]]
                out.append(a)
            else:
                for r in m["results"]:
                    out.append({"role": "tool", "tool_call_id": r["id"], "content": r["content"]})
        return out
