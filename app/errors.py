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


def registrar_errores(app):
    @app.errorhandler(IntegrityError)
    def manejar_integridad(error):
        db.session.rollback()
        # La restricción SQL también protege ante creaciones concurrentes.
        if getattr(error.orig, "args", (None,))[0] == 1062:
            return jsonify({"error": "Ya existe un registro con ese valor único."}), 409
        app.logger.exception("Error de integridad de la base de datos.")
        return jsonify({"error": "Error interno del servidor."}), 500

    @app.errorhandler(OperationalError)
    def manejar_conexion(error):
        db.session.rollback()
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
