"""Translate a screen observation into provider-native image content, never a URL fetch."""
import base64, json


def split_result(name, content):
    if name != "desktop_observe": return content, None
    try:
        try: value = json.loads(content)
        except (ValueError, TypeError): return content, None
        if not isinstance(value, dict): return content, None
        image = value.pop("image", None)
        if image is None: return content, None
        encoded = image["data"]
        if image.get("mime") != "image/png" or not isinstance(encoded, str) or len(encoded) > 11_184_812:
            raise ValueError("invalid image")
        data = base64.b64decode(encoded, validate=True)
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) > 8_388_608: raise ValueError("invalid PNG")
        return json.dumps(value, ensure_ascii=False), {"data": encoded, "mime": "image/png"}
    except (ValueError, TypeError, KeyError, AttributeError):
        return "Screen observation image could not be decoded; observe again.", None


def mcp_content(name, content):
    text, image = split_result(name, content)
    blocks = [{"type": "text", "text": text}]
    if image: blocks.append({"type": "image", "mimeType": image["mime"], "data": image["data"]})
    return blocks
