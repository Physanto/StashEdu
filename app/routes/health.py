import pymysql
from flask import Blueprint, jsonify

from app.db import get_connection

health_bp = Blueprint("health", __name__, url_prefix="/api/v1")


@health_bp.get("/health")
def health():
    try:
        conexion = get_connection()
        try:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT 1")
        finally:
            conexion.close()
        return jsonify({"status": "ok", "database": "connected"})
    except pymysql.MySQLError:
        return jsonify({"status": "error", "database": "unreachable"}), 503
