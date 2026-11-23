from flask import Blueprint, jsonify

from app.auth import autorizar_por_metodo
from app.extensions import db
from app.models import Rol, TipoUsuario
from app.utils import validar_parametros

catalogos_bp = Blueprint("catalogos", __name__, url_prefix="/api/v1")
# Catálogos de solo lectura: cualquier cuenta autenticada.
catalogos_bp.before_request(autorizar_por_metodo)
catalogos_bp.before_request(validar_parametros)


@catalogos_bp.get("/tipos-usuario")
def listar_tipos_usuario():
    """Solo lectura: permite saber qué tipo_usuario_id enviar al crear un usuario."""
    tipos = db.session.scalars(db.select(TipoUsuario).order_by(TipoUsuario.id))
    return jsonify({"data": [t.to_dict() for t in tipos]})


@catalogos_bp.get("/roles")
def listar_roles():
    """Solo lectura: permite saber qué rol_id enviar en POST /auth/register."""
    roles = db.session.scalars(db.select(Rol).order_by(Rol.id))
    return jsonify({"data": [r.to_dict() for r in roles]})
