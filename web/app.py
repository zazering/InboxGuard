"""Flask web dashboard factory."""

from flask import Flask, jsonify, render_template, request


def create_app(config, db):
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    # ── Pages ─────────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        return render_template("index.html")

    # ── JSON API ──────────────────────────────────────────────────────────

    @app.route("/api/emails")
    def api_emails():
        action = request.args.get("action", "all")
        limit  = int(request.args.get("limit", 60))
        return jsonify(db.get_recent(limit=limit, action=action))

    @app.route("/api/stats")
    def api_stats():
        return jsonify(db.get_stats())

    @app.route("/api/config")
    def api_config():
        """Return non-sensitive config info for the UI."""
        return jsonify({
            "llm": {
                "model":      config.get("llm.model"),
                "ollama_url": config.get("llm.ollama_url"),
            },
            "email": {
                "check_interval": config.get("email.check_interval"),
                "folder":         config.get("email.folder", "INBOX"),
                "imap_server":    config.get("email.imap_server"),
            },
            "rules": config.get("rules", {}),
        })

    @app.route("/api/health")
    def api_health():
        from src.llm_client import LLMClient
        llm = LLMClient(config)
        return jsonify({
            "ollama": llm.is_available(),
            "model":  llm.model_is_pulled(),
            "stats":  db.get_stats(),
        })

    return app
