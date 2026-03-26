"""FastAPI middleware for spine token verification."""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from .spine_auth import verify_token

class SpineAuthMiddleware(BaseHTTPMiddleware):
    """Verify spine tokens on incoming requests.

    Checks Authorization header for 'Bearer spine:{timestamp}:{hmac}'.
    Passes through if no spine token present (existing auth still works).
    Rejects if spine token present but invalid.
    """
    async def dispatch(self, request: Request, call_next):
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer spine:"):
            parts = auth[len("Bearer spine:"):].split(":", 1)
            if len(parts) != 2:
                raise HTTPException(401, "Invalid spine token format")
            ts, mac = parts
            if not verify_token(request.url.path, ts, mac):
                raise HTTPException(401, "Invalid or expired spine token")
        return await call_next(request)
