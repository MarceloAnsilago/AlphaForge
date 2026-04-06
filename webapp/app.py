from __future__ import annotations

import os
from typing import Any

from flask import Flask, redirect, url_for

from webapp.backend import get_web_backend_context
from webapp.routes.builder import bp as builder_bp
from webapp.routes.pages import bp as pages_bp


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "alphaforge-local-secret")
    app.register_blueprint(builder_bp)
    app.register_blueprint(pages_bp)

    @app.context_processor
    def inject_layout_context() -> dict[str, Any]:
        backend = get_web_backend_context()
        return {
            "sidebar_links": [
                {"endpoint": "builder.builder_page", "label": "Builder"},
                {"endpoint": "pages.campaigns_page", "label": "Campanhas"},
            ],
            "backend_status": backend.backend_status,
            "backend_mode": backend.backend_mode,
        }

    @app.get("/")
    def home() -> Any:
        return redirect(url_for("builder.builder_page"))

    return app
