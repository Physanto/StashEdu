from datetime import timedelta

from flask import Blueprint, jsonify, request

from app.errors import ErrorAPI
from app.extensions import db
from app.models import Activo, Prestamo, Usuario
from app.models.mixins import _ahora
from app.utils import obtener_json, paginar, validar_requeridos, validar_textos

prestamos_bp = Blueprint("prestamos", __name__, url_prefix="/api/v1/prestamos")

LIMITE_OBSERVACIONES = 1000


def _entero_positivo(valor, campo):
    # bool es subclase de int en Python: se descarta de forma explícita.
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
        raise ErrorAPI(f"El campo '{campo}' debe ser un entero positivo.", 400)
    return valor


def _obtener_o_404(prestamo_id, bloquear=False):
    consulta = db.select(Prestamo).where(Prestamo.id == prestamo_id)
    if bloquear:
        consulta = consulta.with_for_update()
    prestamo = db.session.scalar(consulta)
    if prestamo is None:
        raise ErrorAPI("Préstamo no encontrado.", 404)
    return prestamo


@prestamos_bp.post("")
def crear_prestamo():
    datos = obtener_json()
    validar_requeridos(datos, ("usuario_id", "activo_id"))
    usuario_id = _entero_positivo(datos["usuario_id"], "usuario_id")
    activo_id = _entero_positivo(datos["activo_id"], "activo_id")
    if datos.get("dias") is not None:
        _entero_positivo(datos["dias"], "dias")
    validar_textos(datos, {"observaciones_entrega": LIMITE_OBSERVACIONES}, ())

    # FOR UPDATE bloquea la fila del usuario hasta el commit: dos préstamos
    # simultáneos del mismo usuario se atienden en orden y el conteo de
    # préstamos abiertos no queda desactualizado.
    usuario = db.session.scalar(
        db.select(Usuario).where(Usuario.id == usuario_id).with_for_update()
    )
    if usuario is None:
        raise ErrorAPI("Usuario no encontrado.", 404)
    if db.session.get(Activo, activo_id) is None:
        raise ErrorAPI("Activo no encontrado.", 404)
    if not usuario.habilitado:
        raise ErrorAPI("El usuario está deshabilitado.", 409)

    # Reglas de negocio: los límites dependen del tipo de usuario.
    tipo = usuario.tipo_usuario
    dias = datos.get("dias") or tipo.dias_max_prestamo
    if dias > tipo.dias_max_prestamo:
        raise ErrorAPI(
            f"Un {tipo.codigo} puede pedir prestado máximo "
            f"{tipo.dias_max_prestamo} días.",
            400,
        )
    abiertos = db.session.scalar(
        db.select(db.func.count(Prestamo.id))
        .where(Prestamo.usuario_id == usuario.id, Prestamo.fecha_devolucion.is_(None))
        .with_for_update()
    )
    if abiertos >= tipo.max_prestamos_activos:
        raise ErrorAPI(
            f"El usuario ya tiene {abiertos} préstamo(s) sin devolver; el máximo "
            f"para un {tipo.codigo} es {tipo.max_prestamos_activos}.",
            409,
        )

    # El UPDATE condicional comprueba y reserva el activo en un solo paso:
    # si otra petición lo prestó antes, no cambia ninguna fila.
    reserva = db.session.execute(
        db.update(Activo)
        .where(Activo.id == activo_id, Activo.estado == "disponible")
        .values(estado="prestado")
    )
    if reserva.rowcount != 1:
        raise ErrorAPI("El activo no está disponible.", 409)

    ahora = _ahora()
    prestamo = Prestamo(
        usuario_id=usuario.id,
        activo_id=activo_id,
        fecha_prestamo=ahora,
        fecha_vencimiento=ahora + timedelta(days=dias),
        observaciones_entrega=datos.get("observaciones_entrega"),
    )
    db.session.add(prestamo)
    # Un solo commit: el préstamo y el cambio de estado del activo se guardan
    # juntos o no se guarda ninguno (si algo falla, el manejador hace rollback).
    db.session.commit()
    return jsonify(prestamo.to_dict()), 201


@prestamos_bp.get("")
def listar_prestamos():
    consulta = db.select(Prestamo).order_by(Prestamo.id)
    return jsonify(paginar(consulta, Prestamo.to_dict))


@prestamos_bp.get("/<int:prestamo_id>")
def obtener_prestamo(prestamo_id):
    return jsonify(_obtener_o_404(prestamo_id).to_dict())


@prestamos_bp.post("/<int:prestamo_id>/devolucion")
def registrar_devolucion(prestamo_id):
    # El cuerpo es opcional: solo puede traer las observaciones de la devolución.
    datos = obtener_json() if request.get_data() else {}
    validar_textos(datos, {"observaciones_devolucion": LIMITE_OBSERVACIONES}, ())

    prestamo = _obtener_o_404(prestamo_id, bloquear=True)
    if prestamo.fecha_devolucion is not None:
        raise ErrorAPI("El préstamo ya fue devuelto.", 409)

    liberacion = db.session.execute(
        db.update(Activo)
        .where(Activo.id == prestamo.activo_id, Activo.estado == "prestado")
        .values(estado="disponible")
    )
    if liberacion.rowcount != 1:
        raise ErrorAPI("El estado del activo no coincide con un préstamo vigente.", 409)

    # La fecha la pone el servidor: el cliente no puede "devolver a tiempo" a mano.
    prestamo.fecha_devolucion = _ahora()
    prestamo.observaciones_devolucion = datos.get("observaciones_devolucion")
    db.session.commit()
    return jsonify(prestamo.to_dict())
