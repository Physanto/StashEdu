from flask import jsonify
from sqlalchemy.exc import IntegrityError, OperationalError
from werkzeug.exceptions import HTTPException

from app.extensions import db


class ErrorAPI(Exception):
    """Error controlado de la API con código HTTP y detalles opcionales."""

    def __init__(self, mensaje, codigo=400, detalles=None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo
        self.detalles = detalles


CODIGOS_CHECK = (3819, 4025)  # violación de CHECK: MySQL 3819, MariaDB 4025


def _codigo_mysql(error):
    return getattr(error.orig, "args", (None,))[0]


def _respuesta_restriccion(codigo):
    """Traduce el código de error de una restricción SQL a (respuesta, HTTP); None si no aplica."""
    if codigo == 1062:  # UNIQUE
        return {"error": "Ya existe un registro con ese valor único."}, 409
    if codigo == 1451:  # FK: otro registro depende de este
        return {"error": "El registro tiene datos relacionados."}, 409
    if codigo == 1452:  # FK: el registro referenciado no existe
        return {"error": "Referencia a un registro que no existe."}, 400
    if codigo in CODIGOS_CHECK:
        return {"error": "Los datos incumplen una restricción."}, 400
    return None


def registrar_errores(app):
    @app.errorhandler(IntegrityError)
    def manejar_integridad(error):
        db.session.rollback()
        # Las restricciones SQL son la última defensa: protegen incluso ante
        # peticiones concurrentes o si se salta la validación de la API.
        traducido = _respuesta_restriccion(_codigo_mysql(error))
        if traducido:
            cuerpo, codigo_http = traducido
            return jsonify(cuerpo), codigo_http
        app.logger.exception("Error de integridad de la base de datos.")
        return jsonify({"error": "Error interno del servidor."}), 500

    @app.errorhandler(OperationalError)
    def manejar_conexion(error):
        db.session.rollback()
        # MariaDB reporta la violación de un CHECK como OperationalError (no como
        # IntegrityError): se distingue por su código para no responder "BD caída".
        if _codigo_mysql(error) in CODIGOS_CHECK:
            cuerpo, codigo_http = _respuesta_restriccion(_codigo_mysql(error))
            return jsonify(cuerpo), codigo_http
        app.logger.exception("Error operativo de la base de datos.")
        return jsonify({"error": "La base de datos no está disponible."}), 503

    @app.errorhandler(ErrorAPI)
    def manejar_error_api(error):
        cuerpo = {"error": error.mensaje}
        if error.detalles:
            cuerpo["detalles"] = error.detalles
        return jsonify(cuerpo), error.codigo

    @app.errorhandler(HTTPException)
    def manejar_http(error):
        respuesta = error.get_response()
        respuesta.data = app.json.dumps({"error": error.description})
        respuesta.content_type = "application/json"
        return respuesta

    @app.errorhandler(Exception)
    def manejar_inesperado(error):
        db.session.rollback()
        app.logger.exception(error)
        return jsonify({"error": "Error interno del servidor."}), 500
