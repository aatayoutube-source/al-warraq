"""Request-level protection: per-IP rate limits, a same-origin check for POST requests,
and security headers (CSP, clickjacking, MIME sniffing) on every response.

Rate limits are per client IP. Behind a reverse proxy, run uvicorn with --proxy-headers and
FORWARDED_ALLOW_IPS set to the proxy's address, otherwise every visitor looks like the proxy.
RATE_LIMIT_SCALE=2 doubles every limit; RATE_LIMIT_SCALE=0 turns them off.
"""
import os
import re
import time
from collections import deque
from urllib.parse import urlsplit

from starlette.responses import JSONResponse

WINDOW = 60.0  # seconds
# (method, path pattern, requests per minute per IP); first match wins
RULES = [
    ("POST", re.compile(r"^/api/hit$"), 20),
    ("POST", re.compile(r"^/api/track/search$"), 30),
    ("POST", re.compile(r"^/api/like/"), 30),
    ("POST", re.compile(r"^/contact$"), 6),
    ("GET", re.compile(r"^/admin/"), 20),  # password guessing
    ("GET", re.compile(r"^/api/papers$"), 20),   # each new topic asks OpenAlex
    ("GET", re.compile(r"^/api/cover/"), 300),   # covers of a long results page
    ("GET", re.compile(r"^/api/"), 300),
    ("GET", re.compile(r"^/book/"), 120),
]

# The home page has no inline script; inline style attributes carry the cover colours.
# Google Analytics: its loader comes from googletagmanager.com and reports to google-analytics.com.
GA_CONNECT = "https://*.google-analytics.com https://*.analytics.google.com https://*.googletagmanager.com"
SITE_CSP = ("default-src 'self'; script-src 'self' https://www.googletagmanager.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' " + GA_CONNECT + "; "
            "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
# Book pages run small inline scripts, each carrying this response's nonce.
BOOK_CSP = ("default-src 'self'; script-src 'nonce-{nonce}' https://www.googletagmanager.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https://*.wikipedia.org " + GA_CONNECT + "; "
            "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
# Pages with an ad (home, categories, authors, books): only scripts carrying this response's nonce run, and what
# they load may load more ('strict-dynamic': AdSense pulls further scripts from Google addresses that change with
# the visitor's country, adservice.google.iq ...). Ads draw in frames and report back to Google: frames and
# connections to any https address. ('unsafe-inline' and https: only serve browsers too old for nonces.)
AD_CSP = ("default-src 'self'; script-src 'nonce-{nonce}' 'strict-dynamic' 'unsafe-inline' https:; "
          "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; "
          "img-src 'self' data: https:; connect-src 'self' https:; frame-src https:; "
          "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
NO_CSP = ("/docs", "/redoc", "/openapi.json")  # FastAPI's interactive docs load their own scripts


class RateLimiter:
    def __init__(self, scale: float = 1.0):
        self.scale = scale
        self.hits = {}  # (ip, rule index) -> deque of timestamps

    def allow(self, ip: str, method: str, path: str) -> bool:
        if self.scale <= 0:
            return True
        for i, (m, pattern, per_min) in enumerate(RULES):
            if m == method and pattern.search(path):
                break
        else:
            return True
        now = time.monotonic()
        q = self.hits.setdefault((ip, i), deque())
        while q and now - q[0] > WINDOW:
            q.popleft()
        if len(q) >= max(1, int(per_min * self.scale)):
            return False
        q.append(now)
        if len(self.hits) > 20000:  # forget idle clients
            self.hits = {k: v for k, v in self.hits.items() if v and now - v[-1] <= WINDOW}
        return True


def cross_site(request) -> bool:
    """True for a POST sent by another website (the visitor's browser tells us via Sec-Fetch-Site / Origin)."""
    if request.headers.get("sec-fetch-site") == "cross-site":
        return True
    origin = request.headers.get("origin")
    return bool(origin) and origin != "null" and urlsplit(origin).netloc != request.headers.get("host", "")


def install(app) -> None:
    limiter = RateLimiter(float(os.environ.get("RATE_LIMIT_SCALE", "1")))

    @app.middleware("http")
    async def protect(request, call_next):
        path, method = request.url.path, request.method
        if method == "POST" and (path.startswith("/api/") or path == "/contact") and cross_site(request):
            return JSONResponse({"error": "cross-site request refused"}, status_code=403)
        ip = request.client.host if request.client else "?"
        if not limiter.allow(ip, method, path):
            return JSONResponse({"error": "too many requests, slow down"}, status_code=429, headers={"Retry-After": "60"})
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        h.setdefault("Cross-Origin-Opener-Policy", "same-origin-allow-popups")  # an ad's click opens its page
        if request.url.scheme == "https":
            h.setdefault("Strict-Transport-Security", "max-age=15552000")
        if h.get("content-type", "").startswith("text/html") and not path.startswith(NO_CSP):
            h.setdefault("Content-Security-Policy", SITE_CSP)
        return response


def safe_url(url) -> str:
    """Only plain web links may reach an href or src: never javascript:, data: or the like."""
    url = (url or "").strip()
    return url if re.match(r"^https?://", url, re.I) else ""
