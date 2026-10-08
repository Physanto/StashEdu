from flask import Blueprint, g, jsonify, request

from app.auth import autenticar, es_operador, exigir_operador, exigir_propietario
from app.errors import ErrorAPI
from app.extensions import db
from app.models import Prestamo, Usuario
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
usuarios_bp.before_request(autenticar)

REQUERIDOS = ("nombre_completo", "documento", "email", "tipo_usuario")
EDITABLES = REQUERIDOS + ("telefono", "activo")


def _obtener_o_404(usuario_id):
    usuario = db.session.scalar(
        db.select(Usuario)
        .where(Usuario.id == usuario_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if usuario is None:
        raise ErrorAPI("Usuario no encontrado.", 404)
    return usuario


def _validar(datos):
    if isinstance(datos.get("email"), str):
        datos["email"] = datos["email"].lower()
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


def _validar_desactivacion(usuario):
    pendiente = db.session.scalar(
        db.select(Prestamo.id)
        .where(Prestamo.usuario_id == usuario.id, Prestamo.fecha_devolucion.is_(None))
        .limit(1)
        .with_for_update()
    )
    if pendiente:
        raise ErrorAPI("El usuario tiene préstamos pendientes de devolución.", 409)


@usuarios_bp.post("")
def crear_usuario():
    exigir_operador()
    datos = obtener_json(EDITABLES)
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
    if not es_operador():
        consulta = consulta.where(Usuario.id == g.usuario.id)
    return jsonify(paginar(consulta, Usuario.to_dict))


@usuarios_bp.get("/<int:usuario_id>")
def obtener_usuario(usuario_id):
    exigir_propietario(usuario_id)
    return jsonify(_obtener_o_404(usuario_id).to_dict())


@usuarios_bp.route("/<int:usuario_id>", methods=["PUT", "PATCH"])
def actualizar_usuario(usuario_id):
    exigir_propietario(usuario_id)
    usuario = _obtener_o_404(usuario_id)
    datos = obtener_json(EDITABLES, no_vacio=request.method == "PATCH")
    if request.method == "PUT":
        validar_requeridos(datos, REQUERIDOS)
    _validar(datos)
    _validar_unicos(datos, excluir_id=usuario.id)
    if datos.get("activo") is False:
        _validar_desactivacion(usuario)

    for campo in EDITABLES:
        if campo in datos:
            setattr(usuario, campo, datos[campo])
    db.session.commit()
    return jsonify(usuario.to_dict())


@usuarios_bp.delete("/<int:usuario_id>")
def desactivar_usuario(usuario_id):
    exigir_propietario(usuario_id)
    """Baja lógica: conserva el registro para no romper el historial futuro."""
    usuario = _obtener_o_404(usuario_id)
    _validar_desactivacion(usuario)
    usuario.activo = False
    db.session.commit()
    return "", 204
