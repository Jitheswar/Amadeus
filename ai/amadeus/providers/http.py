import json, time, urllib.request, urllib.error
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from . import ProviderError


def _retry_delay(value, attempt):
    """Retry-After is either delta-seconds or an HTTP date (RFC 9110)."""
    if not value:
        return 2 ** attempt
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError):
        return 2 ** attempt


def post_json(url, body, headers, timeout=600, retries=2):
    data = json.dumps(body).encode()
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers={"content-type": "application/json", **headers})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:800]
            e.close()
            if e.code in (408, 409, 429) or e.code >= 500:
                if attempt < retries:
                    time.sleep(_retry_delay(e.headers.get("retry-after"), attempt))
                    continue
            raise ProviderError(f"HTTP {e.code} from {url}: {detail}")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise ProviderError(f"cannot reach {url}: {e}")
