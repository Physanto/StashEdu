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
# Dos transacciones chocaron (fila cambiada, interbloqueo o espera agotada):
# es un conflicto que el cliente puede reintentar, no una base de datos caída.
CODIGOS_CONCURRENCIA = (1020, 1205, 1213)
# SQLite (las pruebas) usa otros códigos para lo mismo: se traducen a los de MySQL.
SQLITE_A_MYSQL = {2067: 1062, 1555: 1062, 275: 3819}

# Mensajes de los errores que genera Flask/Werkzeug (ruta inexistente, método no
# permitido, cuerpo demasiado grande...): en español y con el mismo formato JSON.
MENSAJES_HTTP = {
    400: "Petición inválida.",
    401: "Se requiere autenticación.",
    403: "No tienes permiso para realizar esta operación.",
    404: "Recurso no encontrado.",
    405: "Método no permitido para este recurso.",
    413: "El cuerpo de la petición supera el tamaño máximo permitido.",
    415: "El Content-Type debe ser application/json.",
    429: "Demasiadas peticiones.",
    500: "Error interno del servidor.",
}


def _codigo_mysql(error):
    orig = getattr(error, "orig", None)
    sqlite = getattr(orig, "sqlite_errorcode", None)
    if sqlite is not None:
        return SQLITE_A_MYSQL.get(sqlite)
    return getattr(orig, "args", (None,))[0]


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
        if _codigo_mysql(error) in CODIGOS_CONCURRENCIA:
            app.logger.warning("Conflicto de concurrencia: %s", error.orig)
            mensaje = "Otra operación modificó estos datos al mismo tiempo; intente de nuevo."
            return jsonify({"error": mensaje}), 409
        app.logger.exception("Error operativo de la base de datos.")
        return jsonify({"error": "La base de datos no está disponible."}), 503

    @app.errorhandler(ErrorAPI)
    def manejar_error_api(error):
        db.session.rollback()
        cuerpo = {"error": error.mensaje}
        if error.detalles:
            cuerpo["detalles"] = error.detalles
        respuesta = jsonify(cuerpo)
        respuesta.status_code = error.codigo
        if error.codigo == 401:
            respuesta.headers["WWW-Authenticate"] = "Bearer"
        return respuesta

    @app.errorhandler(HTTPException)
    def manejar_http(error):
        # get_response conserva los headers propios del error (p. ej. Allow en el 405).
        respuesta = error.get_response()
        mensaje = MENSAJES_HTTP.get(error.code, "La petición no se pudo procesar.")
        respuesta.data = app.json.dumps({"error": mensaje})
        respuesta.content_type = "application/json"
        if error.code == 401:
            respuesta.headers["WWW-Authenticate"] = "Bearer"
        return respuesta

    @app.errorhandler(Exception)
    def manejar_inesperado(error):
        db.session.rollback()
        app.logger.exception(error)
        return jsonify({"error": "Error interno del servidor."}), 500
