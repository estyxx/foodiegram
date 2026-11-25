from typing import TYPE_CHECKING

from starlette.datastructures import MutableHeaders
from starlette.requests import Request

from dispensa.api_session import is_https

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

# What the no-build frontend loads: its own files, Google Fonts (a stylesheet from
# one host, the font files from another), recipe photos from any HTTPS host
# (Cloudinary, plus older Instagram thumbnails), and nothing inline. JavaScript
# that sets element.style is unaffected; only inline <style>/<script> and
# style="" in markup are refused.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; "
    "img-src 'self' data: https:; "
    "connect-src 'self'; "
    "manifest-src 'self'; "
    "worker-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)
# Leave out features the app never uses; wake lock and the clipboard keep their
# same-origin default.
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
# One year. No preload and no includeSubDomains: the app does not own its domain.
HSTS = "max-age=31536000"

_ALWAYS = (
    ("Content-Security-Policy", CONTENT_SECURITY_POLICY),
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Referrer-Policy", "same-origin"),
    ("Permissions-Policy", PERMISSIONS_POLICY),
    ("Cross-Origin-Opener-Policy", "same-origin"),
)


class SecurityHeadersMiddleware:
    """Add the browser security headers to every HTTP response, errors included.

    Plain ASGI rather than BaseHTTPMiddleware, so streamed and compressed
    responses pass through untouched.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Wrap app."""
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Set the headers as the response starts."""
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        https = is_https(Request(scope))

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in _ALWAYS:
                    headers.setdefault(name, value)
                if https:
                    # Only over TLS: a plain-HTTP HSTS header is ignored anyway,
                    # and local development stays on http.
                    headers.setdefault("Strict-Transport-Security", HSTS)
            await send(message)

        await self._app(scope, receive, send_with_headers)
