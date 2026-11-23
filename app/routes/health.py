from flask import Blueprint, jsonify
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.utils import validar_parametros

health_bp = Blueprint("health", __name__, url_prefix="/api/v1")
health_bp.before_request(validar_parametros)


@health_bp.get("/health")
def health():
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify({"status": "ok", "database": "connected"})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"status": "error", "database": "unreachable"}), 503
