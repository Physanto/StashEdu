from flask import Blueprint, current_app, g, jsonify

from app.auth import dummy_hash, emitir_token, requiere_login, requiere_rol
from app.errors import ErrorAPI
from app.extensions import db
from app.models import Rol, Usuario
from app.models.rol import ROL_ADMIN
from app.security import validar_password, verificar_password
from app.utils import (
    entero_positivo,
    obtener_json,
    validar_email,
    validar_requeridos,
    validar_textos,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


@auth_bp.post("/register")
@requiere_rol(ROL_ADMIN)
def registrar():
    """Un admin crea la cuenta (rol + contraseña) de un usuario que ya existe."""
    datos = obtener_json()
    validar_requeridos(datos, ("usuario_id", "password", "rol_id"))
    usuario_id = entero_positivo(datos["usuario_id"], "usuario_id")
    rol_id = entero_positivo(datos["rol_id"], "rol_id")
    validar_password(datos["password"])
    if db.session.get(Rol, rol_id) is None:
        raise ErrorAPI(
            "rol_id no corresponde a un rol existente (consulte GET /api/v1/roles).", 400
        )

    # FOR UPDATE: dos registros simultáneos de la misma persona no crean dos cuentas.
    usuario = db.session.scalar(
        db.select(Usuario).where(Usuario.id == usuario_id).with_for_update()
    )
    if usuario is None:
        raise ErrorAPI("Usuario no encontrado.", 404)
    if usuario.tiene_cuenta:
        raise ErrorAPI("El usuario ya tiene una cuenta.", 409)
    if not usuario.habilitado:
        raise ErrorAPI("El usuario está deshabilitado.", 409)

    usuario.rol_id = rol_id
    usuario.set_password(datos["password"])
    db.session.commit()
    return jsonify(usuario.to_dict()), 201


@auth_bp.post("/login")
def login():
    datos = obtener_json()
    validar_requeridos(datos, ("email", "password"))
    validar_textos(datos, {"email": 120}, ("email",))
    validar_email(datos["email"])
    if not isinstance(datos["password"], str):
        raise ErrorAPI("El campo 'password' debe ser texto.", 400)

    usuario = db.session.scalar(db.select(Usuario).where(Usuario.email == datos["email"]))
    tiene_cuenta = usuario is not None and usuario.tiene_cuenta
    # Siempre se verifica un hash, exista o no la cuenta: la respuesta tarda lo
    # mismo y no revela qué correos están registrados.
    valido = verificar_password(
        usuario.password_hash if tiene_cuenta else dummy_hash(), datos["password"]
    )
    if not tiene_cuenta or not usuario.habilitado or not valido:
        raise ErrorAPI("Credenciales inválidas.", 401)
    return jsonify(
        {
            "access_token": emitir_token(usuario),
            "token_type": "Bearer",
            "expires_in": current_app.config["AUTH_TOKEN_MAX_AGE"],
            "usuario": usuario.to_dict(),
        }
    )


@auth_bp.get("/me")
@requiere_login
def perfil():
    return jsonify(g.usuario.to_dict())
