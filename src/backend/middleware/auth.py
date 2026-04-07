"""Admin authentication middleware for POLYGOD."""

import secrets

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.backend.config import settings

security = HTTPBearer()


async def admin_required(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> bool:
    """Validate admin token for protected endpoints.

    Args:
        credentials: Bearer token from Authorization header.

    Returns:
        True if token is valid.

    Raises:
        HTTPException: 401 if token is invalid or missing.
    """
    # FIX C3: Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(
        credentials.credentials, settings.POLYGOD_ADMIN_TOKEN.get_secret_value()
    ):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return True
