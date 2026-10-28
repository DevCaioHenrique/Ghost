"""GHOST — ponto de entrada. Uso: python app.py"""
import os
from flask import Flask, g, jsonify, send_from_directory
from backend.database import init_db, connect
from backend.api import bp
from backend.validation import ValidationError, NotFound, Conflict

FRONTEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")


def create_app(db_path=None):
    app = Flask(__name__, static_folder=None)
    init_db(db_path).close()

    @app.before_request
    def open_db():
        g.db = connect(db_path)

    @app.teardown_request
    def close_db(_):
        db = g.pop("db", None)
        if db:
            db.close()

    @app.errorhandler(ValidationError)
    def _422(e):
        return jsonify(error=str(e), fields=e.fields), 422

    @app.errorhandler(NotFound)
    def _404(e):
        return jsonify(error=str(e)), 404

    @app.errorhandler(Conflict)
    def _409(e):
        return jsonify(error=str(e), details=e.details, needs_confirmation=True), 409

    @app.errorhandler(Exception)
    def _500(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return jsonify(error=e.description), e.code
        app.logger.exception("Erro interno")
        return jsonify(error="Erro interno. Consulte o terminal."), 500

    app.register_blueprint(bp)

    @app.get("/")
    def index():
        if os.path.exists(os.path.join(FRONTEND, "index.html")):
            return send_from_directory(FRONTEND, "index.html")
        return jsonify(status="GHOST backend ativo", frontend="ainda não implementado (etapa 3)")

    @app.get("/<path:p>")
    def static_files(p):
        return send_from_directory(FRONTEND, p)

    return app


if __name__ == "__main__":
    print("GHOST iniciado em http://127.0.0.1:5000  (Ctrl+C para encerrar)")
    create_app().run(host="127.0.0.1", port=5000, debug=False)
