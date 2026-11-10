"""Comandos de terminal para las cuentas: crear el primer admin y cambiar contraseñas.

POST /auth/register exige un admin; el primero se crea desde un terminal de
confianza con `flask --app run crear-admin`.
"""

import click
from flask.cli import with_appcontext

from app.errors import ErrorAPI
from app.extensions import db
from app.models import Rol, TipoUsuario, Usuario
from app.models.rol import ROL_ADMIN
from app.utils import validar_email


def _guardar(usuario, password):
    try:
        usuario.set_password(password)
        db.session.commit()
    except ErrorAPI as error:
        db.session.rollback()
        raise click.ClickException(error.mensaje)


@click.command("crear-admin")
@click.option("--nombre", prompt="Nombre completo")
@click.option("--documento", prompt="Documento")
@click.option("--email", prompt="Email")
@click.option(
    "--tipo-usuario",
    default="funcionario",
    show_default=True,
    help="Código del tipo de usuario (estudiante, docente o funcionario).",
)
@click.password_option("--password", confirmation_prompt=True)
@with_appcontext
def crear_admin(nombre, documento, email, tipo_usuario, password):
    """Crear una persona con cuenta de rol admin."""
    try:
        validar_email(email)
    except ErrorAPI as error:
        raise click.ClickException(error.mensaje)
    tipo = db.session.scalar(db.select(TipoUsuario).filter_by(codigo=tipo_usuario))
    rol = db.session.scalar(db.select(Rol).filter_by(codigo=ROL_ADMIN))
    if tipo is None:
        raise click.ClickException(f"No existe el tipo de usuario '{tipo_usuario}'.")
    if rol is None:
        raise click.ClickException("No existe el rol admin: ejecuta `flask db upgrade`.")
    for campo, valor in (("documento", documento), ("email", email)):
        if db.session.scalar(db.select(Usuario.id).filter_by(**{campo: valor})):
            raise click.ClickException(f"Ya existe un usuario con ese {campo}.")

    usuario = Usuario(
        nombre_completo=nombre,
        documento=documento,
        email=email,
        tipo_usuario_id=tipo.id,
        rol_id=rol.id,
    )
    db.session.add(usuario)
    _guardar(usuario, password)
    click.echo(f"Admin creado con id {usuario.id}. Inicia sesión con POST /api/v1/auth/login.")


@click.command("set-password")
@click.argument("usuario_id", type=click.IntRange(min=1))
@click.password_option(confirmation_prompt=True)
@with_appcontext
def set_password(usuario_id, password):
    """Cambiar la contraseña de una cuenta existente (invalida sus tokens)."""
    usuario = db.session.get(Usuario, usuario_id)
    if usuario is None:
        raise click.ClickException("Usuario no encontrado.")
    if not usuario.tiene_cuenta:
        raise click.ClickException(
            "El usuario no tiene cuenta: un admin debe crearla con POST /api/v1/auth/register."
        )
    _guardar(usuario, password)
    click.echo("Contraseña actualizada; los tokens anteriores quedan invalidados.")
