"""Flask application and JSON API for the local MST visualization web app."""

from __future__ import annotations

import logging
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from flask import Flask, current_app, jsonify, render_template, request
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from gmlst.visual.api_routes import api_bp

_WELL_KNOWN_PREFIX = "/.well-known/"
_MAX_CONTENT_LENGTH = 32 * 1024 * 1024


class _QuietNotFoundFilter(logging.Filter):
    """Suppress Werkzeug request logs for well-known browser probes and 404s."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Keep the log line only when it is not a well-known probe request."""
        return _WELL_KNOWN_PREFIX not in record.getMessage()


def _json_http_error(exc: HTTPException) -> tuple[Any, int]:
    """Render HTTP-level errors (404/405/413/...) as JSON instead of HTML."""
    return jsonify({"error": exc.description or exc.name}), exc.code or 500


def _reject_oversized_bodies() -> None:
    """Reject bodies above MAX_CONTENT_LENGTH before any view reads them.

    Werkzeug raises 413 lazily when the body stream is first read, which
    would surface inside the routes' JSON-body parsing as a 400/500;
    checking Content-Length up front keeps oversized requests an
    HTTP-level 413 rendered as JSON by the app-wide error handler.
    """
    max_length = current_app.config["MAX_CONTENT_LENGTH"]
    content_length = request.content_length
    if max_length is None or content_length is None:
        return None
    if content_length > max_length:
        raise RequestEntityTooLarge()
    return None


def _enforce_same_origin() -> tuple[Any, int] | None:
    if request.method not in ("POST", "PUT", "DELETE", "PATCH"):
        return None
    origin = request.headers.get("Origin")
    referer = request.headers.get("Referer")
    # Validate Host against allowlist (defends against DNS rebinding,
    # where an attacker's Host header would otherwise match Origin).
    host = request.host.lower()
    allowed_hosts = {"127.0.0.1", "localhost", "[::1]"}
    host_name = host.split(":")[0] if ":" in host else host
    if host_name not in allowed_hosts:
        # Non-loopback binding: require exact Origin match against
        # the actual request Host (still better than no check).
        current_app.logger.warning(
            "Request to non-loopback host %r — CSRF check relies on Host header trust",
            host,
        )
    host_url = request.host_url.rstrip("/")
    if origin is not None and origin.rstrip("/") != host_url:
        return jsonify({"error": "Cross-origin requests are not allowed"}), 403
    if origin is None and referer is not None:
        parsed = urlparse(referer)
        if f"{parsed.scheme}://{parsed.netloc}" != host_url:
            return jsonify({"error": "Cross-origin requests are not allowed"}), 403
    return None


def _set_security_headers(response: Any) -> Any:
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'"
    )
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


def create_visual_app(*, title: str) -> Flask:
    """Create the visualization Flask app serving the Vue UI and JSON API.

    Installs same-origin protection for state-changing requests, security
    headers, a 32 MB upload cap, and the /api/* routes from
    :mod:`gmlst.visual.api_routes`.
    """
    web_root = Path(__file__).resolve().parents[1] / "web"
    app = Flask(
        "gmlst_visual",
        template_folder=str(web_root / "templates"),
        static_folder=str(web_root / "static"),
        static_url_path="/static",
    )
    app.config["GMLST_VISUAL_TITLE"] = title
    app.config["MAX_CONTENT_LENGTH"] = _MAX_CONTENT_LENGTH
    app.config["SECRET_KEY"] = secrets.token_urlsafe(32)

    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.addFilter(_QuietNotFoundFilter())

    app.register_error_handler(HTTPException, _json_http_error)
    app.before_request(_reject_oversized_bodies)
    app.before_request(_enforce_same_origin)
    app.after_request(_set_security_headers)

    @app.get("/")
    def index() -> str:
        """Serve the single-page visualization UI."""
        return render_template(
            "visual/index.html",
            title=app.config["GMLST_VISUAL_TITLE"],
        )

    @app.route("/.well-known/<path:subpath>")
    def well_known_catch(subpath: str) -> tuple[str, int]:
        """Swallow browser well-known probes with an empty 204 response."""
        return "", 204

    @app.get("/health")
    def health() -> tuple[dict[str, str], int]:
        """Liveness endpoint returning ``{"status": "ok"}``."""
        return {"status": "ok"}, 200

    app.register_blueprint(api_bp)

    return app
