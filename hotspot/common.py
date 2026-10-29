import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from jsonschema import Draft202012Validator, FormatChecker

BASE = Path(__file__).resolve().parent.parent
SECRET = re.compile(r'(token|cookie|authorization|password|secret|api.?key|credential)', re.I)

class GateError(ValueError):
    pass

def require(ok, message):
    if not ok:
        raise GateError(message)

def now():
    return datetime.now(timezone.utc).isoformat()

def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')

def sha(data):
    return hashlib.sha256(data).hexdigest()

def digest(obj):
    return sha(canonical(obj))

def read(path):
    return json.loads(Path(path).read_text('utf-8'))

def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.pending-')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(canonical(obj))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def validate(kind, obj):
    filename = {'snapshot': 'hotspot_snapshot', 'candidate': 'topic_candidate'}[kind]
    validator = Draft202012Validator(read(BASE / 'schemas' / (filename + '.schema.json')), format_checker=FormatChecker())
    errors = list(validator.iter_errors(obj))
    require(not errors, '契约校验失败：' + '; '.join('/'.join(map(str, e.path)) + ': ' + e.message for e in errors[:8]))

def safe_url(value):
    if value is None:
        return None
    require(isinstance(value, str), '链接必须是文本')
    u = urlsplit(value)
    require(u.scheme == 'https' and bool(u.hostname) and not u.username and not u.password, '仅接受不含登录凭据的 HTTPS 来源链接')
    require(u.hostname not in ('localhost', '127.0.0.1', '::1') and '.' in u.hostname, '来源须为公开域名')
    return urlunsplit((u.scheme, u.netloc, u.path, urlencode([(k,v) for k,v in parse_qsl(u.query, keep_blank_values=True) if not SECRET.search(k)]), ''))

def redact(obj):
    if isinstance(obj, dict):
        return {k: '[REDACTED]' if SECRET.search(k) else redact(v) for k,v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    if isinstance(obj, str):
        obj = re.sub(r'(?i)(Bearer\s+)[^\s"<>]+', r'\1[REDACTED]', obj)
        obj = re.sub(r'(?i)((?:access_token|refresh_token|api_key|password|cookie|secret)\s*[=:]\s*)[^\s&"<>]+', r'\1[REDACTED]', obj)
    return obj

def contained(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    require(path.is_relative_to(root), '路径越出模块目录')
    return path
