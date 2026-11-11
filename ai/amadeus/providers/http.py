import json, time, urllib.request, urllib.error
from . import ProviderError


def post_json(url, body, headers, timeout=600, retries=2):
    data = json.dumps(body).encode()
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers={"content-type": "application/json", **headers})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:800]
            if e.code in (408, 409, 429) or e.code >= 500:
                if attempt < retries:
                    time.sleep(float(e.headers.get("retry-after") or 2 ** attempt))
                    continue
            raise ProviderError(f"HTTP {e.code} from {url}: {detail}")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise ProviderError(f"cannot reach {url}: {e}")
