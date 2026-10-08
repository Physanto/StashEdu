import re
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify

from app.auth import autenticar, es_operador, exigir_propietario
from app.errors import ErrorAPI
from app.extensions import db
from app.models import Activo, Prestamo, Usuario
from app.models.mixins import _ahora
from app.utils import obtener_json, paginar, validar_requeridos, validar_textos

prestamos_bp = Blueprint("prestamos", __name__, url_prefix="/api/v1/prestamos")
prestamos_bp.before_request(autenticar)


def _id(valor, campo):
    if type(valor) is not int or valor < 1:
        raise ErrorAPI(f"'{campo}' debe ser un entero positivo.")
    return valor


def _fecha(valor):
    try:
        if not isinstance(valor, str) or not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})",
            valor,
        ):
            raise ValueError
        fecha = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        if fecha.tzinfo is None:
            raise ValueError
        return fecha.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError, TypeError, OverflowError):
        raise ErrorAPI(
            "fecha_devolucion_prevista debe ser una fecha ISO 8601 con zona horaria."
        )


@prestamos_bp.post("")
def crear_prestamo():
    datos = obtener_json(
        ("usuario_id", "activo_id", "fecha_devolucion_prevista", "observaciones")
    )
    validar_requeridos(datos, ("usuario_id", "activo_id", "fecha_devolucion_prevista"))
    usuario_id = _id(datos["usuario_id"], "usuario_id")
    exigir_propietario(usuario_id)
    activo_id = _id(datos["activo_id"], "activo_id")
    prevista = _fecha(datos["fecha_devolucion_prevista"])
    validar_textos(datos, {"observaciones": 1000}, ())
    ahora = _ahora()
    if prevista <= ahora:
        raise ErrorAPI(
            "La devolución prevista debe ser posterior al momento del préstamo."
        )
    usuario = db.session.scalar(
        db.select(Usuario)
        .where(Usuario.id == usuario_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if usuario is None:
        raise ErrorAPI("Usuario no encontrado.", 404)
    if not usuario.activo:
        raise ErrorAPI("El usuario está inactivo.", 409)
    # La actualización condicional reserva el activo y serializa préstamos concurrentes.
    reserva = db.session.execute(
        db.update(Activo)
        .where(Activo.id == activo_id, Activo.estado == "disponible")
        .values(estado="prestado")
    )
    if reserva.rowcount != 1:
        existe = db.session.get(Activo, activo_id)
        raise ErrorAPI(
            "Activo no encontrado."
            if existe is None
            else "El activo no está disponible.",
            404 if existe is None else 409,
        )
    ahora = _ahora()
    if prevista <= ahora:
        raise ErrorAPI("La devolución prevista venció mientras se reservaba el activo.")
    prestamo = Prestamo(
        usuario_id=usuario_id,
        activo_id=activo_id,
        fecha_prestamo=ahora,
        fecha_devolucion_prevista=prevista,
        observaciones=datos.get("observaciones"),
    )
    db.session.add(prestamo)
    db.session.commit()
    return jsonify(prestamo.to_dict()), 201


@prestamos_bp.get("")
def listar_prestamos():
    consulta = db.select(Prestamo).order_by(Prestamo.id)
    if not es_operador():
        consulta = consulta.where(Prestamo.usuario_id == g.usuario.id)
    return jsonify(paginar(consulta, Prestamo.to_dict))


@prestamos_bp.get("/<int:prestamo_id>")
def obtener_prestamo(prestamo_id):
    prestamo = db.session.get(Prestamo, prestamo_id)
    if prestamo is None:
        raise ErrorAPI("Préstamo no encontrado.", 404)
    exigir_propietario(prestamo.usuario_id)
    return jsonify(prestamo.to_dict())


@prestamos_bp.post("/<int:prestamo_id>/devolucion")
def registrar_devolucion(prestamo_id):
    # El cuerpo vacío no es necesario: usar {} permite extender el contrato después.
    datos = obtener_json(())
    if datos:
        raise ErrorAPI("La devolución solo acepta un objeto JSON vacío.")
    prestamo = db.session.scalar(
        db.select(Prestamo)
        .where(Prestamo.id == prestamo_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if prestamo is None:
        raise ErrorAPI("Préstamo no encontrado.", 404)
    exigir_propietario(prestamo.usuario_id)
    if prestamo.fecha_devolucion is not None:
        raise ErrorAPI("El préstamo ya fue devuelto.", 409)
    liberacion = db.session.execute(
        db.update(Activo)
        .where(Activo.id == prestamo.activo_id, Activo.estado == "prestado")
        .values(estado="disponible")
    )
    if liberacion.rowcount != 1:
        raise ErrorAPI("El estado del activo no coincide con un préstamo vigente.", 409)
    prestamo.fecha_devolucion = max(_ahora(), prestamo.fecha_prestamo)
    db.session.commit()
    return jsonify(prestamo.to_dict())
