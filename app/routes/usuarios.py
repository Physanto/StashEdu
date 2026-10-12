from flask import Blueprint, jsonify, request

from app.errors import ErrorAPI
from app.extensions import db
from app.models import Usuario
from app.models.usuario import TIPOS_USUARIO
from app.utils import (
    obtener_json,
    paginar,
    validar_email,
    validar_opcion,
    validar_requeridos,
    validar_textos,
)

usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/api/v1/usuarios")

REQUERIDOS = ("nombre_completo", "documento", "email", "tipo_usuario")
EDITABLES = REQUERIDOS + ("telefono", "activo")


def _obtener_o_404(usuario_id):
    usuario = db.session.get(Usuario, usuario_id)
    if usuario is None:
        raise ErrorAPI("Usuario no encontrado.", 404)
    return usuario


def _validar(datos):
    validar_textos(
        datos,
        {
            "nombre_completo": 120,
            "documento": 20,
            "email": 120,
            "telefono": 20,
            "tipo_usuario": 20,
        },
        REQUERIDOS,
    )
    if "email" in datos:
        validar_email(datos["email"])
    if "tipo_usuario" in datos:
        validar_opcion(datos["tipo_usuario"], TIPOS_USUARIO, "tipo_usuario")
    if "activo" in datos and not isinstance(datos["activo"], bool):
        raise ErrorAPI("El campo 'activo' debe ser true o false.", 400)


def _validar_unicos(datos, excluir_id=None):
    for campo in ("documento", "email"):
        if campo in datos:
            existente = db.session.scalars(
                db.select(Usuario).filter_by(**{campo: datos[campo]})
            ).first()
            if existente and existente.id != excluir_id:
                raise ErrorAPI(f"Ya existe un usuario con ese {campo}.", 409)


@usuarios_bp.post("")
def crear_usuario():
    datos = obtener_json()
    validar_requeridos(datos, REQUERIDOS)
    _validar(datos)
    _validar_unicos(datos)

    usuario = Usuario(**{c: datos[c] for c in EDITABLES if c in datos})
    db.session.add(usuario)
    db.session.commit()
    return jsonify(usuario.to_dict()), 201


@usuarios_bp.get("")
def listar_usuarios():
    consulta = db.select(Usuario).order_by(Usuario.id)
    return jsonify(paginar(consulta, Usuario.to_dict))


@usuarios_bp.get("/<int:usuario_id>")
def obtener_usuario(usuario_id):
    return jsonify(_obtener_o_404(usuario_id).to_dict())


@usuarios_bp.route("/<int:usuario_id>", methods=["PUT", "PATCH"])
def actualizar_usuario(usuario_id):
    usuario = _obtener_o_404(usuario_id)
    datos = obtener_json()
    if request.method == "PUT":
        validar_requeridos(datos, REQUERIDOS)
    _validar(datos)
    _validar_unicos(datos, excluir_id=usuario.id)

    for campo in EDITABLES:
        if campo in datos:
            setattr(usuario, campo, datos[campo])
    db.session.commit()
    return jsonify(usuario.to_dict())


@usuarios_bp.delete("/<int:usuario_id>")
def desactivar_usuario(usuario_id):
    """Baja lógica: conserva el registro para no romper el historial futuro."""
    usuario = _obtener_o_404(usuario_id)
    usuario.activo = False
    db.session.commit()
    return "", 204
