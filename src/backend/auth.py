import hashlib
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from .config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)):
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    expected = settings.internal_api_key.encode()
    provided = api_key.encode()
    if not secrets.compare_digest(
        hashlib.sha256(provided).digest(), hashlib.sha256(expected).digest()
    ):
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key
