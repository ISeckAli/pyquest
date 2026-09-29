"""
Security headers added to every response (spec PR-N2).

These tell the browser what each page may and may not do. The Content
Security Policy is the most important: scripts may run only from PyQuest
itself and the two CDNs the site already uses, so even a script somehow
injected into a page would be refused. It is a second layer behind
Jinja2's automatic escaping, not a replacement for it.
"""

# Script and style sources PyQuest actually uses.
JSDELIVR = "https://cdn.jsdelivr.net"  # Monaco editor and Pyodide (Python)
CDNJS = "https://cdnjs.cloudflare.com"  # Chart.js

CONTENT_SECURITY_POLICY = "; ".join([
    # Anything not listed below may come only from PyQuest itself.
    "default-src 'self'",
    # 'wasm-unsafe-eval' lets the browser compile WebAssembly, which is what
    # Pyodide is. It allows WebAssembly only, not JavaScript eval().
    f"script-src 'self' {JSDELIVR} {CDNJS} 'wasm-unsafe-eval'",
    # Monaco starts its helper workers from data: addresses (see
    # challenge.js), and the Python worker is a file on this site.
    "worker-src 'self' data: blob:",
    # Monaco adds its styles at runtime and the dashboard sets a progress
    # bar's width inline. Inline styles cannot run code, so allowing them is
    # low-risk; inline scripts stay blocked.
    f"style-src 'self' 'unsafe-inline' {JSDELIVR}",
    f"font-src 'self' data: {JSDELIVR}",
    "img-src 'self' data:",
    # Pyodide downloads Python's standard library from the CDN.
    f"connect-src 'self' {JSDELIVR}",
    # No other site may show PyQuest inside a frame (clickjacking).
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
])

SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    # Browsers must use each file's declared type, never guess it, so a
    # text file can never be run as a script.
    "X-Content-Type-Options": "nosniff",
    # Older browsers' equivalent of frame-ancestors 'none'.
    "X-Frame-Options": "DENY",
    # Other sites see only which site a visitor came from, not the full
    # page address.
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # PyQuest never needs these, so no page can ask for them.
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}

# One year, including subdomains: browsers then refuse plain HTTP entirely.
HSTS_VALUE = "max-age=31536000; includeSubDomains"


def register_security_headers(app):
    """Add the security headers to every response the app sends."""

    @app.after_request
    def add_security_headers(response):
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        # Only where the site is served over HTTPS (production). Sent over
        # plain HTTP, as on a local development server, it could stop the
        # browser opening the site at all.
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault("Strict-Transport-Security", HSTS_VALUE)
        return response