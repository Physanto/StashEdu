from flask import Blueprint, g, jsonify

from app.auth import autenticar, dummy_hash, emitir_token
from app.errors import ErrorAPI
from app.extensions import db
from app.models import Usuario
from app.routes.usuarios import REQUERIDOS, _validar, _validar_unicos
from app.security import validar_password, verificar_password
from app.utils import obtener_json, validar_email, validar_requeridos, validar_textos

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


@auth_bp.post("/register")
def registrar():
    datos = obtener_json()
    permitidos = set(REQUERIDOS) | {"telefono", "password"}
    if set(datos) - permitidos:
        raise ErrorAPI("El registro contiene campos no permitidos.")
    validar_requeridos(datos, REQUERIDOS + ("password",))
    _validar(datos)
    _validar_unicos(datos)
    validar_password(datos["password"])
    usuario = Usuario(**{c: datos[c] for c in permitidos - {"password"} if c in datos})
    usuario.set_password(datos["password"])
    db.session.add(usuario)
    db.session.commit()
    return jsonify(usuario.to_dict()), 201


@auth_bp.post("/login")
def login():
    datos = obtener_json()
    if set(datos) - {"email", "password"}:
        raise ErrorAPI("El login contiene campos no permitidos.")
    validar_requeridos(datos, ("email", "password"))
    if isinstance(datos.get("email"), str):
        datos["email"] = datos["email"].lower()
    validar_textos(datos, {"email": 120}, ("email",))
    validar_email(datos["email"])
    validar_password(datos["password"])
    usuario = db.session.scalar(
        db.select(Usuario).where(Usuario.email == datos["email"])
    )
    valido = verificar_password(
        usuario.password_hash if usuario and usuario.password_hash else dummy_hash(),
        datos["password"],
    )
    if not usuario or not usuario.password_hash or not usuario.activo or not valido:
        raise ErrorAPI("Credenciales inválidas.", 401)
    from flask import current_app

    return jsonify(
        {
            "access_token": emitir_token(usuario),
            "token_type": "Bearer",
            "expires_in": current_app.config["AUTH_TOKEN_MAX_AGE"],
            "usuario": usuario.to_dict(),
        }
    )


@auth_bp.get("/me")
def perfil():
    autenticar()
    return jsonify(g.usuario.to_dict())
