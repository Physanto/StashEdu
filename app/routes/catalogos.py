from flask import Blueprint, jsonify

from app.extensions import db
from app.models import TipoUsuario

catalogos_bp = Blueprint("catalogos", __name__, url_prefix="/api/v1")


@catalogos_bp.get("/tipos-usuario")
def listar_tipos_usuario():
    """Solo lectura: permite saber qué tipo_usuario_id enviar al crear un usuario."""
    tipos = db.session.scalars(db.select(TipoUsuario).order_by(TipoUsuario.id))
    return jsonify({"data": [t.to_dict() for t in tipos]})
