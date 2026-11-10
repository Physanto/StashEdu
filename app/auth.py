"""Autenticación con JWT y autorización por roles.

Permisos (contrato de la Fase 3):
    admin     -> todo
    operador  -> ver todo; crear/editar usuarios y activos; crear/devolver préstamos
    consulta  -> solo GET
Sin token -> 401. Con token pero sin permiso -> 403.
"""

import hashlib
from datetime import datetime, timedelta, timezone
from functools import lru_cache, wraps

import jwt
from flask import current_app, g, request

from app.errors import ErrorAPI
from app.extensions import db
from app.models import Usuario
from app.models.rol import ROL_ADMIN, ROL_CONSULTA, ROL_OPERADOR
from app.security import hash_password

ALGORITMO = "HS256"
METODOS_LECTURA = ("GET", "HEAD", "OPTIONS")

# Roles que pueden usar cada método HTTP en los recursos protegidos.
PERMISOS_POR_METODO = {
    "GET": (ROL_ADMIN, ROL_OPERADOR, ROL_CONSULTA),
    "HEAD": (ROL_ADMIN, ROL_OPERADOR, ROL_CONSULTA),
    "OPTIONS": (ROL_ADMIN, ROL_OPERADOR, ROL_CONSULTA),
    "POST": (ROL_ADMIN, ROL_OPERADOR),
    "PUT": (ROL_ADMIN, ROL_OPERADOR),
    "PATCH": (ROL_ADMIN, ROL_OPERADOR),
    "DELETE": (ROL_ADMIN,),
}


def _clave():
    clave = current_app.config.get("SECRET_KEY")
    if not isinstance(clave, str) or len(clave) < 32:
        raise ErrorAPI(
            "La autenticación requiere configurar SECRET_KEY con al menos 32 caracteres.",
            503,
        )
    return clave


def _version(usuario):
    """Huella del hash actual: al cambiar la contraseña, los tokens anteriores dejan de valer."""
    return hashlib.sha256((usuario.password_hash or "").encode()).hexdigest()[:16]


def emitir_token(usuario, ahora=None):
    """Firma un JWT (HS256) para una cuenta con rol y contraseña."""
    ahora = ahora or datetime.now(timezone.utc)
    duracion = timedelta(seconds=current_app.config["AUTH_TOKEN_MAX_AGE"])
    claims = {
        "sub": str(usuario.id),  # el estándar exige que "sub" sea texto
        "rol": usuario.rol.codigo,
        "ver": _version(usuario),
        "iat": ahora,
        "exp": ahora + duracion,
    }
    return jwt.encode(claims, _clave(), algorithm=ALGORITMO)


@lru_cache(maxsize=1)
def dummy_hash():
    # Mismo coste de verificación aunque el email no exista.
    return hash_password("dummy-password-for-timing-only")


def autenticar():
    """Valida el header Authorization: Bearer <jwt> y deja la cuenta en g.usuario."""
    partes = request.headers.get("Authorization", "").split()
    if len(partes) != 2 or partes[0].lower() != "bearer":
        raise ErrorAPI("Se requiere un token Bearer válido.", 401)
    try:
        # algorithms fija HS256: un token con "alg": "none" u otro algoritmo se rechaza.
        claims = jwt.decode(
            partes[1],
            _clave(),
            algorithms=[ALGORITMO],
            options={"require": ["sub", "exp", "iat"]},
        )
    except jwt.ExpiredSignatureError:
        raise ErrorAPI("El token expiró; inicia sesión de nuevo.", 401)
    except jwt.InvalidTokenError:
        raise ErrorAPI("Token inválido.", 401)

    try:
        usuario_id = int(claims["sub"])
    except ValueError:
        raise ErrorAPI("Token inválido.", 401)
    usuario = db.session.get(Usuario, usuario_id)
    if (
        usuario is None
        or not usuario.habilitado
        or not usuario.tiene_cuenta
        or claims.get("ver") != _version(usuario)
    ):
        raise ErrorAPI("Token inválido o cuenta deshabilitada.", 401)
    g.usuario = usuario
    return usuario


def exigir_rol(*roles):
    # El rol se lee de la base de datos, no del token: un cambio de rol aplica de inmediato.
    if g.usuario.rol.codigo not in roles:
        raise ErrorAPI("No tienes permiso para realizar esta operación.", 403)


def autorizar_por_metodo():
    """before_request de los recursos protegidos: autentica y aplica PERMISOS_POR_METODO."""
    autenticar()
    exigir_rol(*PERMISOS_POR_METODO.get(request.method, (ROL_ADMIN,)))


def requiere_rol(*roles):
    """Decorador para rutas sueltas: @requiere_rol("admin")."""

    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            autenticar()
            exigir_rol(*roles)
            return vista(*args, **kwargs)

        return envoltura

    return decorador


def requiere_login(vista):
    """Decorador para rutas que solo exigen una cuenta válida, sin importar el rol."""

    @wraps(vista)
    def envoltura(*args, **kwargs):
        autenticar()
        return vista(*args, **kwargs)

    return envoltura
