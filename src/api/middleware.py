"""Middleware for the MCP server."""

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN


def create_auth_middleware(auth_token: str):
    """Create authentication middleware for static token auth.

    Args:
        auth_token: The authentication token to validate against

    Returns:
        Middleware function that validates Bearer token in Authorization header
    """
    async def auth_middleware(request: Request, call_next):
        """Middleware to check Authorization header for static token."""
        # Skip auth for health checks and OPTIONS requests
        if request.url.path in ["/", "/health", "/ready"] or request.method == "OPTIONS":
            return await call_next(request)

        # Check Authorization header for all MCP requests (GET and POST)
        # stateless_http=True handles GET requests properly, so we just need auth
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=HTTP_401_UNAUTHORIZED,
                content={"error": "Missing or invalid Authorization header"},
            )

        token = auth_header.replace("Bearer ", "").strip()
        if token != auth_token:
            return JSONResponse(
                status_code=HTTP_403_FORBIDDEN,
                content={"error": "Invalid authentication token"},
            )

        return await call_next(request)

    return auth_middleware

