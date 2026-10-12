from flask import Blueprint, jsonify, request

from app.errors import ErrorAPI
from app.extensions import db
from app.models import TipoUsuario, Usuario
from app.utils import (
    filtro_booleano,
    filtro_entero,
    obtener_json,
    paginar,
    validar_email,
    validar_requeridos,
    validar_textos,
)

usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/api/v1/usuarios")

REQUERIDOS = ("nombre_completo", "documento", "email", "tipo_usuario_id")
EDITABLES = REQUERIDOS + ("telefono", "habilitado")


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
        },
        REQUERIDOS,
    )
    if "email" in datos:
        validar_email(datos["email"])
    if "tipo_usuario_id" in datos:
        tipo_id = datos["tipo_usuario_id"]
        # bool es subclase de int en Python: se descarta de forma explícita.
        if (
            isinstance(tipo_id, bool)
            or not isinstance(tipo_id, int)
            or db.session.get(TipoUsuario, tipo_id) is None
        ):
            raise ErrorAPI(
                "tipo_usuario_id no corresponde a un tipo de usuario existente "
                "(consulte GET /api/v1/tipos-usuario).",
                400,
            )
    if "habilitado" in datos and not isinstance(datos["habilitado"], bool):
        raise ErrorAPI("El campo 'habilitado' debe ser true o false.", 400)


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
    tipo_usuario_id = filtro_entero("tipo_usuario_id")
    if tipo_usuario_id is not None:
        consulta = consulta.where(Usuario.tipo_usuario_id == tipo_usuario_id)
    habilitado = filtro_booleano("habilitado")
    if habilitado is not None:
        consulta = consulta.where(Usuario.habilitado == habilitado)
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
def deshabilitar_usuario(usuario_id):
    """Baja lógica: conserva el registro para no romper el historial de préstamos."""
    usuario = _obtener_o_404(usuario_id)
    usuario.habilitado = False
    db.session.commit()
    return "", 204
