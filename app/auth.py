import hashlib
from functools import lru_cache

from flask import current_app, g, request
from itsdangerous import BadData, URLSafeTimedSerializer

from app.errors import ErrorAPI
from app.extensions import db
from app.models import Usuario
from app.security import hash_password


def _serializer():
    key = current_app.config.get("SECRET_KEY")
    if not isinstance(key, str) or len(key) < 32:
        raise ErrorAPI(
            "La autenticación requiere configurar SECRET_KEY con al menos 32 caracteres.",
            503,
        )
    return URLSafeTimedSerializer(
        key, salt="stashedu-auth-v1", signer_kwargs={"digest_method": hashlib.sha256}
    )


def _version(usuario):
    return hashlib.sha256((usuario.password_hash or "").encode()).hexdigest()


def emitir_token(usuario):
    return _serializer().dumps({"usuario_id": usuario.id, "version": _version(usuario)})


@lru_cache(maxsize=1)
def dummy_hash():
    # Mismo coste de verificación aunque el email no exista.
    return hash_password("dummy-password-for-timing-only")


def autenticar():
    partes = request.headers.get("Authorization", "").split()
    if len(partes) != 2 or partes[0].lower() != "bearer":
        raise ErrorAPI("Se requiere un token Bearer válido.", 401)
    try:
        datos = _serializer().loads(
            partes[1], max_age=current_app.config["AUTH_TOKEN_MAX_AGE"]
        )
    except BadData:
        raise ErrorAPI("Token inválido o expirado.", 401)
    if not isinstance(datos, dict) or type(datos.get("usuario_id")) is not int:
        raise ErrorAPI("Token inválido.", 401)
    usuario = db.session.get(Usuario, datos["usuario_id"])
    if (
        usuario is None
        or not usuario.activo
        or not usuario.password_hash
        or datos.get("version") != _version(usuario)
    ):
        raise ErrorAPI("Token inválido o usuario inactivo.", 401)
    g.usuario = usuario


def es_operador():
    return g.usuario.id in current_app.config.get("API_OPERATOR_IDS", ())


def exigir_operador():
    if not es_operador():
        raise ErrorAPI("Esta operación requiere un operador autorizado.", 403)


def exigir_propietario(usuario_id):
    if g.usuario.id != usuario_id and not es_operador():
        raise ErrorAPI("No tienes permiso para acceder a otro usuario.", 403)
