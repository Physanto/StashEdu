from flask import Blueprint, jsonify, request

from app.errors import ErrorAPI
from app.extensions import db
from app.models import Activo
from app.models.activo import CATEGORIAS, ESTADOS, ESTADOS_EDITABLES
from app.utils import (
    filtro_opcion,
    obtener_json,
    paginar,
    validar_opcion,
    validar_requeridos,
    validar_textos,
)

activos_bp = Blueprint("activos", __name__, url_prefix="/api/v1/activos")

REQUERIDOS = ("codigo_inventario", "nombre", "categoria")
EDITABLES = REQUERIDOS + ("marca", "modelo", "numero_serie", "estado")


def _obtener_o_404(activo_id):
    activo = db.session.scalar(db.select(Activo).where(Activo.id == activo_id).with_for_update().execution_options(populate_existing=True))
    if activo is None:
        raise ErrorAPI("Activo no encontrado.", 404)
    return activo


def _validar(datos):
    validar_textos(
        datos,
        {
            "codigo_inventario": 30,
            "nombre": 100,
            "categoria": 30,
            "marca": 60,
            "modelo": 60,
            "numero_serie": 60,
            "estado": 20,
        },
        REQUERIDOS + ("estado",),
    )
    if "categoria" in datos:
        validar_opcion(datos["categoria"], CATEGORIAS, "categoria")
    if "estado" in datos:
        validar_opcion(datos["estado"], ESTADOS_EDITABLES, "estado")


def _validar_unicos(datos, excluir_id=None):
    for campo in ("codigo_inventario", "numero_serie"):
        if datos.get(campo):
            existente = db.session.scalars(
                db.select(Activo).filter_by(**{campo: datos[campo]})
            ).first()
            if existente and existente.id != excluir_id:
                raise ErrorAPI(f"Ya existe un activo con ese {campo}.", 409)


@activos_bp.post("")
def crear_activo():
    datos = obtener_json()
    validar_requeridos(datos, REQUERIDOS)
    _validar(datos)
    _validar_unicos(datos)

    activo = Activo(**{c: datos[c] for c in EDITABLES if c in datos})
    db.session.add(activo)
    db.session.commit()
    return jsonify(activo.to_dict()), 201


@activos_bp.get("")
def listar_activos():
    consulta = db.select(Activo).order_by(Activo.id)
    # Aquí el filtro por estado sí acepta "prestado": es una búsqueda, no una edición.
    estado = filtro_opcion("estado", ESTADOS)
    if estado is not None:
        consulta = consulta.where(Activo.estado == estado)
    categoria = filtro_opcion("categoria", CATEGORIAS)
    if categoria is not None:
        consulta = consulta.where(Activo.categoria == categoria)
    return jsonify(paginar(consulta, Activo.to_dict))


@activos_bp.get("/<int:activo_id>")
def obtener_activo(activo_id):
    return jsonify(_obtener_o_404(activo_id).to_dict())


@activos_bp.route("/<int:activo_id>", methods=["PUT", "PATCH"])
def actualizar_activo(activo_id):
    activo = _obtener_o_404(activo_id)
    datos = obtener_json()
    if request.method == "PUT":
        validar_requeridos(datos, REQUERIDOS)
    _validar(datos)
    _validar_unicos(datos, excluir_id=activo.id)

    if activo.estado == "prestado" and "estado" in datos:
        raise ErrorAPI("Un activo prestado solo cambia de estado mediante una devolución.", 409)

    for campo in EDITABLES:
        if campo in datos:
            setattr(activo, campo, datos[campo])
    db.session.commit()
    return jsonify(activo.to_dict())


@activos_bp.delete("/<int:activo_id>")
def dar_de_baja_activo(activo_id):
    """Baja lógica: el activo queda con estado 'baja'."""
    activo = _obtener_o_404(activo_id)
    if activo.estado == "prestado":
        raise ErrorAPI("No se puede dar de baja un activo prestado.", 409)
    activo.estado = "baja"
    db.session.commit()
    return "", 204
